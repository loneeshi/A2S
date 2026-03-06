/**
 * PerformanceMonitor — tracks task results and computes stats per agent
 * and per task type. Used by the extension engine to decide when to expand.
 */

import type { TaskResult, PerformanceStats } from "./types"

export class PerformanceMonitor {
  private history: TaskResult[] = []
  private maxHistory = 1000

  record(result: TaskResult): void {
    this.history.push(result)
    if (this.history.length > this.maxHistory) {
      this.history = this.history.slice(-this.maxHistory)
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

    return {
      totalTasks: total,
      successCount,
      failureCount,
      successRate: total > 0 ? successCount / total : 0,
      byTaskType,
      byAgent,
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

  getRecentFailures(n = 10): TaskResult[] {
    return this.history.filter((r) => !r.success).slice(-n)
  }

  clear(): void {
    this.history = []
  }
}
