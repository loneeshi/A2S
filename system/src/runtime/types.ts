/**
 * Runtime type definitions.
 *
 * Separating types from implementation keeps imports clean and avoids
 * circular dependencies between runtime modules.
 */

import type { LLMClient } from "../llm/client"
import type { ToolExecutor } from "../tool/executor"
import type { ToolRegistry } from "../tool/registry"
import type { MemoryManager } from "../memory/manager"
import type { SkillManager } from "../skill/manager"

export interface AgentDeps {
  llm: LLMClient
  toolExecutor: ToolExecutor
  toolRegistry: ToolRegistry
  memoryManager: MemoryManager
  skillManager: SkillManager
  /** For orchestrators: returns current worker descriptions to inject into prompt */
  getWorkerDescriptions?: () => string | null
}

export interface RunOptions {
  maxIterations?: number
  signal?: AbortSignal
  temperature?: number
  model?: string
  onToolCall?: (toolName: string, args: Record<string, unknown>) => void
  onToolResult?: (toolName: string, result: string, ok: boolean) => void
  onIteration?: (iteration: number) => void
}

export interface ToolCallRecord {
  tool: string
  args: Record<string, unknown>
  result: string
  ok: boolean
  durationMs?: number
  /** For delegate calls: structured sub-agent execution trace. */
  subTrace?: {
    agentId: string
    toolCalls: ToolCallRecord[]
    iterations: number
    usage: { promptTokens: number; completionTokens: number }
    messages?: import("../llm/types").ChatMessage[]
  }
}

export interface RunResult {
  response: string
  toolCalls: ToolCallRecord[]
  iterations: number
  usage: {
    promptTokens: number
    completionTokens: number
  }
  /** Full LLM conversation history (system + user + assistant + tool messages). */
  messages?: import("../llm/types").ChatMessage[]
  /** Number of conversation messages trimmed by the sliding window. */
  trimmedMessages?: number
}
