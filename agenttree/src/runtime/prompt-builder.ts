/**
 * Prompt builder — assembles the system prompt for an agent.
 *
 * Structure (cache-friendly — static first, dynamic last):
 *   1. Base prompt       (from agent .md body — static, cacheable)
 *   2. Agent identity    (spec metadata — static per agent)
 *   3. Skills            (loaded on-demand — semi-static)
 *   4. Working memory    (recent actions/lessons/errors — dynamic)
 */

import type { AgentSpec } from "../spec/agent"
import type { SkillManager } from "../skill/manager"

export interface WorkingContext {
  recentActions: string[]
  lessons: string[]
  knownErrors: string[]
}

export class PromptBuilder {
  static async build(params: {
    basePrompt: string
    spec: AgentSpec
    skillManager: SkillManager
    workingContext?: WorkingContext
  }): Promise<string> {
    const { basePrompt, spec, skillManager, workingContext } = params
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

    if (spec.skills.length > 0) {
      const skillPrompt = await skillManager.buildSkillPrompt(spec.skills)
      if (skillPrompt) {
        sections.push(`<skills>\n${skillPrompt}\n</skills>`)
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

      if (parts.length > 0) {
        sections.push(`<working_memory>\n${parts.join("\n")}\n</working_memory>`)
      }
    }

    return sections.join("\n\n")
  }
}
