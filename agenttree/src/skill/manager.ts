import { readFile, writeFile, unlink, readdir, mkdir, rmdir, stat } from "node:fs/promises"
import { join, dirname, relative } from "node:path"
import matter from "gray-matter"
import { SkillSpecSchema } from "../spec/skill"
import type { SkillSpec } from "../spec/skill"

export class SkillManager {
  constructor(private skillsDir: string) {}

  private resolvePath(skillId: string): string {
    return join(this.skillsDir, `${skillId}.md`)
  }

  async create(spec: SkillSpec, content: string): Promise<void> {
    const validated = SkillSpecSchema.parse(spec)
    const filePath = this.resolvePath(validated.id)

    await mkdir(dirname(filePath), { recursive: true })

    const { id: _, ...frontmatterFields } = validated
    const md = matter.stringify(content, frontmatterFields)
    await writeFile(filePath, md, "utf-8")
  }

  async get(skillId: string): Promise<{ spec: SkillSpec; content: string } | undefined> {
    const filePath = this.resolvePath(skillId)

    let raw: string
    try {
      raw = await readFile(filePath, "utf-8")
    } catch {
      return undefined
    }

    const parsed = matter(raw)
    const spec = SkillSpecSchema.parse({ id: skillId, ...parsed.data })
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

    const filePath = this.resolvePath(skillId)
    const { id: _, ...frontmatterFields } = validated
    const md = matter.stringify(content, frontmatterFields)
    await writeFile(filePath, md, "utf-8")

    return true
  }

  async remove(skillId: string): Promise<boolean> {
    const filePath = this.resolvePath(skillId)

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

  async list(filter?: { tags?: string[] }): Promise<SkillSpec[]> {
    const specs: SkillSpec[] = []
    await this.scanDir(this.skillsDir, specs)

    if (filter?.tags && filter.tags.length > 0) {
      const tagSet = new Set(filter.tags)
      return specs.filter((s) => s.tags.some((t) => tagSet.has(t)))
    }

    return specs
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
        await this.scanDir(fullPath, results)
      } else if (entry.endsWith(".md")) {
        try {
          const raw = await readFile(fullPath, "utf-8")
          const parsed = matter(raw)
          const skillId = relative(this.skillsDir, fullPath).replace(/\.md$/, "")
          const spec = SkillSpecSchema.parse({ id: skillId, ...parsed.data })
          results.push(spec)
        } catch {
          // skip malformed files
        }
      }
    }
  }

  async resolve(skillIds: string[]): Promise<Array<{ spec: SkillSpec; content: string }>> {
    const results: Array<{ spec: SkillSpec; content: string }> = []

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

  async buildSkillPrompt(skillIds: string[]): Promise<string> {
    const skills = await this.resolve(skillIds)

    return skills
      .map(
        ({ spec, content }) =>
          `## Skill: ${spec.description}\nWhen to use: ${spec.whenToUse}\n\n${content}`,
      )
      .join("\n\n---\n\n")
  }

  async validate(skillId: string): Promise<{ valid: boolean; errors: string[] }> {
    const errors: string[] = []
    const filePath = this.resolvePath(skillId)

    let raw: string
    try {
      raw = await readFile(filePath, "utf-8")
    } catch {
      return { valid: false, errors: [`Skill file not found: ${filePath}`] }
    }

    let parsed: matter.GrayMatterFile<string>
    try {
      parsed = matter(raw)
    } catch {
      return { valid: false, errors: ["Failed to parse frontmatter"] }
    }

    const result = SkillSpecSchema.safeParse({ id: skillId, ...parsed.data })
    if (!result.success) {
      for (const issue of result.error.issues) {
        errors.push(`${issue.path.join(".")}: ${issue.message}`)
      }
      return { valid: false, errors }
    }

    return { valid: true, errors: [] }
  }
}

export function getDefaultSkillManager(baseDir?: string): SkillManager {
  const dir = baseDir ? join(baseDir, "skills") : join(process.cwd(), "skills")
  return new SkillManager(dir)
}
