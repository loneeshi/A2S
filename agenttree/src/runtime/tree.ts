/**
 * TreeRuntime — loads all agents from a workspace directory and provides
 * a unified interface to run any agent in the tree.
 *
 * Workspace layout:
 *   <baseDir>/
 *     agents/       .md files (frontmatter spec + prompt body)
 *     tools/        .json tool definitions
 *     skills/       .md skill files (frontmatter + content)
 *     memory/       .jsonl per-agent memory stores
 *
 * Resources are shared: one LLMClient, one ToolExecutor, one ToolRegistry,
 * one SkillManager. Each agent only holds its own spec + prompt + a
 * MemoryManager reference scoped to its ID.
 *
 * New in this version:
 *   - MessageBus for inter-agent communication
 *   - Delegator for manager → worker task dispatch
 *   - ReflectionEngine for failure analysis
 *   - PerformanceMonitor + DynamicExtensionEngine for auto-expansion
 */

import { AgentRuntime } from "./agent"
import type { RunOptions, RunResult } from "./types"
import { AgentStore } from "../spec/store"
import { ToolRegistry } from "../tool/registry"
import { ToolExecutor, type ToolHandler } from "../tool/executor"
import { MemoryManager } from "../memory/manager"
import { SkillManager } from "../skill/manager"
import { LLMClient, type LLMClientOptions } from "../llm/client"
import { MessageBus } from "../messaging/bus"
import { Delegator } from "../messaging/delegate"
import { ReflectionEngine } from "../reflection/engine"
import { PerformanceMonitor } from "../extension/monitor"
import { DynamicExtensionEngine } from "../extension/engine"
import type { FailureInfo } from "../reflection/types"
import type { DelegateResult } from "../messaging/types"
import { join } from "node:path"

export interface TreeRuntimeOptions {
  baseDir: string
  llmOptions: LLMClientOptions
  toolHandlers?: Record<string, ToolHandler>
  extensionThreshold?: number
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

  constructor(options: TreeRuntimeOptions) {
    this.baseDir = options.baseDir
    this.llm = new LLMClient(options.llmOptions)
    this.toolExecutor = new ToolExecutor()
    this.toolRegistry = new ToolRegistry(join(options.baseDir, "tools"))
    this.skillManager = new SkillManager(join(options.baseDir, "skills"))
    this.memoryManager = new MemoryManager(join(options.baseDir, "memory"))

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
      extensionThreshold: options.extensionThreshold,
    })
  }

  async loadAll(): Promise<number> {
    const store = new AgentStore(join(this.baseDir, "agents"))
    const parsedAgents = await store.list()

    for (const parsed of parsedAgents) {
      const runtime = new AgentRuntime(parsed.spec, parsed.prompt, {
        llm: this.llm,
        toolExecutor: this.toolExecutor,
        toolRegistry: this.toolRegistry,
        memoryManager: this.memoryManager,
        skillManager: this.skillManager,
      })

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
    }

    return result
  }

  async checkAndExtend(): Promise<number> {
    const proposals = await this.extension.checkAndExtend()
    if (proposals.length > 0) {
      await this.reload()
    }
    return proposals.length
  }

  registerTool(id: string, handler: ToolHandler): void {
    this.toolExecutor.register(id, handler)
  }

  registerTools(tools: Record<string, ToolHandler>): void {
    this.toolExecutor.registerMany(tools)
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
}
