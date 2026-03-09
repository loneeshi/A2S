/**
 * Factory helpers for creating agents without manually wiring deps.
 */

import type { AgentSpec } from "../spec/agent"
import type { ToolHandler } from "../tool/executor"
import type { LLMClientOptions } from "../llm/client"
import { AgentRuntime } from "./agent"
import { AgentStore } from "../spec/store"
import { ToolRegistry } from "../tool/registry"
import { ToolExecutor } from "../tool/executor"
import { MemoryManager } from "../memory/manager"
import { SkillManager } from "../skill/manager"
import { LLMClient } from "../llm/client"
import { join } from "node:path"

export interface CreateAgentOptions {
  agentId: string
  baseDir: string
  llmOptions: LLMClientOptions
  toolHandlers?: Record<string, ToolHandler>
}

export async function createAgent(options: CreateAgentOptions): Promise<AgentRuntime | undefined> {
  const store = new AgentStore(join(options.baseDir, "agents"))
  const parsed = await store.get(options.agentId)
  if (!parsed) return undefined

  const toolExecutor = new ToolExecutor()
  if (options.toolHandlers) {
    toolExecutor.registerMany(options.toolHandlers)
  }

  return new AgentRuntime(parsed.spec, parsed.prompt, {
    llm: new LLMClient(options.llmOptions),
    toolExecutor,
    toolRegistry: new ToolRegistry(join(options.baseDir, "tools")),
    memoryManager: new MemoryManager(join(options.baseDir, "memory")),
    skillManager: new SkillManager(join(options.baseDir, "skills")),
  })
}

export interface CreateInlineAgentOptions {
  spec: AgentSpec
  prompt: string
  llmOptions: LLMClientOptions
  baseDir?: string
  toolHandlers?: Record<string, ToolHandler>
}

export function createInlineAgent(options: CreateInlineAgentOptions): AgentRuntime {
  const baseDir = options.baseDir ?? process.cwd()
  const toolExecutor = new ToolExecutor()
  if (options.toolHandlers) {
    toolExecutor.registerMany(options.toolHandlers)
  }

  return new AgentRuntime(options.spec, options.prompt, {
    llm: new LLMClient(options.llmOptions),
    toolExecutor,
    toolRegistry: new ToolRegistry(join(baseDir, "tools")),
    memoryManager: new MemoryManager(join(baseDir, "memory")),
    skillManager: new SkillManager(join(baseDir, "skills")),
  })
}
