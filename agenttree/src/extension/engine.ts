/**
 * DynamicExtensionEngine v2 — extends the agent tree via LLM-designed agents and skills.
 *
 * New architecture:
 *   1. Rules detect capability gaps (trigger layer)
 *   2. LLM designs functionally distinct agents/skills (design layer)
 *   3. Generated entities enter probation (validation layer)
 *   4. After N tasks, compare to baseline → promote or disable
 */

import { AgentStore } from "../spec/store"
import { SkillManager } from "../skill/manager"
import type { LLMClient } from "../llm/client"
import type {
  ExtensionProposal,
  ExpansionTrigger,
  ExpansionRecord,
  LLMWorkerDesign,
  LLMSkillDesign,
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
  probationTasks?: number
}

export class DynamicExtensionEngine {
  private baseDir: string
  private monitor: PerformanceMonitor
  private llm: LLMClient
  private threshold: number
  private maxWorkers: number
  private probationTasks: number
  private extensionHistory: ExpansionRecord[] = []
  private appliedTriggers = new Set<string>()

  constructor(options: ExtensionEngineOptions) {
    this.baseDir = options.baseDir
    this.monitor = options.monitor
    this.llm = options.llm
    this.threshold = options.extensionThreshold ?? 0.7
    this.maxWorkers = options.maxWorkers ?? 15
    this.probationTasks = options.probationTasks ?? 5
  }

  async checkAndExtend(): Promise<ExtensionProposal[]> {
    if (!this.monitor.shouldExtend(this.threshold)) {
      return []
    }

    const triggers = this.detectTriggers()
    if (triggers.length === 0) return []

    const applied: ExtensionProposal[] = []

    for (const trigger of triggers.slice(0, 2)) {
      const triggerKey = `${trigger.type}:${trigger.gap.neededCapability}`
      if (this.appliedTriggers.has(triggerKey)) continue

      try {
        const proposal = await this.designSolution(trigger)
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

  detectTriggers(): ExpansionTrigger[] {
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
      const failures = this.monitor.getSubtaskFailures(ws.workerId, 5)
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

  private async designSolution(trigger: ExpansionTrigger): Promise<ExtensionProposal | null> {
    const currentTree = await this.describeCurrentTree()
    const toolLibrary = await this.describeToolLibrary()

    if (trigger.type === "worker_capability_gap") {
      return this.designWorker(trigger, currentTree, toolLibrary)
    } else if (trigger.type === "skill_gap") {
      return this.designSkill(trigger, currentTree)
    }
    return null
  }

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
    if (!design || !design.id || !design.tools || !design.prompt_strategy) return null

    return {
      extensionType: "add_worker",
      reason: trigger.reason,
      priority: 1.0 - trigger.evidence.successRate,
      trigger,
      details: { design },
    }
  }

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
    if (!design || !design.id || !design.content) return null

    return {
      extensionType: "add_skill",
      reason: trigger.reason,
      priority: (1.0 - trigger.evidence.successRate) * 0.8,
      trigger,
      details: { design },
    }
  }

  private async applyProposal(proposal: ExtensionProposal): Promise<string | null> {
    switch (proposal.extensionType) {
      case "add_worker":
        return this.applyWorkerDesign(proposal)
      case "add_skill":
        return this.applySkillDesign(proposal)
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
        generatedBy: "extension_engine_v2",
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

    console.log(`[extension] Created new worker: ${agentId} — ${design.differentiation}`)
    return agentId
  }

  private async applySkillDesign(proposal: ExtensionProposal): Promise<string> {
    const design = proposal.details.design as LLMSkillDesign
    const skillId = design.id

    const skillManager = new SkillManager(join(this.baseDir, "skills"))

    const hasExamples = design.examples && design.examples.trim().length > 0
    const hasToolRestriction = design.allowedTools && design.allowedTools.length > 0

    const specInput = {
      id: skillId,
      description: design.description,
      type: design.type as "reference" | "task" | "workflow" ?? "reference",
      whenToUse: `When handling tasks related to: ${proposal.trigger.gap.neededCapability}`,
      tags: [design.type, "auto-generated"],
      generatedBy: "extension" as const,
      allowedTools: hasToolRestriction ? design.allowedTools : undefined,
    }

    if (hasExamples) {
      const supportingFiles: Record<string, string> = {
        "examples.md": design.examples!,
      }
      const contentWithRef = design.content + "\n\nFor worked examples, see [examples.md](examples.md)."
      await skillManager.createDirectory(specInput, contentWithRef, supportingFiles)
    } else {
      await skillManager.create(specInput, design.content)
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

    console.log(`[extension] Created new skill: ${skillId} for ${design.for_worker}`)
    return skillId
  }

  updateProbation(entityId: string, success: boolean): void {
    const record = this.extensionHistory.find((r) => r.entityId === entityId && r.status === "probation")
    if (!record) return

    record.performance.tasksHandled++
    const tasks = record.performance.tasksHandled
    const currentRate = record.performance.successRate
    record.performance.successRate = currentRate + (success ? 1 - currentRate : -currentRate) / tasks

    if (tasks >= this.probationTasks) {
      if (record.performance.successRate > record.performance.baselineRate) {
        record.status = "active"
        console.log(`[extension] Promoted ${entityId}: ${(record.performance.successRate * 100).toFixed(0)}% vs baseline ${(record.performance.baselineRate * 100).toFixed(0)}%`)
      } else {
        record.status = "disabled"
        console.log(`[extension] Disabled ${entityId}: ${(record.performance.successRate * 100).toFixed(0)}% vs baseline ${(record.performance.baselineRate * 100).toFixed(0)}%`)
      }
    }
  }

  getHistory(): ExpansionRecord[] {
    return [...this.extensionHistory]
  }

  getProbationEntities(): ExpansionRecord[] {
    return this.extensionHistory.filter((r) => r.status === "probation")
  }

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
