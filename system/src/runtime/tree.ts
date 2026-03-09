/**
 * TreeRuntime — loads all agents from a workspace directory and provides
 * a unified interface to run any agent in the tree.
 *
 * Workspace layout:
 *   <baseDir>/           (the tree directory)
 *     agents/            .md files (frontmatter spec + prompt body)
 *     skills/            .md skill files (frontmatter + content)
 *     memory/            .jsonl per-agent memory stores
 *
 *   <toolsDir>/          (shared tool definitions — may be outside baseDir)
 *     *.json             tool definitions
 *
 * Resources are shared: one LLMClient, one ToolExecutor, one ToolRegistry,
 * one SkillManager. Each agent only holds its own spec + prompt + a
 * MemoryManager reference scoped to its ID.
 */

import { AgentRuntime } from "./agent"
import type { AgentDeps, RunOptions, RunResult } from "./types"
import { AgentStore } from "../spec/store"
import { ToolRegistry } from "../tool/registry"
import { ToolExecutor, type ToolHandler } from "../tool/executor"
import { MemoryManager } from "../memory/manager"
import type { Mem0Bridge } from "../memory/mem0-bridge"
import { SkillManager } from "../skill/manager"
import { LLMClient, type LLMClientOptions } from "../llm/client"
import { MessageBus } from "../messaging/bus"
import { Delegator } from "../messaging/delegate"
import { ReflectionEngine } from "../reflection/engine"
import { PerformanceMonitor } from "../extension/monitor"
import { DynamicExtensionEngine } from "../extension/engine"
import { AgentRouter } from "./router"
import type { FailureInfo } from "../reflection/types"
import type { DelegateResult } from "../messaging/types"
import { join } from "node:path"

export interface TreeRuntimeOptions {
  baseDir: string
  /** Directory containing tool JSON definitions. Defaults to join(baseDir, "tools"). */
  toolsDir?: string
  llmOptions: LLMClientOptions
  toolHandlers?: Record<string, ToolHandler>
  extensionThreshold?: number
  maxSteps?: number
  mem0?: Mem0Bridge
}

export class TreeRuntime {
  private agents = new Map<string, AgentRuntime>()
  private baseDir: string
  private llm: LLMClient
  private toolExecutor: ToolExecutor
  private toolRegistry: ToolRegistry
  private skillManager: SkillManager
  private memoryManager: MemoryManager

  readonly bus: MessageBus
  readonly delegator: Delegator
  readonly reflection: ReflectionEngine
  readonly monitor: PerformanceMonitor
  readonly extension: DynamicExtensionEngine
  readonly router: AgentRouter

  constructor(options: TreeRuntimeOptions) {
    this.baseDir = options.baseDir
    this.llm = new LLMClient(options.llmOptions)
    this.toolExecutor = new ToolExecutor()
    this.toolRegistry = new ToolRegistry(options.toolsDir ?? join(options.baseDir, "tools"))
    this.skillManager = new SkillManager(join(options.baseDir, "skills"))
    this.memoryManager = new MemoryManager(join(options.baseDir, "memory"), options.mem0)

    if (options.toolHandlers) {
      this.toolExecutor.registerMany(options.toolHandlers)
    }

    this.bus = new MessageBus()
    this.delegator = new Delegator(this.bus, this.agents)
    this.reflection = new ReflectionEngine({
      llm: this.llm,
      memoryManager: this.memoryManager,
    })
    this.monitor = new PerformanceMonitor()
    this.extension = new DynamicExtensionEngine({
      baseDir: options.baseDir,
      monitor: this.monitor,
      llm: this.llm,
      extensionThreshold: options.extensionThreshold,
      maxSteps: options.maxSteps,
    })
    this.router = new AgentRouter(this.agents)
  }

  async loadAll(): Promise<number> {
    const store = new AgentStore(join(this.baseDir, "agents"))
    const parsedAgents = await store.list()

    for (const parsed of parsedAgents) {
      const deps: AgentDeps = {
        llm: this.llm,
        toolExecutor: this.toolExecutor,
        toolRegistry: this.toolRegistry,
        memoryManager: this.memoryManager,
        skillManager: this.skillManager,
      }

      if (parsed.spec.role === "orchestrator") {
        deps.getWorkerDescriptions = () => this.buildWorkerDescriptions()
      }

      const runtime = new AgentRuntime(parsed.spec, parsed.prompt, deps)

      this.agents.set(parsed.spec.id, runtime)
    }

    return this.agents.size
  }

  async reload(): Promise<number> {
    this.agents.clear()
    return this.loadAll()
  }

  get(agentId: string): AgentRuntime | undefined {
    return this.agents.get(agentId)
  }

  list(): AgentRuntime[] {
    return Array.from(this.agents.values())
  }

  listIds(): string[] {
    return Array.from(this.agents.keys())
  }

  has(agentId: string): boolean {
    return this.agents.has(agentId)
  }

  async run(agentId: string, input: string, options?: RunOptions): Promise<RunResult> {
    const agent = this.agents.get(agentId)
    if (!agent) {
      const available = Array.from(this.agents.keys()).join(", ")
      throw new Error(`Agent "${agentId}" not found. Available: ${available}`)
    }
    return agent.run(input, options)
  }

