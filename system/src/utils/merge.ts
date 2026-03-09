/**
 * WorkspaceMerger — merges isolated worker baseDirs back into the main workspace.
 *
 * After parallel benchmark runs, each worker has its own:
 *   - memory/*.jsonl   (agent memories)
 *   - agents/*.md      (potentially new agents from extension)
 *   - skills/**\/*.md   (potentially new skills from evolution)
 *
 * Merge strategy:
 *   - Memory:  JSONL append (interleave is fine, MemoryStore handles by timestamp)
 *   - Agents:  Copy new .md files; on conflict rename with __w{N} suffix
 *   - Skills:  Copy new .md files; on conflict rename with __w{N} suffix; dedup by content hash
 */

import {
  readdir,
  readFile,
  appendFile,
  copyFile,
  stat,
  mkdir,
} from "node:fs/promises"
import { join, relative } from "node:path"
import { createHash } from "node:crypto"

export interface MergeResult {
  memoryFiles: number
  memoryEntries: number
  agentsCopied: string[]
  agentsRenamed: string[]
  skillsCopied: string[]
  skillsDeduped: string[]
}

export class WorkspaceMerger {
  constructor(private mainDir: string) {}

  async mergeFrom(
    workerDir: string,
    workerId: string,
  ): Promise<MergeResult> {
    const result: MergeResult = {
      memoryFiles: 0,
      memoryEntries: 0,
      agentsCopied: [],
      agentsRenamed: [],
      skillsCopied: [],
      skillsDeduped: [],
    }

    await this.mergeMemory(workerDir, result)
    await this.mergeAgents(workerDir, workerId, result)
    await this.mergeSkills(workerDir, workerId, result)

    return result
  }

  private async mergeMemory(
    workerDir: string,
    result: MergeResult,
  ): Promise<void> {
    const workerMemDir = join(workerDir, "memory")
    const mainMemDir = join(this.mainDir, "memory")
    await mkdir(mainMemDir, { recursive: true })

    let files: string[]
    try {
      files = await readdir(workerMemDir)
    } catch {
      return
    }

    for (const file of files) {
      if (!file.endsWith(".jsonl")) continue
      const workerPath = join(workerMemDir, file)
      const mainPath = join(mainMemDir, file)

      const content = await readFile(workerPath, "utf-8")
      const lines = content.trim().split("\n").filter(Boolean)
      if (lines.length === 0) continue

      await appendFile(mainPath, "\n" + lines.join("\n") + "\n", "utf-8")
      result.memoryFiles++
      result.memoryEntries += lines.length
    }
  }

  private async mergeAgents(
    workerDir: string,
    workerId: string,
    result: MergeResult,
  ): Promise<void> {
    const workerAgentsDir = join(workerDir, "agents")
    const mainAgentsDir = join(this.mainDir, "agents")
    await mkdir(mainAgentsDir, { recursive: true })

    let files: string[]
    try {
      files = await readdir(workerAgentsDir)
    } catch {
      return
    }

    const mainFiles = new Set<string>()
    try {
      const existing = await readdir(mainAgentsDir)
      for (const f of existing) mainFiles.add(f)
    } catch {
      // empty
    }

    for (const file of files) {
      if (!file.endsWith(".md")) continue
      const srcPath = join(workerAgentsDir, file)

      if (!mainFiles.has(file)) {
        await copyFile(srcPath, join(mainAgentsDir, file))
        result.agentsCopied.push(file)
        continue
      }

      const srcContent = await readFile(srcPath, "utf-8")
      const mainContent = await readFile(
        join(mainAgentsDir, file),
        "utf-8",
      )

      if (this.hash(srcContent) === this.hash(mainContent)) {
        continue
      }

      const renamed = file.replace(/\.md$/, `__${workerId}.md`)
      await copyFile(srcPath, join(mainAgentsDir, renamed))
      result.agentsRenamed.push(`${file} → ${renamed}`)
    }
  }

  private async mergeSkills(
    workerDir: string,
    workerId: string,
    result: MergeResult,
  ): Promise<void> {
    const workerSkillsDir = join(workerDir, "skills")
    const mainSkillsDir = join(this.mainDir, "skills")
    await mkdir(mainSkillsDir, { recursive: true })

    const workerFiles = await this.walkDir(workerSkillsDir)

    for (const relPath of workerFiles) {
      if (!relPath.endsWith(".md")) continue
      const srcPath = join(workerSkillsDir, relPath)
      const destPath = join(mainSkillsDir, relPath)

      let destExists = false
      try {
        await stat(destPath)
        destExists = true
      } catch {
        // doesn't exist
      }

      if (!destExists) {
        await mkdir(join(mainSkillsDir, join(relPath, "..")), {
          recursive: true,
        })
        await copyFile(srcPath, destPath)
        result.skillsCopied.push(relPath)
        continue
      }

      const srcContent = await readFile(srcPath, "utf-8")
      const destContent = await readFile(destPath, "utf-8")

      if (this.hash(srcContent) === this.hash(destContent)) {
        result.skillsDeduped.push(relPath)
        continue
      }

      const renamed = relPath.replace(/\.md$/, `__${workerId}.md`)
      const renamedPath = join(mainSkillsDir, renamed)
      await mkdir(join(renamedPath, ".."), { recursive: true })
      await copyFile(srcPath, renamedPath)
      result.skillsCopied.push(`${relPath} → ${renamed}`)
    }
  }

  private async walkDir(dir: string): Promise<string[]> {
    const results: string[] = []

    let entries: string[]
    try {
      entries = await readdir(dir)
    } catch {
      return results
    }

    for (const entry of entries) {
      const fullPath = join(dir, entry)
      const info = await stat(fullPath)

      if (info.isDirectory()) {
        const sub = await this.walkDir(fullPath)
        for (const s of sub) {
          results.push(join(entry, s))
        }
      } else {
        results.push(entry)
      }
    }

    return results
  }

  private hash(content: string): string {
    return createHash("md5").update(content).digest("hex")
  }
}
