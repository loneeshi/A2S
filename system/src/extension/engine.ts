/**
 * DynamicExtensionEngine v3 — two-phase extension: rescue + optimize.
 *
 * Phase 1 (rescue): success rate < threshold
 *   - Detects capability gaps → creates new workers
 *   - Detects strategy gaps → creates new skills
 *
 * Phase 2 (optimize): success rate >= threshold
 *   - Detects step inefficiency → refines existing skills
 *   - Detects near-miss fragility → adds robustness tips
 *   - Detects inconsistent performance → stabilizes strategy
 *   - Detects bottleneck workers → creates targeted optimization skills
 *
 * Convergence guarantee:
 *   - Phase 1 can only ADD entities (monotonic capability growth)
 *   - Phase 2 can only REFINE existing entities (no structural regression)
 *   - Probation prevents bad extensions from persisting
 *   - Convergence checkpoints track trajectory
 */

import { AgentStore } from "../spec/store"
import { SkillManager } from "../skill/manager"
import type { LLMClient } from "../llm/client"
import type {
  ExtensionProposal,
  ExpansionTrigger,
  ExpansionRecord,
  ProbationTrial,
  ProbationConfig,
  LLMWorkerDesign,
  LLMSkillDesign,
  LLMSkillRefinement,
  ExtensionPhase,
  ConvergenceCheckpoint,
  StepStats,
} from "./types"
import { PerformanceMonitor } from "./monitor"
import { join } from "node:path"
import { writeFile, mkdir, readFile } from "node:fs/promises"
import matter from "gray-matter"

export interface ExtensionEngineOptions {
  baseDir: string
  monitor: PerformanceMonitor
  llm: LLMClient
  extensionThreshold?: number
  maxWorkers?: number
  probation?: Partial<ProbationConfig>
  /** Max steps per episode — used for near-miss detection */
  maxSteps?: number
}

export class DynamicExtensionEngine {
  private baseDir: string
  private monitor: PerformanceMonitor
  private llm: LLMClient
  private threshold: number
  private maxWorkers: number
  private probationConfig: ProbationConfig
  private maxSteps: number
  private extensionHistory: ExpansionRecord[] = []
  private appliedTriggers = new Set<string>()

  constructor(options: ExtensionEngineOptions) {
    this.baseDir = options.baseDir
    this.monitor = options.monitor
    this.llm = options.llm
    this.threshold = options.extensionThreshold ?? 0.7
    this.maxWorkers = options.maxWorkers ?? 15
    this.maxSteps = options.maxSteps ?? 25
    this.probationConfig = {
      minTrials: options.probation?.minTrials ?? 8,
      maxTrials: options.probation?.maxTrials ?? 20,
      earlyStopFailures: options.probation?.earlyStopFailures ?? 3,
      confidenceLevel: options.probation?.confidenceLevel ?? 0.9,
    }
  }

  async checkAndExtend(): Promise<ExtensionProposal[]> {
    if (!this.monitor.shouldExtend(this.threshold)) {
      return []
    }

    const globalPhase = this.monitor.getPhase(this.threshold)

    // Always check per-task-type rescue triggers regardless of global phase.
    // This prevents a high global rate from masking individual task types that
    // are struggling (e.g. "examine" at 38% while global is 78%).
    const rescueTriggers = this.detectRescueTriggers()
    const optimizationTriggers = globalPhase === "optimize"
      ? this.detectOptimizationTriggers()
      : []

    // Rescue triggers take priority, then optimization
    const allTriggers = [...rescueTriggers, ...optimizationTriggers]
    if (allTriggers.length === 0) return []

    const applied: ExtensionProposal[] = []
    const maxPerRound = 3

    for (const trigger of allTriggers.slice(0, maxPerRound)) {
      const triggerKey = `${trigger.type}:${trigger.gap.neededCapability}`
      if (this.appliedTriggers.has(triggerKey)) continue

      // Rescue triggers always use rescue phase for solution design;
      // optimization triggers use optimize phase
      const designPhase: ExtensionPhase = (
        trigger.type === "worker_capability_gap" || trigger.type === "skill_gap"
      ) ? "rescue" : "optimize"

      try {
        const proposal = await this.designSolution(trigger, designPhase)
        if (proposal) {
          await this.applyProposal(proposal)
          this.appliedTriggers.add(triggerKey)
          applied.push(proposal)
        }
      } catch (err) {
        console.error(`[extension] Failed to design solution for trigger: ${trigger.reason}`, err)
      }
    }

    return applied
  }

