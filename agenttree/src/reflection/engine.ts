/**
 * ReflectionEngine — analyzes task failures and produces structured
 * reflections that can update memory and prompt caches.
 *
 * Two modes:
 *   1. Rule-based heuristics (no LLM needed, always available)
 *   2. LLM-assisted analysis (optional, higher quality)
 *
 * After analysis, reflections are stored as memory entries and can
 * be applied to agent prompts via PromptBuilder's working context.
 */

import type { LLMClient } from "../llm/client"
import type { MemoryManager } from "../memory/manager"
import type { MemoryConfig } from "../spec/agent"
import type {
  FailureInfo,
  FailureType,
  PromptUpdateAction,
  ReflectionOutput,
} from "./types"

let _reflectionId = 0

export class ReflectionEngine {
  private llm?: LLMClient
  private memoryManager?: MemoryManager

  constructor(options?: { llm?: LLMClient; memoryManager?: MemoryManager }) {
    this.llm = options?.llm
    this.memoryManager = options?.memoryManager
  }

  async analyze(failure: FailureInfo): Promise<ReflectionOutput> {
    const reflectionId = `refl_${Date.now()}_${++_reflectionId}`
    const timestamp = new Date().toISOString()

    if (this.llm) {
      try {
        return await this.analyzeWithLLM(failure, reflectionId, timestamp)
      } catch {
        // fall through to rule-based
      }
    }

    return this.analyzeRuleBased(failure, reflectionId, timestamp)
  }

  async analyzeBatch(failures: FailureInfo[]): Promise<ReflectionOutput[]> {
    return Promise.all(failures.map((f) => this.analyze(f)))
  }

  async applyToMemory(
    reflections: ReflectionOutput[],
    memoryConfig: MemoryConfig = { mode: "light", store: "jsonl", capacity: 200 },
  ): Promise<number> {
    if (!this.memoryManager) return 0

    let applied = 0
    for (const r of reflections) {
      const store = this.memoryManager.getStore(r.agentId, memoryConfig)

      await store.append({
        type: "lesson",
        content: `[${r.failureType}] ${r.rootCause}`,
        tags: ["reflection", r.errorPattern],
      })
      applied++

      for (const update of r.memoryUpdates) {
        await store.append({
          type: update.type,
          content: update.content,
          tags: update.tags,
        })
        applied++
      }
    }

    return applied
  }

  private analyzeRuleBased(
    failure: FailureInfo,
    reflectionId: string,
    timestamp: string,
  ): ReflectionOutput {
    const error = failure.errorMessage.toLowerCase()

    let failureType: FailureType = "unknown"
    let action: PromptUpdateAction = "no_update"

    if (error.includes("tool") || error.includes("function") || error.includes("not registered")) {
      failureType = "tool_misuse"
      action = "update_tool_specifications"
    } else if (error.includes("step") || error.includes("sequence") || error.includes("order")) {
      failureType = "missing_step"
      action = "update_workflow_structure"
    } else if (error.includes("object") || error.includes("target") || error.includes("wrong")) {
      failureType = "wrong_object"
      action = "update_error_prevention"
    } else if (error.includes("timeout") || error.includes("max iteration")) {
      failureType = "timeout"
      action = "update_workflow_structure"
    }

    const errorPattern = `${failureType}:${failure.domain}`

    let promptUpdateContent = ""
    if (action !== "no_update") {
      promptUpdateContent =
        `[Auto-detected ${failureType}] Error: ${failure.errorMessage}. ` +
        `Tools: ${failure.toolsUsed.join(", ")}.`
    }

    return {
      reflectionId,
      timestamp,
      domain: failure.domain,
      taskType: failure.taskType,
      agentId: failure.agentId,
      failureType,
      rootCause: failure.errorMessage,
      toolsInvolved: failure.toolsUsed,
      errorPattern,
      promptUpdateAction: action,
      promptUpdateContent,
      memoryUpdates:
        action !== "no_update"
          ? [
              {
                type: "error",
                content: `${failureType} in ${failure.domain}: ${failure.errorMessage}`,
                tags: [failureType, failure.domain],
              },
            ]
          : [],
      retryRecommendation: action !== "no_update",
      confidence: 0.3,
    }
  }

  private async analyzeWithLLM(
    failure: FailureInfo,
    reflectionId: string,
    timestamp: string,
  ): Promise<ReflectionOutput> {
    const prompt = this.buildAnalysisPrompt(failure)
    const response = await this.llm!.chat(
      [
        { role: "system", content: "You are a failure analysis expert. Return ONLY valid JSON." },
        { role: "user", content: prompt },
      ],
      { temperature: 0.3 },
    )

    let raw = response.content.trim()
    if (raw.startsWith("```")) {
      const lines = raw.split("\n")
      raw = lines.slice(1, -1).join("\n")
    }

    const data = JSON.parse(raw)

    return {
      reflectionId,
      timestamp,
      domain: failure.domain,
      taskType: failure.taskType,
      agentId: failure.agentId,
      failureType: data.failure_type ?? "unknown",
      rootCause: data.root_cause ?? "",
      toolsInvolved: data.tools_involved ?? failure.toolsUsed,
      errorPattern: data.error_pattern ?? "",
      promptUpdateAction: data.prompt_update_action ?? "no_update",
      promptUpdateContent: data.prompt_update_content ?? "",
      memoryUpdates: (data.memory_updates ?? []).map(
        (u: { type: string; content: string; tags: string[] }) => ({
          type: u.type === "lesson" ? "lesson" : u.type === "error" ? "error" : "action",
          content: u.content,
          tags: u.tags ?? [],
        }),
      ),
      retryRecommendation: data.retry_recommendation ?? false,
      confidence: data.confidence ?? 0.5,
    }
  }

  private buildAnalysisPrompt(failure: FailureInfo): string {
    const actions = failure.actionHistory.map((a) => `  - ${a}`).join("\n")
    const tools = failure.toolsUsed.join(", ")

    return `Analyze this agent task failure and return a JSON object.

Domain: ${failure.domain}
Task type: ${failure.taskType}
Agent: ${failure.agentId}
Error message: ${failure.errorMessage}
Observation: ${failure.observation ?? "N/A"}
Tools used: ${tools}
Success rate: ${failure.successRate}
Action history:
${actions}

Return ONLY a JSON object with these fields:
- failure_type: one of "wrong_object", "missing_step", "tool_misuse", "incorrect_sequence", "timeout", "unknown"
- root_cause: 1-2 sentence root cause
- tools_involved: list of tool names involved
- error_pattern: short pattern name (e.g. "tool_misuse:navigation")
- prompt_update_action: one of "update_error_prevention", "update_tool_specifications", "update_core_protocol", "update_workflow_structure", "add_dynamic_example", "no_update"
- prompt_update_content: specific text to add to the prompt section
- memory_updates: list of {type: "lesson"|"error"|"action", content: string, tags: string[]}
- retry_recommendation: boolean
- confidence: float 0.0-1.0`
  }
}
