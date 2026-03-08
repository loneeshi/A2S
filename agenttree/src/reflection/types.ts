/**
 * Reflection types — structured analysis of task failures.
 */

export type FailureType =
  | "wrong_object"
  | "missing_step"
  | "tool_misuse"
  | "incorrect_sequence"
  | "timeout"
  | "unknown"

export type PromptUpdateAction =
  | "update_error_prevention"
  | "update_tool_specifications"
  | "update_core_protocol"
  | "update_workflow_structure"
  | "add_dynamic_example"
  | "no_update"

export interface FailureInfo {
  domain: string
  taskType: string
  agentId: string
  episodeId?: string
  errorMessage: string
  actionHistory: string[]
  observation?: string
  toolsUsed: string[]
  successRate: number
}

export interface ReflectionOutput {
  reflectionId: string
  timestamp: string
  domain: string
  taskType: string
  agentId: string
  failureType: FailureType
  rootCause: string
  toolsInvolved: string[]
  errorPattern: string
  promptUpdateAction: PromptUpdateAction
  promptUpdateContent: string
  memoryUpdates: Array<{
    type: "lesson" | "error" | "action"
    content: string
    tags: string[]
  }>
  retryRecommendation: boolean
  confidence: number
}