  getCurrentPhase(): ExtensionPhase {
    return this.monitor.getPhase(this.threshold)
  }

  // ─── Phase 1: Rescue triggers ─────────────────────────────────────

  private detectRescueTriggers(): ExpansionTrigger[] {
    const triggers: ExpansionTrigger[] = []
    const stats = this.monitor.getStats()

    const difficultTypes = this.monitor.getDifficultTaskTypes(0.5, 3)
    for (const taskType of difficultTypes) {
      const typeStats = stats.byTaskType[taskType]
      const failures = this.monitor.getRecentFailures(5)
        .filter((f) => f.taskType === taskType)

      triggers.push({
        type: "worker_capability_gap",
        reason: `Task type '${taskType}' has ${(typeStats.rate * 100).toFixed(0)}% success rate`,
        evidence: {
          failureCount: typeStats.total - typeStats.success,
          successRate: typeStats.rate,
          recentFailures: failures,
          taskType,
        },
        gap: {
          description: `Workers struggle with ${taskType} tasks`,
          currentCoverage: Object.keys(stats.byAgent),
          neededCapability: taskType,
        },
      })
    }

    const weakSubtasks = this.monitor.getWeakSubtasks(0.4, 3)
    for (const ws of weakSubtasks) {
      triggers.push({
        type: "skill_gap",
        reason: `${ws.workerId} fails at '${ws.subtaskType}' subtasks (${(ws.rate * 100).toFixed(0)}%)`,
        evidence: {
          failureCount: ws.total - Math.round(ws.rate * ws.total),
          successRate: ws.rate,
          recentFailures: [],
        },
        gap: {
          description: `${ws.workerId} has the right tools but wrong strategy for ${ws.subtaskType}`,
          currentCoverage: [ws.workerId],
          neededCapability: `${ws.subtaskType}_skill`,
        },
      })
    }

    return triggers.sort((a, b) => a.evidence.successRate - b.evidence.successRate)
  }

  // ─── Phase 2: Optimization triggers ───────────────────────────────

  private detectOptimizationTriggers(): ExpansionTrigger[] {
    return this.monitor.getOptimizationTriggers(this.maxSteps)
  }

  // ─── Solution design ──────────────────────────────────────────────

  private async designSolution(
    trigger: ExpansionTrigger,
    phase: ExtensionPhase,
  ): Promise<ExtensionProposal | null> {
    const currentTree = await this.describeCurrentTree()
    const toolLibrary = await this.describeToolLibrary()

    if (phase === "rescue") {
      if (trigger.type === "worker_capability_gap") {
        return this.designWorker(trigger, currentTree, toolLibrary)
      } else if (trigger.type === "skill_gap") {
        return this.designSkill(trigger, currentTree)
      }
    } else {
      // Optimize phase: refine existing skills
      return this.designSkillRefinement(trigger, currentTree)
    }

    return null
  }

  // ─── Rescue: design new worker ────────────────────────────────────

