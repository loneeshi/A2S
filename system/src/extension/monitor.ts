/**
 * PerformanceMonitor v3 — tracks task results with step-level efficiency metrics.
 *
 * v3 additions:
 *   - Step count tracking for successful tasks
 *   - Per-task-type step statistics (min, max, mean, median, p25, p75, stddev)
 *   - Optimization trigger detection:
 *     • step_efficiency: avg steps >> best performance
 *     • near_miss: tasks succeed but use >80% of max allowed steps
 *     • consistency_gap: high step variance within same task type
 *     • subtask_bottleneck: one worker consistently slower
 *   - Convergence checkpoint generation
 */

import type {
  TaskResult,
  SubtaskResult,
  PerformanceStats,
  StepStats,
  TypeStatsWithEfficiency,
  ExpansionTrigger,
  ConvergenceCheckpoint,
  ExtensionPhase,
} from "./types"

export class PerformanceMonitor {
  private history: TaskResult[] = []
  private subtaskHistory: SubtaskResult[] = []
  private failurePatterns = new Map<string, number>()
  private checkpoints: ConvergenceCheckpoint[] = []
  private maxHistory = 1000

  record(result: TaskResult): void {
    this.history.push(result)
    if (this.history.length > this.maxHistory) {
      this.history = this.history.slice(-this.maxHistory)
    }

    if (!result.success && result.errorMessage) {
      const pattern = this.classifyFailure(result.errorMessage)
      this.failurePatterns.set(pattern, (this.failurePatterns.get(pattern) ?? 0) + 1)
    }
  }

  recordSubtask(result: SubtaskResult): void {
    result.timestamp = result.timestamp ?? Date.now()
    if (result.steps === undefined && result.toolCalls) {
      result.steps = result.toolCalls.length
    }
    this.subtaskHistory.push(result)
    if (this.subtaskHistory.length > this.maxHistory * 3) {
      this.subtaskHistory = this.subtaskHistory.slice(-this.maxHistory * 3)
    }
  }

  getStats(): PerformanceStats {
    const total = this.history.length
    const successCount = this.history.filter((r) => r.success).length
    const failureCount = total - successCount

    const byTaskType: Record<string, TypeStatsWithEfficiency> = {}
    const byAgent: PerformanceStats["byAgent"] = {}

    // Group results by taskType
    const taskTypeGroups = new Map<string, TaskResult[]>()
    for (const r of this.history) {
      const group = taskTypeGroups.get(r.taskType) ?? []
      group.push(r)
      taskTypeGroups.set(r.taskType, group)

      if (!byAgent[r.agentUsed]) {
        byAgent[r.agentUsed] = { total: 0, success: 0, rate: 0 }
      }
      byAgent[r.agentUsed].total++
      if (r.success) byAgent[r.agentUsed].success++
    }

    for (const [taskType, results] of taskTypeGroups) {
      const t = results.length
      const s = results.filter((r) => r.success).length
      const successfulSteps = results
        .filter((r) => r.success && r.steps !== undefined)
        .map((r) => r.steps!)

      byTaskType[taskType] = {
        total: t,
        success: s,
        rate: t > 0 ? s / t : 0,
        stepStats: this.computeStepStats(successfulSteps),
      }
    }

    for (const v of Object.values(byAgent)) {
      v.rate = v.total > 0 ? v.success / v.total : 0
    }

    const bySubtask: PerformanceStats["bySubtask"] = {}
    for (const r of this.subtaskHistory) {
      const key = `${r.workerId}:${r.subtaskType}`
      if (!bySubtask[key]) {
        bySubtask[key] = { total: 0, success: 0, rate: 0 }
      }
      bySubtask[key].total++
      if (r.success) bySubtask[key].success++
    }
    for (const v of Object.values(bySubtask)) {
      v.rate = v.total > 0 ? v.success / v.total : 0
    }

    return {
      totalTasks: total,
      successCount,
      failureCount,
      successRate: total > 0 ? successCount / total : 0,
      byTaskType,
      byAgent,
      bySubtask,
      failurePatterns: Object.fromEntries(this.failurePatterns),
    }
  }

