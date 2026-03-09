/**
 * AgentRuntime — the agentic execution loop for a single agent.
 *
 * Lifecycle per `run()` call:
 *   1. Build system prompt  (base prompt + identity + skills + working memory)
 *   2. Resolve tool schemas  (registry definitions × executor handlers × policy filter)
 *   3. LLM call
 *   4. If tool_calls → execute each tool → append results → goto 3
 *   5. If text response → record to memory → return
 *
 * Each agent instance is cheap: it holds a spec + prompt + shared deps reference.
 * Heavy resources (LLM client, tool executor, memory manager) are shared via deps.
 */

import type { AgentSpec } from "../spec/agent"
import type { ChatMessage } from "../llm/types"
import type { AgentDeps, RunOptions, RunResult, ToolCallRecord } from "./types"
import { PromptBuilder } from "./prompt-builder"

const DEFAULT_MAX_ITERATIONS = 10
const DEFAULT_TEMPERATURE = 0.15
const LOOP_DETECT_WINDOW = 4
const MAX_CONTEXT_MESSAGES = 40
const MAX_TOOL_RESULT_LENGTH = 1500

export class AgentRuntime {
  readonly spec: AgentSpec
  readonly prompt: string
  private deps: AgentDeps

  constructor(spec: AgentSpec, prompt: string, deps: AgentDeps) {
    this.spec = spec
    this.prompt = prompt
    this.deps = deps
  }

  async run(input: string, options?: RunOptions): Promise<RunResult> {
    const { llm, toolExecutor, toolRegistry, memoryManager, skillManager } = this.deps
    const maxIter = options?.maxIterations ?? DEFAULT_MAX_ITERATIONS

    const workingContext = await memoryManager.getWorkingContext(
      this.spec.id,
      this.spec.memory,
    )
    const systemPrompt = await PromptBuilder.build({
      basePrompt: this.prompt,
      spec: this.spec,
      skillManager,
      workingContext,
      workerDescriptions: this.deps.getWorkerDescriptions?.() ?? null,
    })

    const allTools = await toolRegistry.loadAll()
    const agentTools = toolRegistry.resolve(this.spec.tools, allTools)
    const toolSchemas = toolExecutor.toOpenAISchemas(agentTools)

    const messages: ChatMessage[] = [
      { role: "system", content: systemPrompt },
      { role: "user", content: input },
    ]

    const toolCallLog: ToolCallRecord[] = []
    let totalPrompt = 0
    let totalCompletion = 0
    let iterations = 0
    let trimmedCount = 0

    const recentTargets: string[] = []

    while (iterations < maxIter) {
      iterations++
      options?.onIteration?.(iterations)

      const response = await llm.chat(messages, {
        model: options?.model,
        temperature: options?.temperature ?? DEFAULT_TEMPERATURE,
        tools: toolSchemas.length > 0 ? toolSchemas : undefined,
        signal: options?.signal,
      })

      if (response.usage) {
        totalPrompt += response.usage.promptTokens
        totalCompletion += response.usage.completionTokens
      }

      if (!response.toolCalls || response.toolCalls.length === 0) {
        const store = memoryManager.getStore(this.spec.id, this.spec.memory)
        await store.append({
          type: "action",
          content: `Responded: ${response.content.slice(0, 200)}`,
          tags: ["response"],
        })

        return {
          response: response.content,
          toolCalls: toolCallLog,
          iterations,
          usage: { promptTokens: totalPrompt, completionTokens: totalCompletion },
          messages,
          trimmedMessages: trimmedCount || undefined,
        }
      }

      messages.push({
        role: "assistant",
        content: response.content || "",
        tool_calls: response.toolCalls,
      })

      for (const tc of response.toolCalls) {
        const toolName = tc.function.name
        let args: Record<string, unknown>
        try {
          args = JSON.parse(tc.function.arguments)
        } catch {
          args = {}
        }

        options?.onToolCall?.(toolName, args)

        const result = await toolExecutor.execute(toolName, args)
        let output = result.ok ? result.output : `Error: ${result.error}`

        options?.onToolResult?.(toolName, output, result.ok)

        toolCallLog.push({
          tool: toolName,
          args,
          result: output,
          ok: result.ok,
          durationMs: result.durationMs,
          ...(result.metadata?.subTrace ? { subTrace: result.metadata.subTrace as ToolCallRecord["subTrace"] } : {}),
        })

        const store = memoryManager.getStore(this.spec.id, this.spec.memory)
        await store.append({
          type: result.ok ? "action" : "error",
          content: `${toolName}(${JSON.stringify(args).slice(0, 100)}): ${output.slice(0, 150)}`,
          tags: [toolName],
        })

        // --- Loop detection ---
        // Track recent tool call signatures; if the last N calls repeat a
        // pattern, inject a warning so the LLM breaks the cycle.
        const sig = `${toolName}:${JSON.stringify(args)}`
        recentTargets.push(sig)
        if (recentTargets.length > LOOP_DETECT_WINDOW * 3) {
          recentTargets.splice(0, recentTargets.length - LOOP_DETECT_WINDOW * 3)
        }

        if (recentTargets.length >= LOOP_DETECT_WINDOW) {
          const tail = recentTargets.slice(-LOOP_DETECT_WINDOW)
          const unique = new Set(tail)
          if (unique.size <= 2) {
            output += "\n\n⚠ WARNING: You are repeating the same actions. " +
              "The locations you have been visiting do not contain what you need. " +
              "Try a DIFFERENT location you have NOT visited yet. " +
              "Consider: drawers, cabinets, shelves, sidetables, dressers, or other receptacles listed in the room description."
          }
        }

        messages.push({
          role: "tool",
          content: output.length > MAX_TOOL_RESULT_LENGTH
            ? output.slice(0, MAX_TOOL_RESULT_LENGTH) + "\n…[truncated]"
            : output,
          tool_call_id: tc.id,
          name: toolName,
        })
      }

      if (messages.length > MAX_CONTEXT_MESSAGES + 2) {
        const excess = messages.length - (MAX_CONTEXT_MESSAGES + 2)
        messages.splice(2, excess)
        trimmedCount += excess
      }
    }

    const lastAssistant = messages
      .filter((m) => m.role === "assistant")
      .pop()?.content
    return {
      response: lastAssistant || "[Max iterations reached]",
      toolCalls: toolCallLog,
      iterations,
      usage: { promptTokens: totalPrompt, completionTokens: totalCompletion },
      messages,
      trimmedMessages: trimmedCount || undefined,
    }
  }
}