  private async designWorker(
    trigger: ExpansionTrigger,
    currentTree: string,
    toolLibrary: string,
  ): Promise<ExtensionProposal | null> {
    const failureSummary = trigger.evidence.recentFailures
      .map((f, i) => `${i + 1}. Task: ${f.metadata?.task ?? f.taskType}\n   Error: ${f.errorMessage ?? "timeout"}`)
      .join("\n")

    const prompt = `You are designing a new worker agent for a multi-agent system.

## Current Agent Tree
${currentTree}

## Available Tools
${toolLibrary}

## Problem
${trigger.reason}

## Recent Failures
${failureSummary || "No detailed failure logs available."}

## Capability Gap
${trigger.gap.description}
Current coverage: ${trigger.gap.currentCoverage.join(", ")}
Missing capability: ${trigger.gap.neededCapability}

## Your Task
Design a NEW worker agent that fills this gap. The new agent MUST be functionally different from existing workers — different tools subset, different prompt strategy, or different operational approach.

Output ONLY a JSON object:
{
  "id": "descriptive_snake_case",
  "role": "worker",
  "description": "What this worker does and WHY it differs from existing workers",
  "capabilities": ["cap1", "cap2"],
  "tools": ["tool_id_1", "tool_id_2"],
  "skills": [],
  "prompt_strategy": "Full prompt text for this worker (detailed, actionable, in English)",
  "mount_point": "parent_manager_id",
  "differentiation": "How this differs from existing workers"
}`

    const response = await this.llm.chat(
      [
        { role: "system", content: "You are an agent architecture designer. Output ONLY valid JSON, no markdown fences." },
        { role: "user", content: prompt },
      ],
      { temperature: 0.4 },
    )

    const design = this.parseJSON<LLMWorkerDesign>(response.content)
    if (!design || !design.id || !design.tools || !design.prompt_strategy) {
      console.warn(`[extension:rescue] designWorker parse failed for "${trigger.gap.neededCapability}". LLM response (first 500 chars): ${response.content.slice(0, 500)}`)
      return null
    }

    return {
      extensionType: "add_worker",
      reason: trigger.reason,
      priority: 1.0 - trigger.evidence.successRate,
      trigger,
      details: { design },
    }
  }

  // ─── Rescue: design new skill ─────────────────────────────────────

  private async designSkill(
    trigger: ExpansionTrigger,
    currentTree: string,
  ): Promise<ExtensionProposal | null> {
    const prompt = `You are writing a skill document for a multi-agent system.

## Context
${currentTree}

## Problem
${trigger.reason}

## Your Task
Design a skill that teaches the worker how to handle this situation better.
The skill should be practical and include concrete examples.

Output ONLY a JSON object:
{
  "id": "domain/skill_name",
  "type": "manual|knowledge|workflow",
  "for_worker": "worker_id",
  "description": "What this skill teaches",
  "content": "Full markdown content (use ## headers, bullet points, concrete examples)",
  "examples": "Optional markdown with worked examples showing the skill applied",
  "allowedTools": ["tool_ids the skill user should restrict to, or empty array"]
}`

    const response = await this.llm.chat(
      [
        { role: "system", content: "You are an agent skill designer. Output ONLY valid JSON, no markdown fences." },
        { role: "user", content: prompt },
      ],
      { temperature: 0.4 },
    )

    const design = this.parseJSON<LLMSkillDesign>(response.content)
    if (!design || !design.id || !design.content) {
      console.warn(`[extension:rescue] designSkill parse failed for "${trigger.gap.neededCapability}". LLM response (first 500 chars): ${response.content.slice(0, 500)}`)
      return null
    }

    return {
      extensionType: "add_skill",
      reason: trigger.reason,
      priority: (1.0 - trigger.evidence.successRate) * 0.8,
      trigger,
      details: { design },
    }
  }

  // ─── Optimize: refine existing skill ──────────────────────────────

