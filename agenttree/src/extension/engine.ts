/**
 * DynamicExtensionEngine — extends the agent tree at runtime based on
 * performance feedback.
 *
 * Extension loop:
 *   1. PerformanceMonitor detects low success rate
 *   2. Engine generates proposals (add worker, specialize, replicate)
 *   3. Proposals are sorted by priority
 *   4. Top proposals are applied → new .md files written → TreeRuntime reloaded
 *
 * This is the TS port of Python core/optimizer/extension_engine.py,
 * adapted to work with the filesystem-based agent store.
 */

import type { AgentSpec } from "../spec/agent"
import { AgentStore } from "../spec/store"
import type { ExtensionProposal, ExtensionType } from "./types"
import { PerformanceMonitor } from "./monitor"
import { join } from "node:path"
import { writeFile, mkdir } from "node:fs/promises"
import matter from "gray-matter"

export interface ExtensionEngineOptions {
  baseDir: string
  monitor: PerformanceMonitor
  extensionThreshold?: number
  maxWorkers?: number
  maxManagers?: number
}

export class DynamicExtensionEngine {
  private baseDir: string
  private monitor: PerformanceMonitor
  private threshold: number
  private maxWorkers: number
  private maxManagers: number
  private extensionHistory: ExtensionProposal[] = []

  constructor(options: ExtensionEngineOptions) {
    this.baseDir = options.baseDir
    this.monitor = options.monitor
    this.threshold = options.extensionThreshold ?? 0.7
    this.maxWorkers = options.maxWorkers ?? 20
    this.maxManagers = options.maxManagers ?? 5
  }

  async checkAndExtend(): Promise<ExtensionProposal[]> {
    if (!this.monitor.shouldExtend(this.threshold)) {
      return []
    }

    const proposals = this.generateProposals()
    if (proposals.length === 0) return []

    proposals.sort((a, b) => b.priority - a.priority)

    const toApply = proposals.slice(0, 3)
    for (const proposal of toApply) {
      await this.applyProposal(proposal)
      this.extensionHistory.push(proposal)
    }

    return toApply
  }

  generateProposals(): ExtensionProposal[] {
    const proposals: ExtensionProposal[] = []
    const stats = this.monitor.getStats()

    const difficultTypes = this.monitor.getDifficultTaskTypes(0.5)
    for (const taskType of difficultTypes) {
      const typeStats = stats.byTaskType[taskType]
      proposals.push({
        extensionType: "add_worker",
        reason: `Task type '${taskType}' has low success rate (${typeStats.rate.toFixed(2)})`,
        priority: 1.0 - typeStats.rate,
        details: {
          taskType,
          currentSuccessRate: typeStats.rate,
          specialization: taskType,
        },
      })
    }

    const underperforming = this.monitor.getUnderperformingAgents(this.threshold)
    for (const agentId of underperforming) {
      const agentStats = stats.byAgent[agentId]
      proposals.push({
        extensionType: "specialize_worker",
        reason: `Agent '${agentId}' underperforming (${agentStats.rate.toFixed(2)})`,
        priority: (1.0 - agentStats.rate) * 0.9,
        details: {
          agentId,
          currentSuccessRate: agentStats.rate,
        },
      })
    }

    return proposals
  }

  async applyProposal(proposal: ExtensionProposal): Promise<string | null> {
    switch (proposal.extensionType) {
      case "add_worker":
        return this.addWorker(proposal)
      case "specialize_worker":
        return this.specializeWorker(proposal)
      case "replicate_worker":
        return this.replicateWorker(proposal)
      case "add_manager":
        return this.addManager(proposal)
      default:
        return null
    }
  }

  getHistory(): ExtensionProposal[] {
    return [...this.extensionHistory]
  }

  private async addWorker(proposal: ExtensionProposal): Promise<string> {
    const spec = proposal.details.specialization as string
    const agentId = `${spec}_specialist_${Date.now()}`

    // Find the best existing worker to inherit from (the one that handles this task type)
    const parentAgent = await this.findParentAgent(spec)

    const tools = parentAgent?.spec.tools ?? { allow: [], deny: [] }
    const skills = parentAgent?.spec.skills ?? []
    const parentPrompt = parentAgent?.prompt ?? ""

    const frontmatter = {
      id: agentId,
      name: `${this.capitalize(spec)}Specialist`,
      role: "worker",
      mode: "subagent",
      description: `Specialized worker for ${spec} tasks — auto-generated from ${parentAgent?.spec.id ?? "scratch"}`,
      tools,
      memory: { mode: "light", store: "jsonl", capacity: 200 },
      skills,
      metadata: {
        domain: parentAgent?.spec.metadata?.domain ?? spec,
        benchmark: parentAgent?.spec.metadata?.benchmark ?? undefined,
        taskTypes: [spec],
        priority: 10,
        generatedBy: "extension_engine",
        parentAgent: parentAgent?.spec.id,
        reason: proposal.reason,
        version: "0.1.0",
      },
    }

    // Inherit the parent's prompt (which has the actual domain strategies)
    // Add a specialization header
    const header = `<!-- Auto-generated specialist for ${spec}. Inherited from ${parentAgent?.spec.id ?? "template"}. -->\n\n`
    const body = parentPrompt ? header + parentPrompt : header + `You are a specialized worker for ${spec} tasks.\n\n- Focus on ${spec} operations.\n- Record failure reasons and try alternative strategies.\n- Report results when done.\n`

    const md = matter.stringify(body, frontmatter)
    const agentsDir = join(this.baseDir, "agents")
    await mkdir(agentsDir, { recursive: true })
    await writeFile(join(agentsDir, `${agentId}.md`), md, "utf-8")

    return agentId
  }

