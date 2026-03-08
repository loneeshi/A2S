/**
 * SkillEvolutionEngine — generates new skills from reflection patterns.
 *
 * Trigger conditions:
 *   1. A task_type has success_rate < threshold AND ≥ minFailures failures
 *   2. Multiple reflections share the same errorPattern (repeated mistakes)
 *
 * Generation modes:
 *   1. LLM-assisted: Uses LLM to craft skill content from failure summaries
 *   2. Template-based: Builds a skeleton skill from reflection data (fallback)
 *
 * Generated skills are:
 *   - Written to skills/<domain>/<taskType>_auto.md
 *   - Injected into underperforming agents' skill lists
 *   - Tracked in evolution history for dedup
 */

import type { LLMClient } from "../llm/client"
import type { SkillSpec, SkillSpecInput } from "../spec/skill"
import type { ReflectionOutput } from "../reflection/types"
import type { PerformanceStats } from "../extension/types"
import { SkillManager } from "./manager"
import { AgentStore } from "../spec/store"
import { stringifyAgentFile } from "../parser/agent-parser"
import { join } from "node:path"
import { writeFile, mkdir } from "node:fs/promises"

export interface SkillEvolutionOptions {
  baseDir: string
  skillManager: SkillManager
  llm?: LLMClient
  failureThreshold?: number
  minFailures?: number
}

export interface EvolutionResult {
  skillId: string
  reason: string
  domain: string
  taskType: string
  injectedInto: string[]
}

export class SkillEvolutionEngine {
  private baseDir: string
  private skillManager: SkillManager
  private llm?: LLMClient
  private failureThreshold: number
  private minFailures: number
  private generatedSkills = new Set<string>()

  constructor(options: SkillEvolutionOptions) {
    this.baseDir = options.baseDir
    this.skillManager = options.skillManager
    this.llm = options.llm
    this.failureThreshold = options.failureThreshold ?? 0.5
    this.minFailures = options.minFailures ?? 2
  }

  async evolve(
    reflections: ReflectionOutput[],
    stats: PerformanceStats,
  ): Promise<EvolutionResult[]> {
    const results: EvolutionResult[] = []

    const patternGroups = this.groupByPattern(reflections)

    for (const [pattern, group] of patternGroups) {
      if (group.length < this.minFailures) continue

      const domain = group[0].domain
      const taskType = group[0].taskType
      const skillId = `${domain}/${taskType}_auto`

      if (this.generatedSkills.has(skillId)) {
        const existing = await this.skillManager.get(skillId)
        if (existing) {
          const updated = await this.updateSkill(skillId, existing.content, group)
          if (updated) {
            results.push({
              skillId,
              reason: `Updated skill with ${group.length} new failure patterns (${pattern})`,
              domain,
              taskType,
              injectedInto: [],
            })
          }
          continue
        }
      }

      const typeStats = stats.byTaskType[taskType]
      if (typeStats && typeStats.rate >= this.failureThreshold && typeStats.total >= 3) {
        continue
      }

      const content = await this.generateSkillContent(domain, taskType, group)
      const spec: SkillSpecInput = {
        id: skillId,
        description: `Auto-generated skill for ${taskType} tasks based on ${group.length} failure reflections`,
        whenToUse: `When handling ${taskType} tasks, especially to avoid: ${pattern}`,
        steps: this.extractSteps(group),
        tags: [domain, taskType, "auto-generated"],
        generatedBy: "evolution",
      }

      await this.skillManager.create(spec, content)
      this.generatedSkills.add(skillId)

      const injected = await this.injectSkill(skillId, domain, taskType)
      results.push({
        skillId,
        reason: `Generated from ${group.length} failures (pattern: ${pattern})`,
        domain,
        taskType,
        injectedInto: injected,
      })
    }

    const crossCuttingSkill = await this.checkCrossCuttingPatterns(reflections, stats)
    if (crossCuttingSkill) {
      results.push(crossCuttingSkill)
    }

    return results
  }