  private async designSkillRefinement(
    trigger: ExpansionTrigger,
    currentTree: string,
  ): Promise<ExtensionProposal | null> {
    const taskType = trigger.evidence.taskType ?? trigger.gap.neededCapability
    const stepStats = trigger.evidence.stepStats

    // Find which skill currently covers this task type
    const skillManager = new SkillManager(join(this.baseDir, "skills"))
    const targetSkillId = await this.findRelevantSkill(taskType, skillManager)

    let existingSkillContent = ""
    if (targetSkillId) {
      const skill = await skillManager.get(targetSkillId)
      existingSkillContent = skill?.content ?? ""
    }

    const stepStatsStr = stepStats
      ? `\nStep statistics for successful ${taskType} tasks:\n  min=${stepStats.min}, p25=${stepStats.p25}, median=${stepStats.median}, mean=${stepStats.mean.toFixed(1)}, p75=${stepStats.p75}, max=${stepStats.max}, stddev=${stepStats.stddev.toFixed(1)}`
      : ""

    const bottleneckWorker = trigger.evidence.bottleneckWorker
    const bottleneckStr = bottleneckWorker
      ? `\nBottleneck worker: ${bottleneckWorker}`
      : ""

    const prompt = `You are refining an existing skill to improve efficiency in a multi-agent system.

## Current Agent Tree
${currentTree}

## Optimization Target
${trigger.reason}
${stepStatsStr}
${bottleneckStr}

## Trigger Type: ${trigger.type}
${trigger.gap.description}

## Current Skill${targetSkillId ? ` (${targetSkillId})` : ""}
${existingSkillContent || "(no existing skill found for this task type)"}

## Your Task
${trigger.type === "step_efficiency" ? `
The tasks succeed but take too many steps. Analyze the step distribution and write specific optimization advice:
- What patterns lead to high step counts?
- How can the agent be more direct/efficient?
- What search shortcuts or action batching would help?
` : ""}${trigger.type === "near_miss" ? `
Many tasks barely succeed (using >80% of max allowed steps). Write advice to make the strategy more robust:
- What causes the agent to take so many steps?
- What faster fallback strategies should it use when the primary approach is slow?
- At what point should the agent switch strategies?
` : ""}${trigger.type === "consistency_gap" ? `
The same task type has wildly different step counts. Write advice to stabilize the strategy:
- What causes some runs to be fast and others slow?
- What is the most reliable approach that works consistently?
- Should the agent use a fixed strategy rather than adaptive exploration?
` : ""}${trigger.type === "subtask_bottleneck" ? `
One worker (${bottleneckWorker}) is significantly slower than its peers. Write advice to speed it up:
- What is this worker doing that takes so long?
- What shortcuts or heuristics would speed it up?
- Should the task decomposition give this worker simpler sub-tasks?
` : ""}

Output ONLY a JSON object:
{
  "skill_id": "${targetSkillId ?? `alfworld/${taskType.replace(/[^a-z0-9_]/g, "_")}_optimization`}",
  "changes": "Full markdown content to ADD to the skill (new sections with ## headers)",
  "new_sections": "What sections you're adding and why",
  "removed_sections": [],
  "rationale": "Why these changes should improve efficiency"
}`

    const response = await this.llm.chat(
      [
        { role: "system", content: "You are an agent skill optimizer. Output ONLY valid JSON, no markdown fences." },
        { role: "user", content: prompt },
      ],
      { temperature: 0.4 },
    )

    const design = this.parseJSON<LLMSkillRefinement>(response.content)
    if (!design || !design.changes) {
      console.warn(`[extension:optimize] designSkillRefinement parse failed for "${trigger.gap.neededCapability}". LLM response (first 500 chars): ${response.content.slice(0, 500)}`)
      return null
    }

    return {
      extensionType: "refine_skill",
      reason: trigger.reason,
      priority: 0.5,
      trigger,
      details: {
        design,
        targetSkillId,
        stepStats,
      },
    }
  }

  private async findRelevantSkill(taskType: string, skillManager: SkillManager): Promise<string | null> {
    // Try exact match first
    const candidates = [
      `alfworld/${taskType}`,
      `alfworld/task_decomposition`,
      `alfworld/object_search_strategy`,
      `alfworld/object_handling`,
      `alfworld/appliance_operation`,
    ]

    for (const id of candidates) {
      const skill = await skillManager.get(id)
      if (skill) {
        const content = skill.content.toLowerCase()
        const type = taskType.replace(/_/g, " ").toLowerCase()
        if (content.includes(type) || id.includes(taskType)) {
          return id
        }
      }
    }

    // Fallback: task_decomposition always relevant for optimization
    const td = await skillManager.get("alfworld/task_decomposition")
    if (td) return "alfworld/task_decomposition"

    return null
  }

  // ─── Apply proposals ──────────────────────────────────────────────

  private async applyProposal(proposal: ExtensionProposal): Promise<string | null> {
    switch (proposal.extensionType) {
      case "add_worker":
        return this.applyWorkerDesign(proposal)
      case "add_skill":
        return this.applySkillDesign(proposal)
      case "refine_skill":
        return this.applySkillRefinement(proposal)
      default:
        return null
    }
  }