  // ─── Phase determination ──────────────────────────────────────────

  getPhase(threshold = 0.7): ExtensionPhase {
    if (this.history.length < 5) return "rescue"
    const stats = this.getStats()
    return stats.successRate < threshold ? "rescue" : "optimize"
  }

  /**
   * Original method: should the system try to extend?
   * In v3, this always returns true — the *type* of extension depends on the phase.
   */
  shouldExtend(threshold = 0.7): boolean {
    if (this.history.length < 5) return false
    // v3: always allow extension — phase determines what kind
    return true
  }

  // ─── Rescue-phase triggers (existing) ─────────────────────────────

  getDifficultTaskTypes(threshold = 0.5, minTasks = 3): string[] {
    const stats = this.getStats()
    return Object.entries(stats.byTaskType)
      .filter(([, v]) => v.total >= minTasks && v.rate < threshold)
      .map(([k]) => k)
  }

  getWeakSubtasks(threshold = 0.4, minAttempts = 3): Array<{
    key: string; workerId: string; subtaskType: string; rate: number; total: number
  }> {
    const stats = this.getStats()
    return Object.entries(stats.bySubtask)
      .filter(([, v]) => v.total >= minAttempts && v.rate < threshold)
      .map(([key, v]) => {
        const [workerId, subtaskType] = key.split(":")
        return { key, workerId, subtaskType, rate: v.rate, total: v.total }
      })
      .sort((a, b) => a.rate - b.rate)
  }

  // ─── Optimize-phase triggers (new in v3) ──────────────────────────

  /**
   * Detect task types where successful tasks take significantly more steps
   * than necessary. Trigger: p75 > 2 × p25 AND mean > threshold.
   */
  getInefficientTaskTypes(
    minSuccesses = 5,
    stepThreshold = 15,
  ): Array<{ taskType: string; stepStats: StepStats; reason: string }> {
    const stats = this.getStats()
    const results: Array<{ taskType: string; stepStats: StepStats; reason: string }> = []

    for (const [taskType, ts] of Object.entries(stats.byTaskType)) {
      const ss = ts.stepStats
      if (ss.count < minSuccesses) continue

      // High spread: p75 is more than 2× p25
      if (ss.p25 > 0 && ss.p75 > 2 * ss.p25) {
        results.push({
          taskType,
          stepStats: ss,
          reason: `Step spread too wide: p25=${ss.p25}, p75=${ss.p75} (${(ss.p75 / ss.p25).toFixed(1)}× ratio)`,
        })
        continue
      }

      // Mean steps too high relative to best performance
      if (ss.mean > stepThreshold && ss.min > 0 && ss.mean > 2 * ss.min) {
        results.push({
          taskType,
          stepStats: ss,
          reason: `Mean steps (${ss.mean.toFixed(1)}) >> best (${ss.min}): ${(ss.mean / ss.min).toFixed(1)}× ratio`,
        })
      }
    }

    return results
  }

  /**
   * Detect tasks that barely succeed — use >80% of max allowed steps.
   * These tasks are at risk of becoming failures if conditions change.
   */
  getNearMissTasks(
    maxSteps: number,
    nearMissRatio = 0.8,
    minTasks = 3,
  ): Array<{ taskType: string; nearMissCount: number; totalSuccess: number; ratio: number }> {
    const results: Array<{ taskType: string; nearMissCount: number; totalSuccess: number; ratio: number }> = []
    const nearMissThreshold = maxSteps * nearMissRatio

    const byType = new Map<string, { nearMiss: number; success: number }>()
    for (const r of this.history) {
      if (!r.success) continue
      const entry = byType.get(r.taskType) ?? { nearMiss: 0, success: 0 }
      entry.success++
      if (r.steps !== undefined && r.steps >= nearMissThreshold) {
        entry.nearMiss++
      }
      byType.set(r.taskType, entry)
    }

    for (const [taskType, data] of byType) {
      if (data.success < minTasks) continue
      const ratio = data.nearMiss / data.success
      if (ratio >= 0.3) {
        results.push({
          taskType,
          nearMissCount: data.nearMiss,
          totalSuccess: data.success,
          ratio,
        })
      }
    }

    return results.sort((a, b) => b.ratio - a.ratio)
  }

