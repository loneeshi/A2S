/**
 * Extension types — proposals for dynamically extending the agent tree.
 */

export type ExtensionType =
  | "add_worker"
  | "add_tool_to_worker"
  | "specialize_worker"
  | "add_manager"
  | "replicate_worker"

export interface ExtensionProposal {
  extensionType: ExtensionType
  reason: string
  priority: number
  details: Record<string, unknown>
}

export interface TaskResult {
  taskId: string
  taskType: string
  agentUsed: string
  success: boolean
  errorMessage?: string
  durationMs?: number
  metadata?: Record<string, unknown>
}

export interface PerformanceStats {
  totalTasks: number
  successCount: number
  failureCount: number
  successRate: number
  byTaskType: Record<string, { total: number; success: number; rate: number }>
  byAgent: Record<string, { total: number; success: number; rate: number }>
}