  private async applyWorkerDesign(proposal: ExtensionProposal): Promise<string> {
    const design = proposal.details.design as LLMWorkerDesign
    const agentId = design.id.replace(/[^a-z0-9_]/g, "_")

    const frontmatter = {
      id: agentId,
      name: agentId.split("_").map((s) => s.charAt(0).toUpperCase() + s.slice(1)).join(""),
      role: "worker",
      mode: "subagent",
      description: design.description,
      tools: { allow: design.tools, deny: [] },
      memory: { mode: "light", store: "jsonl", capacity: 200 },
      skills: design.skills ?? [],
      metadata: {
        domain: "alfworld",
        benchmark: "alfworld",
        capabilities: design.capabilities,
        generatedBy: "extension_engine_v3",
        mountPoint: design.mount_point,
        differentiation: design.differentiation,
        status: "probation",
        version: "0.1.0",
      },
    }

    const md = matter.stringify(design.prompt_strategy + "\n", frontmatter)
    const agentsDir = join(this.baseDir, "agents")
    await mkdir(agentsDir, { recursive: true })
    await writeFile(join(agentsDir, `${agentId}.md`), md, "utf-8")

    this.extensionHistory.push({
      id: `ext_${Date.now()}`,
      type: "worker",
      createdAt: new Date().toISOString(),
      trigger: proposal.trigger,
      entityId: agentId,
      performance: { tasksHandled: 0, successRate: 0, baselineRate: proposal.trigger.evidence.successRate },
      status: "probation",
    })

    console.log(`[extension:rescue] Created new worker: ${agentId} — ${design.differentiation}`)
    return agentId
  }

  private async applySkillDesign(proposal: ExtensionProposal): Promise<string> {
    const design = proposal.details.design as LLMSkillDesign
    const skillId = design.id

    const skillManager = new SkillManager(join(this.baseDir, "skills"))

    const hasExamples = design.examples && design.examples.trim().length > 0
    const hasToolRestriction = design.allowedTools && design.allowedTools.length > 0

    const validTypes = ["reference", "task", "workflow", "knowledge"] as const
    const skillType = validTypes.includes(design.type as any) ? design.type : "reference"

    const specInput = {
      id: skillId,
      description: design.description,
      type: skillType as typeof validTypes[number],
      whenToUse: `When handling tasks related to: ${proposal.trigger.gap.neededCapability}`,
      tags: [design.type, "auto-generated"],
      generatedBy: "extension" as const,
      allowedTools: hasToolRestriction ? design.allowedTools : undefined,
    }

    try {
      if (hasExamples) {
        const supportingFiles: Record<string, string> = {
          "examples.md": design.examples!,
        }
        const contentWithRef = design.content + "\n\nFor worked examples, see [examples.md](examples.md)."
        await skillManager.createDirectory(specInput, contentWithRef, supportingFiles)
      } else {
        await skillManager.create(specInput, design.content)
      }
    } catch (err) {
      console.warn(`[extension] Failed to create skill '${skillId}':`, err instanceof Error ? err.message : err)
      return ""
    }

    if (design.for_worker) {
      const agentStore = new AgentStore(join(this.baseDir, "agents"))
      const agent = await agentStore.get(design.for_worker)
      if (agent && !agent.spec.skills.includes(skillId)) {
        await agentStore.update(design.for_worker, {
          skills: [...agent.spec.skills, skillId],
        })
      }
    }

    this.extensionHistory.push({
      id: `ext_${Date.now()}`,
      type: "skill",
      createdAt: new Date().toISOString(),
      trigger: proposal.trigger,
      entityId: skillId,
      performance: { tasksHandled: 0, successRate: 0, baselineRate: proposal.trigger.evidence.successRate },
      status: "probation",
    })

    console.log(`[extension:rescue] Created new skill: ${skillId} for ${design.for_worker}`)
    return skillId
  }

