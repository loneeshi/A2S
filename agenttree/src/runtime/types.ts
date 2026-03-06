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
}

export interface RunResult {
  response: string
  toolCalls: ToolCallRecord[]
  iterations: number
  usage: {
    promptTokens: number
    completionTokens: number
  }
}