  async delegate(params: {
    from: string
    to: string
    input: string
    metadata?: Record<string, unknown>
    runOptions?: RunOptions
  }): Promise<DelegateResult> {
    const result = await this.delegator.delegate(params)

    this.monitor.record({
      taskId: result.taskId,
      taskType: params.metadata?.taskType as string ?? "unknown",
      agentUsed: params.to,
      success: result.success,
      errorMessage: result.error,
      metadata: params.metadata,
    })

    if (!result.success && result.error) {
      const agent = this.agents.get(params.to)
      const failure: FailureInfo = {
        domain: agent?.spec.metadata?.domain as string ?? "unknown",
        taskType: params.metadata?.taskType as string ?? "unknown",
        agentId: params.to,
        errorMessage: result.error,
        actionHistory: result.toolCalls?.map(
          (tc) => `${tc.tool}(${JSON.stringify(tc.args).slice(0, 80)})`
        ) ?? [],
        toolsUsed: result.toolCalls?.map((tc) => tc.tool) ?? [],
        successRate: this.monitor.getStats().successRate,
      }
      const reflections = await this.reflection.analyzeBatch([failure])
      await this.reflection.applyToMemory(reflections)

      if (this.memoryManager.hasMem0()) {
        for (const r of reflections) {
          if (r.confidence >= 0.3) {
            await this.memoryManager.addLesson(
              r.agentId,
              `[${r.failureType}] ${r.rootCause}`,
              { errorPattern: r.errorPattern, taskType: r.taskType },
            )
          }
        }
      }
    }

    return result
  }

  async checkAndExtend(): Promise<number> {
    const proposals = await this.extension.checkAndExtend()
    if (proposals.length > 0) {
      await this.reload()

      if (this.memoryManager.hasMem0()) {
        for (const p of proposals) {
          await this.memoryManager.addOrgKnowledge(
            `Extension created: ${JSON.stringify(p)}`,
            { type: "extension_record" },
          )
        }
      }
    }
    return proposals.length
  }

  registerTool(id: string, handler: ToolHandler): void {
    this.toolExecutor.register(id, handler)
  }

  registerTools(tools: Record<string, ToolHandler>): void {
    this.toolExecutor.registerMany(tools)
  }

  registerDelegateTool(options?: {
    managerId?: string
    successCheck?: () => boolean
    runOptions?: RunOptions
  }): void {
    const fromId = options?.managerId ?? "alfworld_manager"

    this.toolExecutor.register("delegate", async (args) => {
      const workerId = args.worker_id as string
      const task = args.task as string

      if (!this.agents.has(workerId)) {
        const available = Array.from(this.agents.keys())
          .filter((id) => this.agents.get(id)?.spec.role === "worker")
          .join(", ")
        return `Error: Worker "${workerId}" not found. Available workers: ${available}`
      }

      const result = await this.delegator.delegate({
        from: fromId,
        to: workerId,
        input: task,
        successCheck: options?.successCheck,
        runOptions: options?.runOptions,
      })

      this.monitor.recordSubtask({
        taskId: `delegate_${Date.now()}`,
        subtaskIndex: 0,
        subtaskType: workerId.replace(/_worker$/, ""),
        workerId,
        success: result.success,
        steps: result.toolCalls?.length ?? 0,
        toolCalls: (result.toolCalls ?? []).map((tc) => ({
          tool: tc.tool,
          args: tc.args,
          result: tc.result,
        })),
        errorMessage: result.error,
      })

      const traceLines: string[] = []
      if (result.toolCalls && result.toolCalls.length > 0) {
        traceLines.push("## Execution Trace")
        for (const tc of result.toolCalls) {
          const argsStr = Object.entries(tc.args).map(([k, v]) => `${k}="${v}"`).join(", ")
          traceLines.push(`> ${tc.tool}(${argsStr})`)
          traceLines.push(`  → ${tc.result.slice(0, 300)}`)
        }
      }

      const trace = traceLines.join("\n")

      // Build structured sub-trace for trace capture
      const subTrace = result.runResult ? {
        agentId: workerId,
        toolCalls: result.runResult.toolCalls,
        iterations: result.runResult.iterations,
        usage: result.runResult.usage,
        messages: result.runResult.messages,
      } : undefined

      const output = result.success
        ? `SUCCESS: Worker ${workerId} completed the subtask.\n\n${trace}\n\n## Worker Response\n${result.output.slice(0, 500)}`
        : `FAILED: Worker ${workerId} did not complete the subtask.\n\n${trace}\n\n## Worker Response\n${result.output.slice(0, 500)}${result.error ? `\n\n## Error\n${result.error}` : ""}`

      return { output, metadata: { subTrace } }
    })
  }

  getMemoryManager(): MemoryManager {
    return this.memoryManager
  }

  getToolExecutor(): ToolExecutor {
    return this.toolExecutor
  }

  getLLM(): LLMClient {
    return this.llm
  }

  getSkillManager(): SkillManager {
    return this.skillManager
  }

  getBaseDir(): string {
    return this.baseDir
  }

  private buildWorkerDescriptions(): string | null {
    const workers = Array.from(this.agents.values())
      .filter((a) => a.spec.role === "worker")
    if (workers.length === 0) return null

    return workers.map((w) => {
      const tools = w.spec.tools.allow.join(", ")
      const caps = (w.spec.metadata?.capabilities as string[])?.join(", ") ?? ""
      const desc = w.spec.description ?? ""
      const status = (w.spec.metadata?.status as string) === "probation" ? " [probation]" : ""
      return `- **${w.spec.id}**${status}: ${desc}\n  tools: [${tools}]${caps ? `\n  capabilities: [${caps}]` : ""}`
    }).join("\n")
  }
}
