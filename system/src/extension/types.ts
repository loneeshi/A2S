/**
 * Extension types — proposals for dynamically extending the agent tree.
 *
 * v2: Added subtask tracking, LLM-designed expansion, probation system.
 * v3: Added optimization triggers, step tracking, efficiency metrics,
 *     staged expansion (rescue → optimize), convergence tracking.
 */

export type ExtensionType =
  | "add_worker"
  | "add_skill"
  | "refine_skill"
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
  /** Total tool calls (env actions) in this episode */
  steps?: number
  /** Number of delegate calls from manager */
  delegateCalls?: number
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
  /** How many tool calls this subtask took */
  steps?: number
}

// ─── Performance Stats ──────────────────────────────────────────────

export interface TypeStats {
  total: number
  success: number
  rate: number
}

export interface TypeStatsWithEfficiency extends TypeStats {
  /** Step counts for successful tasks only */
  stepStats: StepStats
}

export interface StepStats {
  /** Number of successful tasks with step data */
  count: number
  /** Minimum steps among successes */
  min: number
  /** Maximum steps among successes */
  max: number
  /** Mean steps */
  mean: number
  /** Median steps */
  median: number
  /** 25th percentile */
  p25: number
  /** 75th percentile */
  p75: number
  /** Standard deviation */
  stddev: number
}

export interface PerformanceStats {
  totalTasks: number
  successCount: number
  failureCount: number
  successRate: number
  byTaskType: Record<string, TypeStatsWithEfficiency>
  byAgent: Record<string, TypeStats>
  bySubtask: Record<string, TypeStats>
  failurePatterns: Record<string, number>
}

// ─── Expansion Triggers ─────────────────────────────────────────────

export type TriggerType =
  | "worker_capability_gap"      // success rate too low → need new worker
  | "skill_gap"                  // worker has tools but wrong strategy → need new skill
  | "step_efficiency"            // tasks succeed but take too many steps → refine skill
  | "near_miss"                  // tasks barely succeed (use >80% of max steps) → refine strategy
  | "consistency_gap"            // high variance in steps for same task type → stabilize strategy
  | "subtask_bottleneck"         // one worker is the weak link → refine that worker's skill
  | "composite_tool_need"        // repeated tool sequences → create composite tool

export interface ExpansionTrigger {
  type: TriggerType
  reason: string
  evidence: {
    failureCount: number
    successRate: number
    recentFailures: TaskResult[]
    /** For optimization triggers */
    stepStats?: StepStats
    /** Which task type this trigger is about */
    taskType?: string
    /** Which worker is the bottleneck */
    bottleneckWorker?: string
  }
  gap: {
    description: string
    currentCoverage: string[]
    neededCapability: string
  }
}

// ─── Extension Phase ────────────────────────────────────────────────

/**
 * The extension engine operates in two phases:
 *
 * Phase 1 (rescue): success rate < threshold
 *   - Creates new workers for capability gaps
 *   - Creates new skills for strategy gaps
 *   - Goal: get success rate above threshold
 *
 * Phase 2 (optimize): success rate >= threshold
 *   - Refines existing skills for efficiency
 *   - Stabilizes inconsistent strategies
 *   - Goal: reduce step count and variance
 */
export type ExtensionPhase = "rescue" | "optimize"

// ─── Convergence Tracking ───────────────────────────────────────────

/**
 * Tracks the system's evolution trajectory over time.
 * Used to verify the system is converging toward a better state.
 */
export interface ConvergenceCheckpoint {
  timestamp: string
  episode: number
  phase: ExtensionPhase
  metrics: {
    successRate: number
    avgSteps: number
    medianSteps: number
    /** How many task types are above rescue threshold */
    typesAboveThreshold: number
    totalTypes: number
  }
  /** What changed at this checkpoint */
  changes: Array<{
    type: "agent_added" | "skill_added" | "skill_refined" | "agent_disabled"
    entityId: string
    reason: string
  }>
}

// ─── LLM Design Outputs ────────────────────────────────────────────

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

export interface LLMSkillRefinement {
  skill_id: string
  changes: string
  new_sections: string
  removed_sections: string[]
  rationale: string
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
  type: "worker" | "skill" | "skill_refinement" | "composite_tool"
  createdAt: string
  trigger: ExpansionTrigger
  entityId: string
  performance: {
    tasksHandled: number
    successRate: number
    baselineRate: number
    /** For optimization records: baseline avg steps before refinement */
    baselineAvgSteps?: number
    /** Current avg steps after refinement */
    currentAvgSteps?: number
  }
  status: "probation" | "active" | "disabled"
  /** Full trial history for sequential testing */
  trialHistory?: ProbationTrial[]
  /** Which task types this entity was evaluated on */
  evaluatedTaskTypes?: string[]
  /** Reason for final decision */
  verdict?: string
}

export interface ProbationTrial {
  success: boolean
  taskType: string
  steps?: number
  timestamp: string
}

// ─── Probation Config ───────────────────────────────────────────────

export interface ProbationConfig {
  /** Minimum trials before considering promotion (default: 8) */
  minTrials: number
  /** Maximum trials before forced decision (default: 20) */
  maxTrials: number
  /** Consecutive failures to trigger early-stop (default: 3) */
  earlyStopFailures: number
  /** Confidence level for Wilson interval (default: 0.9) */
  confidenceLevel: number
}