  private groupByPattern(
    reflections: ReflectionOutput[],
  ): Map<string, ReflectionOutput[]> {
    const groups = new Map<string, ReflectionOutput[]>()

    for (const r of reflections) {
      const key = r.errorPattern || `${r.failureType}:${r.domain}`
      const existing = groups.get(key) ?? []
      existing.push(r)
      groups.set(key, existing)
    }

    return groups
  }

  private async generateSkillContent(
    domain: string,
    taskType: string,
    reflections: ReflectionOutput[],
  ): Promise<string> {
    if (this.llm) {
      try {
        return await this.generateWithLLM(domain, taskType, reflections)
      } catch {
        // fallback to template
      }
    }

    return this.generateTemplate(domain, taskType, reflections)
  }

  private async generateWithLLM(
    domain: string,
    taskType: string,
    reflections: ReflectionOutput[],
  ): Promise<string> {
    const failureSummary = reflections
      .map(
        (r, i) =>
          `${i + 1}. [${r.failureType}] ${r.rootCause}\n   Tools: ${r.toolsInvolved.join(", ")}\n   Fix: ${r.promptUpdateContent || "N/A"}`,
      )
      .join("\n")

    const prompt = `You are writing a concise skill guide for an agent operating in the "${domain}" domain.

The agent repeatedly fails at "${taskType}" tasks. Here are the failure patterns:

${failureSummary}

Write a markdown skill guide (NO frontmatter, just content) that teaches the agent how to avoid these failures.

Requirements:
- Use ## headers for sections
- Include a step-by-step workflow
- Include a "Common Mistakes" section with concrete prevention rules
- Include a "Recovery Strategies" section for when things go wrong
- Reference tool names like \`env.goto\`, \`env.take\` etc
- Keep it under 400 words
- Write in the same language as the failure descriptions (Chinese if they're in Chinese)`

    const response = await this.llm!.chat(
      [
        {
          role: "system",
          content: "You are a skill documentation writer. Output ONLY markdown content.",
        },
        { role: "user", content: prompt },
      ],
      { temperature: 0.4 },
    )

    return response.content.trim()
  }

  private generateTemplate(
    domain: string,
    taskType: string,
    reflections: ReflectionOutput[],
  ): string {
    const failureTypes = [
      ...new Set(reflections.map((r) => r.failureType)),
    ]
    const rootCauses = reflections
      .map((r) => r.rootCause)
      .filter(Boolean)
      .slice(0, 5)
    const tools = [
      ...new Set(reflections.flatMap((r) => r.toolsInvolved)),
    ]
    const fixes = reflections
      .map((r) => r.promptUpdateContent)
      .filter(Boolean)
      .slice(0, 5)

    const sections: string[] = []

    sections.push(`## ${taskType} 任务指南（自动生成）`)
    sections.push("")
    sections.push(
      `本技能基于 ${reflections.length} 次失败反思自动生成，帮助避免常见错误。`,
    )

    sections.push("")
    sections.push("### 关键工具")
    for (const tool of tools) {
      sections.push(`- \`${tool}\``)
    }

    sections.push("")
    sections.push("### 常见错误")
    for (const cause of rootCauses) {
      sections.push(`- ${cause}`)
    }

    if (fixes.length > 0) {
      sections.push("")
      sections.push("### 预防措施")
      for (const fix of fixes) {
        sections.push(`- ${fix}`)
      }
    }

    sections.push("")
    sections.push("### 恢复策略")
    for (const ft of failureTypes) {
      switch (ft) {
        case "wrong_object":
          sections.push(
            "- 操作前用 `env.look` 或 `env.examine` 确认目标物体的确切名称和编号",
          )
          break
        case "missing_step":
          sections.push("- 严格按步骤执行，不要跳过中间步骤（如先 open 再 take）")
          break
        case "tool_misuse":
          sections.push("- 检查工具参数是否正确，确认工具名称拼写无误")
          break
        case "timeout":
          sections.push("- 制定搜索策略，优先检查最可能的位置，避免盲目遍历")
          break
        case "incorrect_sequence":
          sections.push("- 先导航到目标位置（goto），再执行操作（take/put/open）")
          break
        default:
          sections.push("- 仔细阅读环境反馈，根据 observation 调整策略")
      }
    }

    return sections.join("\n")
  }

