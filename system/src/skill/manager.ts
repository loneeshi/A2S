/**
 * SkillManager v2 — manages skills in both legacy (.md) and directory (SKILL.md) formats.
 *
 * Supports:
 *   - Legacy: skills/<domain>/<name>.md (single file, frontmatter + content)
 *   - Directory: skills/<domain>/<name>/SKILL.md + supporting files
 *   - Dynamic context injection: !`command` replaced with shell output
 *   - Argument substitution: $ARGUMENTS, $ARGUMENTS[N], $N
 *   - Supporting file resolution for directory-based skills
 */

import { readFile, writeFile, unlink, readdir, mkdir, rmdir, stat } from "node:fs/promises"
import { join, dirname, relative, resolve } from "node:path"
import { execSync } from "node:child_process"
import matter from "gray-matter"
import { SkillSpecSchema } from "../spec/skill"
import type { SkillSpec, SkillSpecInput } from "../spec/skill"

export interface ResolvedSkill {
  spec: SkillSpec
  content: string
  dir?: string
  supportingFiles?: string[]
}

export class SkillManager {
  constructor(private skillsDir: string) {}

  async create(spec: SkillSpecInput, content: string): Promise<void> {
    const validated = SkillSpecSchema.parse(spec)
    const filePath = this.resolveLegacyPath(validated.id)

    await mkdir(dirname(filePath), { recursive: true })

    const { id: _, ...frontmatterFields } = validated
    const cleaned = this.cleanFrontmatter(frontmatterFields)
    const md = matter.stringify(content, cleaned)
    await writeFile(filePath, md, "utf-8")
  }

  async createDirectory(spec: SkillSpecInput, content: string, supportingFiles?: Record<string, string>): Promise<void> {
    const validated = SkillSpecSchema.parse(spec)
    const skillDir = join(this.skillsDir, validated.id)
    await mkdir(skillDir, { recursive: true })

    const { id: _, ...frontmatterFields } = validated
    const cleaned = this.cleanFrontmatter(frontmatterFields)
    const md = matter.stringify(content, cleaned)
    await writeFile(join(skillDir, "SKILL.md"), md, "utf-8")

    if (supportingFiles) {
      for (const [filename, fileContent] of Object.entries(supportingFiles)) {
        const filePath = join(skillDir, filename)
        await mkdir(dirname(filePath), { recursive: true })
        await writeFile(filePath, fileContent, "utf-8")
      }
    }
  }

  async get(skillId: string): Promise<ResolvedSkill | undefined> {
    const dirSkill = await this.getFromDirectory(skillId)
    if (dirSkill) return dirSkill

    return this.getFromLegacy(skillId)
  }

  private async getFromDirectory(skillId: string): Promise<ResolvedSkill | undefined> {
    const skillDir = join(this.skillsDir, skillId)
    const skillMd = join(skillDir, "SKILL.md")

    let raw: string
    try {
      raw = await readFile(skillMd, "utf-8")
    } catch {
      return undefined
    }

    const parsed = matter(raw)
    const spec = SkillSpecSchema.parse({ ...parsed.data, id: skillId })

    const supportingFiles: string[] = []
    await this.listSupportingFiles(skillDir, skillDir, supportingFiles)

    return { spec, content: parsed.content.trim(), dir: skillDir, supportingFiles }
  }

  private async getFromLegacy(skillId: string): Promise<ResolvedSkill | undefined> {
    const filePath = this.resolveLegacyPath(skillId)

    let raw: string
    try {
      raw = await readFile(filePath, "utf-8")
    } catch {
      return undefined
    }

    const parsed = matter(raw)
    const spec = SkillSpecSchema.parse({ ...parsed.data, id: skillId })
    return { spec, content: parsed.content.trim() }
  }

  async update(
    skillId: string,
    updates: Partial<SkillSpec>,
    newContent?: string,
  ): Promise<boolean> {
    const existing = await this.get(skillId)
    if (!existing) return false

    const merged: SkillSpec = { ...existing.spec, ...updates, id: skillId }
    const content = newContent ?? existing.content
    const validated = SkillSpecSchema.parse(merged)

    const isDir = existing.dir !== undefined
    const filePath = isDir
      ? join(existing.dir!, "SKILL.md")
      : this.resolveLegacyPath(skillId)

    const { id: _, ...frontmatterFields } = validated
    const cleaned = this.cleanFrontmatter(frontmatterFields)
    const md = matter.stringify(content, cleaned)
    await writeFile(filePath, md, "utf-8")

    return true
  }

