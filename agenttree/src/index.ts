// === Spec layer (schemas & validation) ===
export { AgentSpecSchema, ToolPolicySchema, MemoryConfigSchema } from "./spec/agent"
export type { AgentSpec, ToolPolicy, MemoryConfig } from "./spec/agent"
export { SkillSpecSchema } from "./spec/skill"
export type { SkillSpec } from "./spec/skill"
export { MemoryEntrySchema } from "./spec/memory"
export type { MemoryEntry } from "./spec/memory"
export { AgentStore } from "./spec/store"

// === Parser (markdown frontmatter ↔ AgentSpec) ===
export { parseAgentFile, stringifyAgentFile } from "./parser"
export type { ParsedAgent } from "./parser"

// === Tool (registry + executor) ===
export { ToolRegistry, ToolDefinitionSchema, getDefaultRegistry } from "./tool"
export type { ToolDefinition } from "./tool"
export { ToolExecutor } from "./tool"
export type { ToolResult, ToolHandler } from "./tool"

// === Memory (store + manager) ===
export { MemoryStore, NoopMemoryStore } from "./memory/store"
export { MemoryManager } from "./memory/manager"

// === Skill (manager + evolution) ===
export { SkillManager, getDefaultSkillManager } from "./skill"
export { SkillEvolutionEngine } from "./skill/evolution"
export type { SkillEvolutionOptions, EvolutionResult } from "./skill/evolution"

// === LLM (client) ===
export { LLMClient } from "./llm"
export type { LLMClientOptions } from "./llm"
export type { ChatMessage, ChatResponse, ChatOptions, ToolCallRequest, ToolSchema } from "./llm"

// === Messaging (bus + delegation) ===
export { MessageBus } from "./messaging"
export { Delegator } from "./messaging"
export type {
  AgentMessage,
  MessageType,
  MessageHandler,
  DelegateRequest,
  DelegateResult,
} from "./messaging"

// === Reflection (failure analysis) ===
export { ReflectionEngine } from "./reflection"
export type {
  FailureInfo,
  FailureType,
  PromptUpdateAction,
  ReflectionOutput,
} from "./reflection"

// === Extension (dynamic tree expansion) ===
export { PerformanceMonitor, DynamicExtensionEngine } from "./extension"
export type {
  ExtensionType,
  ExtensionProposal,
  TaskResult,
  PerformanceStats,
  ExtensionEngineOptions,
} from "./extension"

// === Bridge (benchmark environment connection) ===
export { BenchmarkBridge } from "./bridge"
export type { BridgeOptions, ResetResult, StepResult, StatusResult } from "./bridge"

// === Utils (workspace merge) ===
export { WorkspaceMerger } from "./utils"
export type { MergeResult } from "./utils"

// === Runtime (agent loop + tree + factory) ===
export { AgentRuntime } from "./runtime"
export { TreeRuntime } from "./runtime"
export type { TreeRuntimeOptions } from "./runtime"
export { PromptBuilder } from "./runtime"
export { createAgent, createInlineAgent } from "./runtime"
export type {
  AgentDeps,
  RunOptions,
  RunResult,
  ToolCallRecord,
  CreateAgentOptions,
  CreateInlineAgentOptions,
} from "./runtime"