  /**
   * Detect task types with high step variance — inconsistent strategy.
   * Trigger: coefficient of variation (stddev/mean) > cvThreshold.
   */
  getInconsistentTaskTypes(
    minSuccesses = 5,
    cvThreshold = 0.5,
  ): Array<{ taskType: string; stepStats: StepStats; cv: number }> {
    const stats = this.getStats()
    const results: Array<{ taskType: string; stepStats: StepStats; cv: number }> = []

    for (const [taskType, ts] of Object.entries(stats.byTaskType)) {
      const ss = ts.stepStats
      if (ss.count < minSuccesses || ss.mean === 0) continue

      const cv = ss.stddev / ss.mean
      if (cv > cvThreshold) {
        results.push({ taskType, stepStats: ss, cv })
      }
    }

    return results.sort((a, b) => b.cv - a.cv)
  }

  /**
   * Detect worker bottlenecks — workers that are called often but have
   * significantly higher step counts than their peers.
   */
  getSubtaskBottlenecks(
    minAttempts = 5,
  ): Array<{ workerId: string; avgSteps: number; peerAvg: number; ratio: number }> {
    const workerSteps = new Map<string, number[]>()

    for (const r of this.subtaskHistory) {
      if (!r.success || r.steps === undefined) continue
      const steps = workerSteps.get(r.workerId) ?? []
      steps.push(r.steps)
      workerSteps.set(r.workerId, steps)
    }

    const workerAvgs: Array<{ workerId: string; avg: number; count: number }> = []
    for (const [workerId, steps] of workerSteps) {
      if (steps.length < minAttempts) continue
      const avg = steps.reduce((a, b) => a + b, 0) / steps.length
      workerAvgs.push({ workerId, avg, count: steps.length })
    }

    if (workerAvgs.length < 2) return []

    const overallAvg = workerAvgs.reduce((s, w) => s + w.avg * w.count, 0) /
      workerAvgs.reduce((s, w) => s + w.count, 0)

    return workerAvgs
      .filter((w) => w.avg > overallAvg * 1.5)
      .map((w) => ({
        workerId: w.workerId,
        avgSteps: w.avg,
        peerAvg: overallAvg,
        ratio: w.avg / overallAvg,
      }))
      .sort((a, b) => b.ratio - a.ratio)
  }

  // ─── Optimization triggers (assembled) ────────────────────────────