  private async findParentAgent(taskType: string): Promise<{ spec: AgentSpec; prompt: string } | null> {
    const store = new AgentStore(join(this.baseDir, "agents"))
    const agents = await store.list()

    // First: find a worker whose taskTypes includes this taskType
    for (const agent of agents) {
      if (agent.spec.role !== "worker") continue
      const meta = agent.spec.metadata as Record<string, unknown> | undefined
      const taskTypes = meta?.taskTypes as string[] | undefined
      if (taskTypes?.includes(taskType)) {
        return agent
      }
    }

    // Second: find any worker in the same domain
    for (const agent of agents) {
      if (agent.spec.role !== "worker") continue
      const meta = agent.spec.metadata as Record<string, unknown> | undefined
      if (meta?.domain === taskType.split("_")[0]) {
        return agent
      }
    }

    // Third: find any worker with tools (not empty)
    for (const agent of agents) {
      if (agent.spec.role !== "worker") continue
      if (agent.spec.tools.allow && agent.spec.tools.allow.length > 0) {
        return agent
      }
    }

    return null
  }

  private async specializeWorker(proposal: ExtensionProposal): Promise<string | null> {
    const agentId = proposal.details.agentId as string
    const store = new AgentStore(join(this.baseDir, "agents"))
    const existing = await store.get(agentId)
    if (!existing) return null

    const newId = `${agentId}_specialized_${Date.now()}`
    const existingMeta = existing.spec.metadata as Record<string, unknown> | undefined

    const frontmatter = {
      id: newId,
      name: `${existing.spec.name}Specialized`,
      role: existing.spec.role,
      mode: existing.spec.mode,
      description: `Specialized from ${agentId} — ${proposal.reason}`,
      tools: existing.spec.tools,
      memory: existing.spec.memory,
      skills: existing.spec.skills,
      metadata: {
        ...existingMeta,
        taskTypes: existingMeta?.taskTypes ?? undefined,
        priority: ((existingMeta?.priority as number) ?? 0) + 5,
        parentAgent: agentId,
        generatedBy: "extension_engine",
        reason: proposal.reason,
      },
    }

    const header = `<!-- Specialized from ${agentId}. ${proposal.reason} -->\n\n`
    const body = existing.prompt ? header + existing.prompt : header
    const md = matter.stringify(body, frontmatter)
    const agentsDir = join(this.baseDir, "agents")
    await writeFile(join(agentsDir, `${newId}.md`), md, "utf-8")

    return newId
  }

  private async replicateWorker(proposal: ExtensionProposal): Promise<string | null> {
    const agentId = proposal.details.agentId as string
    const store = new AgentStore(join(this.baseDir, "agents"))
    const existing = await store.get(agentId)
    if (!existing) return null

    const newId = `${agentId}_replica_${Date.now()}`
    const spec = {
      ...existing.spec,
      id: newId,
      name: `${existing.spec.name}Replica`,
      metadata: {
        ...existing.spec.metadata,
        parentAgent: agentId,
        replica: true,
        generatedBy: "extension_engine",
      },
    }

    const frontmatter = { ...spec }
    const md = matter.stringify(existing.prompt, frontmatter)
    const agentsDir = join(this.baseDir, "agents")
    await writeFile(join(agentsDir, `${newId}.md`), md, "utf-8")

    return newId
  }

  private async addManager(proposal: ExtensionProposal): Promise<string> {
    const managerType = (proposal.details.managerType as string) ?? "coordinator"
    const agentId = `${managerType}_manager_${Date.now()}`

    const frontmatter = {
      id: agentId,
      name: `${this.capitalize(managerType)}Manager`,
      role: "manager",
      mode: "subagent",
      description: `Coordinator manager — auto-generated by extension engine`,
      tools: { allow: [], deny: [] },
      memory: { mode: "light", store: "jsonl", capacity: 300 },
      skills: [],
      metadata: {
        managerType,
        generatedBy: "extension_engine",
        reason: proposal.reason,
        version: "0.1.0",
      },
    }

    const body = `你是一个 ${managerType} 类型的 manager，负责协调 worker 的任务分配。\n\n- 根据任务类型路由到合适的 worker。\n- 监控 worker 执行结果。\n- 失败时尝试重新分配。\n`

    const md = matter.stringify(body, frontmatter)
    const agentsDir = join(this.baseDir, "agents")
    await mkdir(agentsDir, { recursive: true })
    await writeFile(join(agentsDir, `${agentId}.md`), md, "utf-8")

    return agentId
  }

  private capitalize(s: string): string {
    return s.charAt(0).toUpperCase() + s.slice(1)
  }
}
