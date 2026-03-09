/**
 * Prompt builder v2 — assembles the system prompt for an agent.
 *
 * Structure (cache-friendly — static first, dynamic last):
 *   1. Base prompt       (from agent .md body — static, cacheable)
 *   2. Agent identity    (spec metadata — static per agent)
 *   3. Skills            (loaded on-demand, preprocessed — semi-static)
 *   4. Working memory    (recent actions/lessons/errors — dynamic)
 *
 * New in v2:
 *   - Skills processed with argument substitution and dynamic injection
 *   - Active skill tool restrictions surfaced in prompt
 *   - Fork-context skills excluded (they run in subagents, not inline)
 *   - Supporting file references included for directory skills
 */

import type { AgentSpec } from "../spec/agent"
import type { SkillManager } from "../skill/manager"
import type { SkillSpec } from "../spec/skill"
import type { WorkingContext } from "../memory/manager"

export type { WorkingContext }

export interface SkillBuildArgs {
  arguments?: string
  argumentList?: string[]
}

export class PromptBuilder {
  static async build(params: {
    basePrompt: string
    spec: AgentSpec
    skillManager: SkillManager
    workingContext?: WorkingContext
    skillArgs?: SkillBuildArgs
    workerDescriptions?: string | null
  }): Promise<string> {
    const { basePrompt, spec, skillManager, workingContext, skillArgs, workerDescriptions } = params
    const sections: string[] = []

    sections.push(basePrompt)

    sections.push(
      [
        "<agent_identity>",
        `id: ${spec.id}`,
        `name: ${spec.name}`,
        `role: ${spec.role}`,
        spec.description ? `description: ${spec.description}` : "",
        "</agent_identity>",
      ]
        .filter(Boolean)
        .join("\n"),
    )

    if (workerDescriptions && spec.role === "orchestrator") {
      sections.push(`<available_workers>\n${workerDescriptions}\n</available_workers>`)
    }

    if (spec.skills.length > 0) {
      const skills = await skillManager.resolve(spec.skills)
      const inlineSkills = skills.filter((s) => s.spec.context !== "fork")

      if (inlineSkills.length > 0) {
        const skillPrompt = await skillManager.buildSkillPrompt(
          inlineSkills.map((s) => s.spec.id),
          skillArgs,
        )
        if (skillPrompt) {
          sections.push(`<skills>\n${skillPrompt}\n</skills>`)
        }
      }

      const forkSkills = skills.filter((s) => s.spec.context === "fork")
      if (forkSkills.length > 0) {
        const forkList = forkSkills
          .map((s) => `- ${s.spec.id}: ${s.spec.description}`)
          .join("\n")
        sections.push(`<available_fork_skills>\n${forkList}\n</available_fork_skills>`)
      }

      const toolRestrictions = this.collectToolRestrictions(inlineSkills.map((s) => s.spec))
      if (toolRestrictions) {
        sections.push(`<skill_tool_restrictions>\n${toolRestrictions}\n</skill_tool_restrictions>`)
      }
    }

    if (workingContext) {
      const parts: string[] = []

      if (workingContext.lessons.length > 0) {
        parts.push("## Lessons Learned")
        workingContext.lessons.forEach((l) => parts.push(`- ${l}`))
      }

      if (workingContext.knownErrors.length > 0) {
        parts.push("## Known Errors")
        workingContext.knownErrors.forEach((e) => parts.push(`- ${e}`))
      }

      if (workingContext.recentActions.length > 0) {
        parts.push("## Recent Actions")
        workingContext.recentActions.forEach((a) => parts.push(`- ${a}`))
      }

      if (workingContext.semanticMemories && workingContext.semanticMemories.length > 0) {
        parts.push("## Relevant Past Experience")
        workingContext.semanticMemories.forEach((m) =>
          parts.push(`- ${m.content}${m.score !== undefined ? ` (relevance: ${m.score.toFixed(2)})` : ""}`),
        )
      }

      if (parts.length > 0) {
        sections.push(`<working_memory>\n${parts.join("\n")}\n</working_memory>`)
      }
    }

    return sections.join("\n\n")
  }

  private static collectToolRestrictions(skills: SkillSpec[]): string | null {
    const restrictions = skills
      .filter((s) => s.allowedTools && s.allowedTools.length > 0)
      .map((s) => `- ${s.id}: only [${s.allowedTools!.join(", ")}]`)

    return restrictions.length > 0 ? restrictions.join("\n") : null
  }
}
