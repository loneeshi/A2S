/**
 * AgentRouter — dynamically selects the best agent for a task
 * by matching taskType against agent metadata.
 *
 * Selection logic:
 *   1. Filter agents by role=worker AND metadata.benchmark matches
 *   2. Filter to agents whose metadata.taskTypes includes the taskType
 *   3. Sort by metadata.priority (higher wins, specialists > generalists)
 *   4. Return the highest-priority match
 *
 * This replaces the hardcoded selectWorker() in the runner and makes
 * extension-generated agents discoverable automatically — as long as
 * they have the right metadata.taskTypes set.
 */

import type { AgentRuntime } from "./agent"

export interface RouteResult {
  agentId: string
  matchType: "specialist" | "generalist" | "fallback"
}

export class AgentRouter {
  constructor(private agents: Map<string, AgentRuntime>) {}

  route(benchmark: string, taskType: string): RouteResult {
    const candidates: Array<{
      id: string
      priority: number
      matchType: "specialist" | "generalist"
    }> = []

    for (const [id, agent] of this.agents) {
      if (agent.spec.role !== "worker") continue

      const meta = agent.spec.metadata as Record<string, unknown> | undefined
      if (!meta) continue

      // Skip agents from a different benchmark
      if (meta.benchmark && meta.benchmark !== benchmark) continue

      const taskTypes = meta.taskTypes as string[] | undefined
      const priority = (meta.priority as number) ?? 0

      if (taskTypes && Array.isArray(taskTypes)) {
        if (taskTypes.includes(taskType)) {
          candidates.push({ id, priority, matchType: "specialist" })
        }
        // Agent has taskTypes but doesn't match → skip (it's a specialist for other types)
      } else {
        // No taskTypes declared → generalist, matches anything in its benchmark
        candidates.push({ id, priority: priority - 100, matchType: "generalist" })
      }
    }

    // Sort: specialists first (higher priority), then generalists
    candidates.sort((a, b) => b.priority - a.priority)

    if (candidates.length > 0) {
      const best = candidates[0]
      return { agentId: best.id, matchType: best.matchType }
    }

    // Absolute fallback — pick the first worker we find
    for (const [id, agent] of this.agents) {
      if (agent.spec.role === "worker") {
        return { agentId: id, matchType: "fallback" }
      }
    }

    throw new Error(`No worker agents available for ${benchmark}/${taskType}`)
  }

  /**
   * List all workers that could handle a given benchmark, grouped by taskType coverage.
   * Useful for injecting into coordinator prompts.
   */
  describeWorkers(benchmark: string): string {
    const lines: string[] = []
    for (const [id, agent] of this.agents) {
      if (agent.spec.role !== "worker") continue

      const meta = agent.spec.metadata as Record<string, unknown> | undefined
      if (meta?.benchmark && meta.benchmark !== benchmark) continue

      const taskTypes = (meta?.taskTypes as string[])?.join(", ") ?? "all"
      const priority = (meta?.priority as number) ?? 0
      const desc = agent.spec.description ?? ""
      lines.push(`- ${id} [priority=${priority}] tasks=[${taskTypes}]: ${desc}`)
    }
    return lines.join("\n")
  }
}