  private async applySkillRefinement(proposal: ExtensionProposal): Promise<string> {
    const design = proposal.details.design as LLMSkillRefinement
    const targetSkillId = (proposal.details.targetSkillId as string) ?? design.skill_id
    const stepStats = proposal.details.stepStats as StepStats | undefined

    const skillManager = new SkillManager(join(this.baseDir, "skills"))
    const existing = await skillManager.get(targetSkillId)

    if (existing) {
      // Append optimization content to existing skill
      const refinementHeader = `\n\n## Optimization Notes (auto-generated ${new Date().toISOString().split("T")[0]})`
      const rationale = `\n\n> Trigger: ${proposal.trigger.type} — ${design.rationale}`
      const updatedContent = existing.content + refinementHeader + rationale + "\n\n" + design.changes

      await skillManager.update(targetSkillId, {}, updatedContent)

      console.log(`[extension:optimize] Refined skill: ${targetSkillId} — ${design.new_sections}`)
    } else {
      // Create new optimization skill
      const specInput = {
        id: design.skill_id,
        description: `Optimization guide: ${design.rationale}`,
        type: "reference" as const,
        whenToUse: `When ${proposal.trigger.gap.description}`,
        tags: ["optimization", "auto-generated"],
        generatedBy: "extension" as const,
      }

      await skillManager.create(specInput, design.changes)
      console.log(`[extension:optimize] Created optimization skill: ${design.skill_id}`)
    }

    // Inject skill into matching worker agents
    const finalSkillId = targetSkillId ?? design.skill_id
    const agentStore = new AgentStore(join(this.baseDir, "agents"))
    const agents = await agentStore.list()
    for (const agent of agents) {
      const agentDomain = agent.spec.metadata?.domain as string | undefined
      if (agentDomain !== "alfworld") continue
      if (agent.spec.role !== "worker") continue
      if (agent.spec.skills.includes(finalSkillId)) continue
      await agentStore.update(agent.spec.id, {
        skills: [...agent.spec.skills, finalSkillId],
      })
      console.log(`[extension:optimize] Injected ${finalSkillId} into ${agent.spec.id}`)
    }

    this.extensionHistory.push({
      id: `ext_${Date.now()}`,
      type: "skill_refinement",
      createdAt: new Date().toISOString(),
      trigger: proposal.trigger,
      entityId: targetSkillId ?? design.skill_id,
      performance: {
        tasksHandled: 0,
        successRate: proposal.trigger.evidence.successRate,
        baselineRate: proposal.trigger.evidence.successRate,
        baselineAvgSteps: stepStats?.mean,
      },
      status: "probation",
    })

    return targetSkillId ?? design.skill_id
  }

  // ─── Probation: sequential testing ─────────────────────────────────