  /**
   * Collect all optimization-phase triggers.
   * Called when the system is in "optimize" phase (success rate above threshold).
   */
  getOptimizationTriggers(maxSteps: number): ExpansionTrigger[] {
    const triggers: ExpansionTrigger[] = []
    const stats = this.getStats()

    // 1. Step efficiency
    for (const eff of this.getInefficientTaskTypes()) {
      triggers.push({
        type: "step_efficiency",
        reason: eff.reason,
        evidence: {
          failureCount: 0,
          successRate: stats.byTaskType[eff.taskType]?.rate ?? 1,
          recentFailures: [],
          stepStats: eff.stepStats,
          taskType: eff.taskType,
        },
        gap: {
          description: `${eff.taskType} tasks succeed but use too many steps (mean: ${eff.stepStats.mean.toFixed(1)}, best: ${eff.stepStats.min})`,
          currentCoverage: Object.keys(stats.byAgent),
          neededCapability: `${eff.taskType}_efficiency`,
        },
      })
    }

    // 2. Near-miss detection
    for (const nm of this.getNearMissTasks(maxSteps)) {
      triggers.push({
        type: "near_miss",
        reason: `${nm.nearMissCount}/${nm.totalSuccess} successful ${nm.taskType} tasks used >80% of max steps — fragile`,
        evidence: {
          failureCount: 0,
          successRate: stats.byTaskType[nm.taskType]?.rate ?? 1,
          recentFailures: [],
          stepStats: stats.byTaskType[nm.taskType]?.stepStats,
          taskType: nm.taskType,
        },
        gap: {
          description: `${nm.taskType} tasks are fragile — ${(nm.ratio * 100).toFixed(0)}% barely succeed`,
          currentCoverage: Object.keys(stats.byAgent),
          neededCapability: `${nm.taskType}_robustness`,
        },
      })
    }

    // 3. Consistency gap
    for (const ic of this.getInconsistentTaskTypes()) {
      triggers.push({
        type: "consistency_gap",
        reason: `${ic.taskType} has high step variance (CV=${ic.cv.toFixed(2)}, stddev=${ic.stepStats.stddev.toFixed(1)}, mean=${ic.stepStats.mean.toFixed(1)})`,
        evidence: {
          failureCount: 0,
          successRate: stats.byTaskType[ic.taskType]?.rate ?? 1,
          recentFailures: [],
          stepStats: ic.stepStats,
          taskType: ic.taskType,
        },
        gap: {
          description: `${ic.taskType} strategy is inconsistent — step count varies widely`,
          currentCoverage: Object.keys(stats.byAgent),
          neededCapability: `${ic.taskType}_consistency`,
        },
      })
    }

    // 4. Subtask bottleneck
    for (const bn of this.getSubtaskBottlenecks()) {
      triggers.push({
        type: "subtask_bottleneck",
        reason: `${bn.workerId} takes ${bn.avgSteps.toFixed(1)} steps avg vs peer avg ${bn.peerAvg.toFixed(1)} (${bn.ratio.toFixed(1)}×)`,
        evidence: {
          failureCount: 0,
          successRate: 1,
          recentFailures: [],
          bottleneckWorker: bn.workerId,
        },
        gap: {
          description: `${bn.workerId} is the bottleneck — ${bn.ratio.toFixed(1)}× slower than peers`,
          currentCoverage: [bn.workerId],
          neededCapability: `${bn.workerId}_efficiency`,
        },
      })
    }

    return triggers
  }

  // ─── Convergence tracking ─────────────────────────────────────────

  createCheckpoint(
    episode: number,
    threshold: number,
    changes: ConvergenceCheckpoint["changes"] = [],
  ): ConvergenceCheckpoint {
    const stats = this.getStats()
    const successfulWithSteps = this.history.filter((r) => r.success && r.steps !== undefined)
    const allSteps = successfulWithSteps.map((r) => r.steps!)
    const typesAboveThreshold = Object.values(stats.byTaskType)
      .filter((t) => t.total >= 3 && t.rate >= threshold).length

    const cp: ConvergenceCheckpoint = {
      timestamp: new Date().toISOString(),
      episode,
      phase: this.getPhase(threshold),
      metrics: {
        successRate: stats.successRate,
        avgSteps: allSteps.length > 0 ? allSteps.reduce((a, b) => a + b, 0) / allSteps.length : 0,
        medianSteps: allSteps.length > 0 ? this.percentile(allSteps.sort((a, b) => a - b), 50) : 0,
        typesAboveThreshold,
        totalTypes: Object.keys(stats.byTaskType).length,
      },
      changes,
    }

    this.checkpoints.push(cp)
    return cp
  }

  getCheckpoints(): ConvergenceCheckpoint[] {
    return [...this.checkpoints]
  }

