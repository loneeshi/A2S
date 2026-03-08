/**
 * Extension types — proposals for dynamically extending the agent tree.
 *
 * v2: Added subtask tracking, LLM-designed expansion, probation system.
 */

export type ExtensionType =
  | "add_worker"
  | "add_skill"
  | "add_composite_tool"

export interface ExtensionProposal {
  extensionType: ExtensionType
  reason: string
  priority: number
  trigger: ExpansionTrigger
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

export interface SubtaskResult {
  taskId: string
  subtaskIndex: number
  subtaskType: string
  workerId: string
  success: boolean
  toolCalls: Array<{ tool: string; args: Record<string, unknown>; result: string }>
  errorMessage?: string
  timestamp?: number
}

export interface PerformanceStats {
  totalTasks: number
  successCount: number
  failureCount: number
  successRate: number
  byTaskType: Record<string, { total: number; success: number; rate: number }>
  byAgent: Record<string, { total: number; success: number; rate: number }>
  bySubtask: Record<string, { total: number; success: number; rate: number }>
  failurePatterns: Record<string, number>
}

export interface ExpansionTrigger {
  type: "worker_capability_gap" | "skill_gap" | "composite_tool_need"
  reason: string
  evidence: {
    failureCount: number
    successRate: number
    recentFailures: TaskResult[]
  }
  gap: {
    description: string
    currentCoverage: string[]
    neededCapability: string
  }
}

export interface LLMWorkerDesign {
  id: string
  role: "worker"
  description: string
  capabilities: string[]
  tools: string[]
  skills: string[]
  prompt_strategy: string
  mount_point: string
  differentiation: string
}

export interface LLMSkillDesign {
  id: string
  type: "manual" | "knowledge" | "workflow"
  for_worker: string
  description: string
  content: string
  examples?: string
  allowedTools?: string[]
}

export interface LLMCompositeToolDesign {
  id: string
  description: string
  parameters: Record<string, { type: string; description: string; required: boolean }>
  steps: Array<{ tool: string; args_template: Record<string, string> }>
  for_workers: string[]
}

export interface ExpansionRecord {
  id: string
  type: "worker" | "skill" | "composite_tool"
  createdAt: string
  trigger: ExpansionTrigger
  entityId: string
  performance: {
    tasksHandled: number
    successRate: number
    baselineRate: number
  }
  status: "probation" | "active" | "disabled"
}