  async remove(skillId: string): Promise<boolean> {
    const existing = await this.get(skillId)
    if (!existing) return false

    if (existing.dir) {
      const { rm } = await import("node:fs/promises")
      await rm(existing.dir, { recursive: true, force: true })
      return true
    }

    const filePath = this.resolveLegacyPath(skillId)
    try {
      await unlink(filePath)
    } catch {
      return false
    }

    let dir = dirname(filePath)
    while (dir !== this.skillsDir && dir.startsWith(this.skillsDir)) {
      try {
        const entries = await readdir(dir)
        if (entries.length > 0) break
        await rmdir(dir)
        dir = dirname(dir)
      } catch {
        break
      }
    }

    return true
  }

  async list(filter?: { tags?: string[]; type?: string }): Promise<SkillSpec[]> {
    const specs: SkillSpec[] = []
    await this.scanDir(this.skillsDir, specs)

    let result = specs

    if (filter?.tags && filter.tags.length > 0) {
      const tagSet = new Set(filter.tags)
      result = result.filter((s) => s.tags.some((t) => tagSet.has(t)))
    }

    if (filter?.type) {
      result = result.filter((s) => s.type === filter.type)
    }

    return result
  }

  async resolve(skillIds: string[]): Promise<ResolvedSkill[]> {
    const results: ResolvedSkill[] = []

    for (const id of skillIds) {
      const skill = await this.get(id)
      if (skill) {
        results.push(skill)
      } else {
        console.warn(`Skill not found: ${id}`)
      }
    }

    return results
  }

  async buildSkillPrompt(
    skillIds: string[],
    args?: { arguments?: string; argumentList?: string[] },
  ): Promise<string> {
    const skills = await this.resolve(skillIds)

    return skills
      .map(({ spec, content, dir, supportingFiles }) => {
        let processed = content

        processed = this.processArgumentSubstitution(processed, args)
        processed = this.processDynamicInjection(processed, dir)

        const header = `## Skill: ${spec.description}`
        const meta: string[] = []
        if (spec.type !== "reference") meta.push(`Type: ${spec.type}`)
        if (spec.whenToUse) meta.push(`When to use: ${spec.whenToUse}`)
        if (spec.allowedTools) meta.push(`Allowed tools: ${spec.allowedTools.join(", ")}`)
        if (supportingFiles && supportingFiles.length > 0) {
          meta.push(`Supporting files: ${supportingFiles.join(", ")}`)
        }
        const metaBlock = meta.length > 0 ? meta.join("\n") + "\n\n" : ""

        return `${header}\n${metaBlock}${processed}`
      })
      .join("\n\n---\n\n")
  }

  async readSupportingFile(skillId: string, filename: string): Promise<string | undefined> {
    const skill = await this.get(skillId)
    if (!skill?.dir) return undefined

    try {
      return await readFile(join(skill.dir, filename), "utf-8")
    } catch {
      return undefined
    }
  }

  processArgumentSubstitution(
    content: string,
    args?: { arguments?: string; argumentList?: string[] },
  ): string {
    if (!args) return content

    let result = content

    if (args.arguments !== undefined) {
      result = result.replace(/\$ARGUMENTS/g, args.arguments)
    }

    if (args.argumentList) {
      for (let i = 0; i < args.argumentList.length; i++) {
        result = result.replace(new RegExp(`\\$ARGUMENTS\\[${i}\\]`, "g"), args.argumentList[i])
        result = result.replace(new RegExp(`\\$${i}(?![0-9])`, "g"), args.argumentList[i])
      }
    }

    if (args.arguments !== undefined && !content.includes("$ARGUMENTS")) {
      result += `\n\nARGUMENTS: ${args.arguments}`
    }

    return result
  }