  /**
   * Check if the system is converging: success rate trending up
   * AND/OR step count trending down over recent checkpoints.
   */
  isConverging(windowSize = 3): { converging: boolean; reason: string } {
    if (this.checkpoints.length < windowSize) {
      return { converging: true, reason: "Not enough data yet" }
    }

    const recent = this.checkpoints.slice(-windowSize)
    const first = recent[0]
    const last = recent[recent.length - 1]

    const rateImproving = last.metrics.successRate >= first.metrics.successRate
    const stepsImproving = last.metrics.avgSteps <= first.metrics.avgSteps || last.metrics.avgSteps === 0

    if (rateImproving && stepsImproving) {
      return { converging: true, reason: `Success rate: ${(first.metrics.successRate * 100).toFixed(0)}% → ${(last.metrics.successRate * 100).toFixed(0)}%, steps: ${first.metrics.avgSteps.toFixed(1)} → ${last.metrics.avgSteps.toFixed(1)}` }
    }

    if (rateImproving) {
      return { converging: true, reason: `Success rate improving: ${(first.metrics.successRate * 100).toFixed(0)}% → ${(last.metrics.successRate * 100).toFixed(0)}% (steps slightly up)` }
    }

    return { converging: false, reason: `Success rate stalled/declining: ${(first.metrics.successRate * 100).toFixed(0)}% → ${(last.metrics.successRate * 100).toFixed(0)}%` }
  }

  // ─── Existing helpers ─────────────────────────────────────────────

  getRecentFailures(n = 10): TaskResult[] {
    return this.history.filter((r) => !r.success).slice(-n)
  }

  getSubtaskFailures(workerId?: string, n = 10): SubtaskResult[] {
    let results = this.subtaskHistory.filter((r) => !r.success)
    if (workerId) results = results.filter((r) => r.workerId === workerId)
    return results.slice(-n)
  }

  getWorkersSince(since: number): Array<{ workerId: string; success: boolean }> {
    return this.subtaskHistory
      .filter((r) => (r.timestamp ?? 0) >= since)
      .map((r) => ({ workerId: r.workerId, success: r.success }))
  }

  getUnderperformingAgents(threshold = 0.7, minTasks = 3): string[] {
    const stats = this.getStats()
    return Object.entries(stats.byAgent)
      .filter(([, v]) => v.total >= minTasks && v.rate < threshold)
      .map(([k]) => k)
  }

  clear(): void {
    this.history = []
    this.subtaskHistory = []
    this.failurePatterns.clear()
    this.checkpoints = []
  }

  // ─── Internal ─────────────────────────────────────────────────────

  private computeStepStats(steps: number[]): StepStats {
    if (steps.length === 0) {
      return { count: 0, min: 0, max: 0, mean: 0, median: 0, p25: 0, p75: 0, stddev: 0 }
    }

    const sorted = [...steps].sort((a, b) => a - b)
    const n = sorted.length
    const sum = sorted.reduce((a, b) => a + b, 0)
    const mean = sum / n

    const variance = sorted.reduce((s, v) => s + (v - mean) ** 2, 0) / n
    const stddev = Math.sqrt(variance)

    return {
      count: n,
      min: sorted[0],
      max: sorted[n - 1],
      mean,
      median: this.percentile(sorted, 50),
      p25: this.percentile(sorted, 25),
      p75: this.percentile(sorted, 75),
      stddev,
    }
  }

  private percentile(sorted: number[], p: number): number {
    if (sorted.length === 0) return 0
    const idx = (p / 100) * (sorted.length - 1)
    const lower = Math.floor(idx)
    const upper = Math.ceil(idx)
    if (lower === upper) return sorted[lower]
    return sorted[lower] + (sorted[upper] - sorted[lower]) * (idx - lower)
  }

  private classifyFailure(error: string): string {
    const e = error.toLowerCase()
    if (e.includes("loop") || e.includes("repeat")) return "loop_detected"
    if (e.includes("not found") || e.includes("not find")) return "object_not_found"
    if (e.includes("nothing happens")) return "invalid_action"
    if (e.includes("timeout") || e.includes("max iteration") || e.includes("not completed")) return "timeout"
    if (e.includes("wrong") || e.includes("incorrect")) return "wrong_action"
    return "unknown"
  }
}