  /**
   * Record a trial result for a probationary entity and evaluate whether
   * to promote, disable, or continue observing.
   *
   * Uses Wilson score confidence interval for sequential testing:
   * - Early-stop: consecutive failures ≥ threshold → DISABLE
   * - After minTrials: Wilson lower bound > baseline → PROMOTE
   * - After minTrials: Wilson upper bound < baseline → DISABLE
   * - After maxTrials: forced decision based on point estimate
   */
  updateProbation(entityId: string, success: boolean, taskType?: string, steps?: number): void {
    const record = this.extensionHistory.find(
      (r) => r.entityId === entityId && r.status === "probation",
    )
    if (!record) return

    // Initialize trial history if needed
    if (!record.trialHistory) record.trialHistory = []
    if (!record.evaluatedTaskTypes) record.evaluatedTaskTypes = []

    // Record the trial
    const trial: ProbationTrial = {
      success,
      taskType: taskType ?? "unknown",
      steps,
      timestamp: new Date().toISOString(),
    }
    record.trialHistory.push(trial)
    if (taskType && !record.evaluatedTaskTypes.includes(taskType)) {
      record.evaluatedTaskTypes.push(taskType)
    }

    // Update running stats
    record.performance.tasksHandled = record.trialHistory.length
    const successes = record.trialHistory.filter((t) => t.success).length
    record.performance.successRate = successes / record.trialHistory.length

    // Track step improvement for refinements
    if (record.type === "skill_refinement" && steps !== undefined) {
      const successfulSteps = record.trialHistory
        .filter((t) => t.success && t.steps !== undefined)
        .map((t) => t.steps!)
      if (successfulSteps.length > 0) {
        record.performance.currentAvgSteps =
          successfulSteps.reduce((a, b) => a + b, 0) / successfulSteps.length
      }
    }

    const n = record.trialHistory.length
    const cfg = this.probationConfig

    // ── Early-stop check: consecutive failures ──
    if (n >= cfg.earlyStopFailures) {
      const lastN = record.trialHistory.slice(-cfg.earlyStopFailures)
      const allFailed = lastN.every((t) => !t.success)
      if (allFailed) {
        record.status = "disabled"
        record.verdict = `Early-stop: ${cfg.earlyStopFailures} consecutive failures at trial ${n}`
        console.log(`[probation] ✗ DISABLED ${entityId}: ${record.verdict}`)
        return
      }
    }

    // Zero successes after 5+ trials — clearly not working
    if (n >= 5 && successes === 0) {
      record.status = "disabled"
      record.verdict = `0/${n} success rate — no evidence of capability`
      console.log(`[probation] ✗ DISABLED ${entityId}: ${record.verdict}`)
      return
    }

    // ── Not enough trials yet ──
    if (n < cfg.minTrials) return

    // ── Sequential test: Wilson score interval vs baseline ──
    const baseline = this.getMatchedBaseline(record)
    const { lower, upper } = this.wilsonInterval(successes, n, cfg.confidenceLevel)

    if (record.type === "skill_refinement") {
      // For refinements: rate must not drop AND steps should improve
      const rateOk = lower >= baseline - 0.1
      const stepsOk = !record.performance.baselineAvgSteps ||
        !record.performance.currentAvgSteps ||
        record.performance.currentAvgSteps <= record.performance.baselineAvgSteps * 1.05

      if (rateOk && stepsOk && n >= cfg.minTrials) {
        record.status = "active"
        record.verdict = `Refinement effective: rate=${this.pct(record.performance.successRate)} [${this.pct(lower)},${this.pct(upper)}] vs baseline ${this.pct(baseline)}, steps=${record.performance.currentAvgSteps?.toFixed(1) ?? "N/A"} (was ${record.performance.baselineAvgSteps?.toFixed(1) ?? "N/A"})`
        console.log(`[probation] ✓ PROMOTED ${entityId}: ${record.verdict}`)
        return
      }

      if (upper < baseline - 0.1) {
        record.status = "disabled"
        record.verdict = `Refinement harmful: rate=${this.pct(record.performance.successRate)} [${this.pct(lower)},${this.pct(upper)}] vs baseline ${this.pct(baseline)}`
        console.log(`[probation] ✗ DISABLED ${entityId}: ${record.verdict}`)
        return
      }
    } else {
      // For new workers/skills: must beat baseline
      if (lower > baseline) {
        record.status = "active"
        record.verdict = `Significantly better: ${this.pct(record.performance.successRate)} [${this.pct(lower)},${this.pct(upper)}] > baseline ${this.pct(baseline)} after ${n} trials`
        console.log(`[probation] ✓ PROMOTED ${entityId}: ${record.verdict}`)
        return
      }

      if (upper < baseline) {
        record.status = "disabled"
        record.verdict = `Significantly worse: ${this.pct(record.performance.successRate)} [${this.pct(lower)},${this.pct(upper)}] < baseline ${this.pct(baseline)} after ${n} trials`
        console.log(`[probation] ✗ DISABLED ${entityId}: ${record.verdict}`)
        return
      }
    }

    // ── Max trials reached: forced decision ──
    if (n >= cfg.maxTrials) {
      if (record.performance.successRate >= baseline) {
        record.status = "active"
        record.verdict = `Max trials (${n}): rate ${this.pct(record.performance.successRate)} ≥ baseline ${this.pct(baseline)}, promoting on trend`
        console.log(`[probation] ✓ PROMOTED ${entityId}: ${record.verdict}`)
      } else {
        record.status = "disabled"
        record.verdict = `Max trials (${n}): rate ${this.pct(record.performance.successRate)} < baseline ${this.pct(baseline)}, insufficient improvement`
        console.log(`[probation] ✗ DISABLED ${entityId}: ${record.verdict}`)
      }
      return
    }

    // ── Continue observing ──
    if (n % 5 === 0) {
      console.log(`[probation] … ${entityId}: ${successes}/${n} (${this.pct(record.performance.successRate)}) CI [${this.pct(lower)},${this.pct(upper)}] vs baseline ${this.pct(baseline)} — continuing`)
    }
  }

