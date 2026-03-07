/**
 * PerformanceMonitor — tracks task results at task-level and subtask-level.
 * Used by the extension engine to detect capability gaps and trigger expansion.
 *
 * Tracks:
 *   - Task-level success rates by taskType and agentUsed
 *   - Subtask-level success rates by subtaskType and workerId
 *   - Failure pattern classification
 */

import type { TaskResult, SubtaskResult, PerformanceStats } from "./types"

export class PerformanceMonitor {
  private history: TaskResult[] = []
  private subtaskHistory: SubtaskResult[] = []
  private failurePatterns = new Map<string, number>()
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
    this.subtaskHistory.push(result)
    if (this.subtaskHistory.length > this.maxHistory * 3) {
      this.subtaskHistory = this.subtaskHistory.slice(-this.maxHistory * 3)
    }
  }

  getStats(): PerformanceStats {
    const total = this.history.length
    const successCount = this.history.filter((r) => r.success).length
    const failureCount = total - successCount

    const byTaskType: PerformanceStats["byTaskType"] = {}
    const byAgent: PerformanceStats["byAgent"] = {}

    for (const r of this.history) {
      if (!byTaskType[r.taskType]) {
        byTaskType[r.taskType] = { total: 0, success: 0, rate: 0 }
      }
      byTaskType[r.taskType].total++
      if (r.success) byTaskType[r.taskType].success++

      if (!byAgent[r.agentUsed]) {
        byAgent[r.agentUsed] = { total: 0, success: 0, rate: 0 }
      }
      byAgent[r.agentUsed].total++
      if (r.success) byAgent[r.agentUsed].success++
    }

    for (const v of Object.values(byTaskType)) {
      v.rate = v.total > 0 ? v.success / v.total : 0
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

    const failurePatterns: Record<string, number> = Object.fromEntries(this.failurePatterns)

    return {
      totalTasks: total,
      successCount,
      failureCount,
      successRate: total > 0 ? successCount / total : 0,
      byTaskType,
      byAgent,
      bySubtask,
      failurePatterns,
    }
  }

  shouldExtend(threshold = 0.7): boolean {
    if (this.history.length < 5) return false
    const stats = this.getStats()
    return stats.successRate < threshold
  }

  getUnderperformingAgents(threshold = 0.7, minTasks = 3): string[] {
    const stats = this.getStats()
    return Object.entries(stats.byAgent)
      .filter(([, v]) => v.total >= minTasks && v.rate < threshold)
      .map(([k]) => k)
  }

  getDifficultTaskTypes(threshold = 0.5, minTasks = 3): string[] {
    const stats = this.getStats()
    return Object.entries(stats.byTaskType)
      .filter(([, v]) => v.total >= minTasks && v.rate < threshold)
      .map(([k]) => k)
  }

  getWeakSubtasks(threshold = 0.5, minAttempts = 3): Array<{ key: string; workerId: string; subtaskType: string; rate: number; total: number }> {
    const stats = this.getStats()
    return Object.entries(stats.bySubtask)
      .filter(([, v]) => v.total >= minAttempts && v.rate < threshold)
      .map(([key, v]) => {
        const [workerId, subtaskType] = key.split(":")
        return { key, workerId, subtaskType, rate: v.rate, total: v.total }
      })
      .sort((a, b) => a.rate - b.rate)
  }

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

  private classifyFailure(error: string): string {
    const e = error.toLowerCase()
    if (e.includes("loop") || e.includes("repeat")) return "loop_detected"
    if (e.includes("not found") || e.includes("not find")) return "object_not_found"
    if (e.includes("nothing happens")) return "invalid_action"
    if (e.includes("timeout") || e.includes("max iteration") || e.includes("not completed")) return "timeout"
    if (e.includes("wrong") || e.includes("incorrect")) return "wrong_action"
    return "unknown"
  }

  clear(): void {
    this.history = []
    this.subtaskHistory = []
    this.failurePatterns.clear()
  }
}