  processDynamicInjection(content: string, skillDir?: string): string {
    return content.replace(/!\`([^`]+)\`/g, (_match, command: string) => {
      try {
        const cwd = skillDir ?? this.skillsDir
        const output = execSync(command, {
          cwd,
          encoding: "utf-8",
          timeout: 10_000,
          stdio: ["pipe", "pipe", "pipe"],
        })
        return output.trim()
      } catch (err) {
        return `[Command failed: ${command}]`
      }
    })
  }

  async validate(skillId: string): Promise<{ valid: boolean; errors: string[] }> {
    const errors: string[] = []

    const skill = await this.get(skillId)
    if (!skill) {
      return { valid: false, errors: [`Skill not found: ${skillId}`] }
    }

    const result = SkillSpecSchema.safeParse(skill.spec)
    if (!result.success) {
      for (const issue of result.error.issues) {
        errors.push(`${issue.path.join(".")}: ${issue.message}`)
      }
      return { valid: false, errors }
    }

    if (skill.spec.context === "fork" && !skill.spec.agent) {
      errors.push("Skills with context:fork should specify an agent type")
    }

    if (skill.spec.arguments && skill.content.includes("$ARGUMENTS")) {
      const hasAll = skill.spec.arguments
        .filter((a) => a.required)
        .every((_, i) => skill.content.includes(`$${i}`) || skill.content.includes(`$ARGUMENTS[${i}]`))
      if (!hasAll) {
        errors.push("Required arguments declared but not all referenced in content")
      }
    }

    return { valid: errors.length === 0, errors }
  }

  private resolveLegacyPath(skillId: string): string {
    return join(this.skillsDir, `${skillId}.md`)
  }

  private async listSupportingFiles(baseDir: string, dir: string, results: string[]): Promise<void> {
    let entries: string[]
    try {
      entries = await readdir(dir)
    } catch {
      return
    }

    for (const entry of entries) {
      if (entry === "SKILL.md") continue
      const fullPath = join(dir, entry)
      const info = await stat(fullPath)

      if (info.isDirectory()) {
        await this.listSupportingFiles(baseDir, fullPath, results)
      } else {
        results.push(relative(baseDir, fullPath))
      }
    }
  }

  private async scanDir(dir: string, results: SkillSpec[]): Promise<void> {
    let entries: string[]
    try {
      entries = await readdir(dir)
    } catch {
      return
    }

    for (const entry of entries) {
      const fullPath = join(dir, entry)
      const info = await stat(fullPath)

      if (info.isDirectory()) {
        const skillMd = join(fullPath, "SKILL.md")
        try {
          const raw = await readFile(skillMd, "utf-8")
          const parsed = matter(raw)
          const skillId = relative(this.skillsDir, fullPath)
          const spec = SkillSpecSchema.parse({ ...parsed.data, id: skillId })
          results.push(spec)
        } catch {
          await this.scanDir(fullPath, results)
        }
      } else if (entry.endsWith(".md")) {
        try {
          const raw = await readFile(fullPath, "utf-8")
          const parsed = matter(raw)
          const skillId = relative(this.skillsDir, fullPath).replace(/\.md$/, "")
          const spec = SkillSpecSchema.parse({ ...parsed.data, id: skillId })
          results.push(spec)
        } catch {
          // skip malformed
        }
      }
    }
  }

  private cleanFrontmatter(fields: Record<string, unknown>): Record<string, unknown> {
    const cleaned: Record<string, unknown> = {}
    for (const [key, value] of Object.entries(fields)) {
      if (value === undefined) continue
      if (Array.isArray(value) && value.length === 0) continue
      if (typeof value === "string" && value === "") continue
      if (key === "invocation") {
        const inv = value as { modelCanInvoke: boolean; userCanInvoke: boolean }
        if (inv.modelCanInvoke && inv.userCanInvoke) continue
      }
      if (key === "context" && value === "inline") continue
      if (key === "type" && value === "reference") continue
      cleaned[key] = value
    }
    return cleaned
  }
}

export function getDefaultSkillManager(baseDir?: string): SkillManager {
  const dir = baseDir ? join(baseDir, "skills") : join(process.cwd(), "skills")
  return new SkillManager(dir)
}