  /**
   * Get baseline success rate matched to the same task types the entity was evaluated on.
   * Falls back to global baseline if no matched data.
   */
  private getMatchedBaseline(record: ExpansionRecord): number {
    const stats = this.monitor.getStats()
    const taskTypes = record.evaluatedTaskTypes ?? []

    if (taskTypes.length === 0) {
      return record.performance.baselineRate
    }

    // Compute weighted average baseline across matched task types
    let totalTasks = 0
    let totalSuccesses = 0
    for (const tt of taskTypes) {
      const ts = stats.byTaskType[tt]
      if (ts) {
        totalTasks += ts.total
        totalSuccesses += ts.success
      }
    }

    if (totalTasks === 0) return record.performance.baselineRate
    return totalSuccesses / totalTasks
  }

  /**
   * Wilson score confidence interval for binomial proportion.
   *
   * More accurate than normal approximation for small samples.
   * z = 1.645 for 90% CI, 1.96 for 95% CI, 1.28 for 80% CI.
   */
  private wilsonInterval(
    successes: number,
    n: number,
    confidence: number,
  ): { lower: number; upper: number } {
    if (n === 0) return { lower: 0, upper: 1 }

    const z = this.zScore(confidence)
    const p = successes / n
    const z2 = z * z

    const denominator = 1 + z2 / n
    const center = (p + z2 / (2 * n)) / denominator
    const halfWidth = (z * Math.sqrt((p * (1 - p) + z2 / (4 * n)) / n)) / denominator

    return {
      lower: Math.max(0, center - halfWidth),
      upper: Math.min(1, center + halfWidth),
    }
  }

  /**
   * Approximate z-score for given confidence level.
   */
  private zScore(confidence: number): number {
    // Common z-scores lookup
    if (confidence >= 0.99) return 2.576
    if (confidence >= 0.95) return 1.96
    if (confidence >= 0.9) return 1.645
    if (confidence >= 0.85) return 1.44
    if (confidence >= 0.8) return 1.28
    return 1.0
  }

  private pct(v: number): string {
    return `${(v * 100).toFixed(0)}%`
  }

  // ─── Accessors ────────────────────────────────────────────────────

  getHistory(): ExpansionRecord[] {
    return [...this.extensionHistory]
  }

  getProbationEntities(): ExpansionRecord[] {
    return this.extensionHistory.filter((r) => r.status === "probation")
  }

  setMaxSteps(maxSteps: number): void {
    this.maxSteps = maxSteps
  }

  // ─── Internal helpers ─────────────────────────────────────────────

  private async describeCurrentTree(): Promise<string> {
    const store = new AgentStore(join(this.baseDir, "agents"))
    const agents = await store.list()
    const lines: string[] = []

    for (const agent of agents) {
      const meta = agent.spec.metadata as Record<string, unknown> | undefined
      const caps = (meta?.capabilities as string[])?.join(", ") ?? "general"
      const tools = agent.spec.tools.allow.join(", ")
      const skills = agent.spec.skills.join(", ") || "none"
      lines.push(`- ${agent.spec.id} (${agent.spec.role}): ${agent.spec.description ?? ""}`)
      lines.push(`  tools: [${tools}], skills: [${skills}], capabilities: [${caps}]`)
    }

    return lines.join("\n")
  }

  private async describeToolLibrary(): Promise<string> {
    const toolsDir = join(this.baseDir, "tools")
    const { readdir } = await import("node:fs/promises")
    const lines: string[] = []

    try {
      const files = await readdir(toolsDir)
      for (const file of files.filter((f) => f.endsWith(".json"))) {
        try {
          const content = await readFile(join(toolsDir, file), "utf-8")
          const tool = JSON.parse(content)
          lines.push(`- ${tool.id}: ${tool.description ?? ""}`)
        } catch { /* skip malformed */ }
      }
    } catch { /* no tools dir */ }

    return lines.join("\n")
  }

  private parseJSON<T>(text: string): T | null {
    let raw = text.trim()
    if (raw.startsWith("```")) {
      const lines = raw.split("\n")
      raw = lines.slice(1, -1).join("\n")
    }
    try {
      return JSON.parse(raw) as T
    } catch {
      const match = raw.match(/\{[\s\S]*\}/)
      if (match) {
        try {
          return JSON.parse(match[0]) as T
        } catch { /* ignore */ }
      }
      return null
    }
  }
}