  private extractSteps(reflections: ReflectionOutput[]): string[] {
    const steps: string[] = [
      "分析任务目标，确认需要的工具和操作序列",
      "观察环境状态，定位目标物体",
    ]

    const hasWrongObject = reflections.some(
      (r) => r.failureType === "wrong_object",
    )
    if (hasWrongObject) {
      steps.push("确认物体名称和编号（包括数字后缀）")
    }

    const hasMissingStep = reflections.some(
      (r) => r.failureType === "missing_step",
    )
    if (hasMissingStep) {
      steps.push("列出完整操作步骤，不跳过任何中间步骤")
    }

    steps.push("执行操作并验证每步结果")
    steps.push("确认任务完成")

    return steps
  }

  private async updateSkill(
    skillId: string,
    existingContent: string,
    newReflections: ReflectionOutput[],
  ): Promise<boolean> {
    const newCauses = newReflections
      .map((r) => r.rootCause)
      .filter(Boolean)

    if (newCauses.length === 0) return false

    const appendSection = [
      "",
      `### 新增失败模式 (${new Date().toISOString().split("T")[0]})`,
    ]
    for (const cause of newCauses.slice(0, 3)) {
      appendSection.push(`- ${cause}`)
    }

    const updatedContent = existingContent + "\n" + appendSection.join("\n")

    await this.skillManager.update(skillId, {}, updatedContent)
    return true
  }

  private async injectSkill(
    skillId: string,
    domain: string,
    _taskType: string,
  ): Promise<string[]> {
    const agentStore = new AgentStore(join(this.baseDir, "agents"))
    const agents = await agentStore.list()
    const injected: string[] = []

    for (const agent of agents) {
      const agentDomain = agent.spec.metadata?.domain as string | undefined
      if (agentDomain !== domain) continue
      if (agent.spec.role !== "worker") continue
      if (agent.spec.skills.includes(skillId)) continue

      const updatedSkills = [...agent.spec.skills, skillId]
      await agentStore.update(agent.spec.id, { skills: updatedSkills })
      injected.push(agent.spec.id)
    }

    return injected
  }

  private async checkCrossCuttingPatterns(
    reflections: ReflectionOutput[],
    stats: PerformanceStats,
  ): Promise<EvolutionResult | null> {
    if (stats.totalTasks < 6) return null

    const timeoutCount = reflections.filter(
      (r) => r.failureType === "timeout",
    ).length
    if (timeoutCount >= 3 && !this.generatedSkills.has("common/efficiency_auto")) {
      const skillId = "common/efficiency_auto"
      const spec: SkillSpecInput = {
        id: skillId,
        description: "Efficiency strategies to avoid timeout failures",
        whenToUse:
          "When tasks frequently time out or take too many steps",
        steps: [
          "优先搜索最可能的位置",
          "避免重复访问已检查的位置",
          "跟踪已访问位置的列表",
          "使用环境线索缩小搜索范围",
        ],
        tags: ["common", "efficiency", "auto-generated"],
      }
      const content = [
        "## 效率优化（自动生成）",
        "",
        "### 搜索策略",
        "1. 先 `env.look` 观察当前位置，获取可见物体和位置列表",
        "2. 根据任务类型优先搜索最可能的位置（如找食物先检查 fridge、countertop）",
        "3. 记住已检查过的位置，不要重复访问",
        "4. 如果前 5 个位置都没找到目标，重新审视任务描述",
        "",
        "### 操作效率",
        "- 先导航到目标位置再操作（减少 'Nothing happens' 错误）",
        "- 一次行动完成一个子目标",
        "- 不要在已完成的步骤上重复操作",
      ].join("\n")

      await this.skillManager.create(spec, content)
      this.generatedSkills.add(skillId)

      return {
        skillId,
        reason: `${timeoutCount} timeout failures detected across tasks`,
        domain: "common",
        taskType: "cross-cutting",
        injectedInto: [],
      }
    }

    return null
  }

  getGeneratedSkills(): string[] {
    return [...this.generatedSkills]
  }
}
