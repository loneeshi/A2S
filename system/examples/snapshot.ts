/**
 * Snapshot CLI — create, list, and compare agenttree snapshots.
 *
 * Usage:
 *   npx tsx examples/snapshot.ts create --benchmark alfworld --split eval_out_of_distribution --model gpt-4o-mini --phase pre
 *   npx tsx examples/snapshot.ts create --benchmark alfworld --split eval_out_of_distribution --model gpt-4o-mini --phase post --run-id <id>
 *   npx tsx examples/snapshot.ts list
 *   npx tsx examples/snapshot.ts diff --run-id <id>
 *   npx tsx examples/snapshot.ts show --run-id <id> --phase pre
 *
 * Special:
 *   npx tsx examples/snapshot.ts create-from-git --commit 0d3974a --benchmark alfworld --split train --model gpt-4o-mini --label initial
 */

import { SnapshotManager } from "../src/snapshot/manager"
import { join } from "node:path"
import { cp, mkdir, rm } from "node:fs/promises"
import { execSync } from "node:child_process"

const SYSTEM_DIR = join(import.meta.dirname ?? __dirname, "..")
const PROJECT_ROOT = join(SYSTEM_DIR, "..")
const TREES_DIR = join(PROJECT_ROOT, "trees")
const SNAPSHOTS_DIR = join(PROJECT_ROOT, "snapshots")

async function main() {
  const args = process.argv.slice(2)
  const command = args[0]

  // Extract --tree flag
  let treeName = "alfworld_full"
  const treeIdx = args.indexOf("--tree")
  if (treeIdx >= 0 && args[treeIdx + 1]) {
    treeName = args[treeIdx + 1]
  }
  const treeDir = join(TREES_DIR, treeName)

  const mgr = new SnapshotManager(treeDir, SNAPSHOTS_DIR)

  switch (command) {
    case "create":
      await cmdCreate(mgr, args.slice(1))
      break
    case "create-from-git":
      await cmdCreateFromGit(mgr, args.slice(1))
      break
    case "list":
      await cmdList(mgr)
      break
    case "diff":
      await cmdDiff(mgr, args.slice(1))
      break
    case "show":
      await cmdShow(mgr, args.slice(1))
      break
    default:
      printUsage()
  }
}

function parseFlags(args: string[]): Record<string, string> {
  const flags: Record<string, string> = {}
  for (let i = 0; i < args.length; i++) {
    if (args[i].startsWith("--")) {
      const key = args[i].slice(2)
      flags[key] = args[i + 1] ?? "true"
      i++
    }
  }
  return flags
}

async function cmdCreate(mgr: SnapshotManager, args: string[]) {
  const flags = parseFlags(args)
  const benchmark = flags.benchmark ?? "alfworld"
  const split = flags.split ?? "train"
  const model = flags.model ?? "gpt-4o-mini"
  const phase = (flags.phase ?? "pre") as "pre" | "post"

  const config = { benchmark, split, model }

  let runId = flags["run-id"]
  if (!runId) {
    runId = mgr.createRunId(config)
  }

  console.log(`Creating ${phase} snapshot: ${runId}`)

  if (phase === "pre") {
    const dir = await mgr.snapshotPre(runId, config)
    console.log(`  Saved to: ${dir}`)
  } else {
    const dir = await mgr.snapshotPost(runId, config)
    console.log(`  Saved to: ${dir}`)
  }

  const manifest = await mgr.getManifest(runId, phase)
  console.log(`  Agents: ${manifest.agents.length}`)
  console.log(`    ${manifest.agents.map((a) => a.id).join(", ")}`)
  console.log(`  Skills: ${manifest.skills.length}`)
  console.log(`    ${manifest.skills.map((s) => s.id).join(", ")}`)
  console.log(`  Memory files: ${manifest.memoryFiles.length}`)
  for (const m of manifest.memoryFiles) {
    console.log(`    ${m.agent}: ${m.entries} entries (${(m.sizeBytes / 1024).toFixed(1)} KB)`)
  }
  console.log(`  memory.db: ${manifest.hasMemoryDb ? "yes" : "no"}`)
  console.log(`  vector_store.db: ${manifest.hasVectorStoreDb ? "yes" : "no"}`)
  console.log(`  Git: ${manifest.gitCommit} (${manifest.gitBranch})`)
  console.log(`\n  Run ID: ${runId}`)
}

async function cmdCreateFromGit(mgr: SnapshotManager, args: string[]) {
  const flags = parseFlags(args)
  const commit = flags.commit
  if (!commit) {
    console.error("Error: --commit is required")
    process.exit(1)
  }

  const benchmark = flags.benchmark ?? "alfworld"
  const split = flags.split ?? "train"
  const model = flags.model ?? "gpt-4o-mini"
  const label = flags.label ?? commit
  const phase = (flags.phase ?? "pre") as "pre" | "post"

  const runId = flags["run-id"] ?? `${benchmark}_${split}_${model.replace(/[/\\:]/g, "-")}_${label}`

  console.log(`Creating snapshot from git commit ${commit}...`)

  // Extract files from the git commit into a temp dir
  const tempDir = join(SYSTEM_DIR, ".snapshot-temp")
  await rm(tempDir, { recursive: true, force: true })
  await mkdir(tempDir, { recursive: true })

  try {
    // Extract agents
    await mkdir(join(tempDir, "agents"), { recursive: true })
    const agentFiles = execSync(`git ls-tree -r ${commit} --name-only -- agenttree/agents/`, {
      cwd: PROJECT_ROOT,
      encoding: "utf-8",
    }).trim().split("\n").filter(Boolean)

    for (const file of agentFiles) {
      const basename = file.split("/").pop()!
      const content = execSync(`git show ${commit}:${file}`, {
        cwd: PROJECT_ROOT,
        encoding: "utf-8",
      })
      const { writeFile } = await import("node:fs/promises")
      await writeFile(join(tempDir, "agents", basename), content, "utf-8")
    }

    // Extract skills
    const skillFiles = execSync(`git ls-tree -r ${commit} --name-only -- agenttree/skills/`, {
      cwd: PROJECT_ROOT,
      encoding: "utf-8",
    }).trim().split("\n").filter(Boolean)

    for (const file of skillFiles) {
      const relPath = file.replace("agenttree/skills/", "")
      const dirPart = relPath.split("/").slice(0, -1).join("/")
      if (dirPart) {
        await mkdir(join(tempDir, "skills", dirPart), { recursive: true })
      }
      const content = execSync(`git show ${commit}:${file}`, {
        cwd: PROJECT_ROOT,
        encoding: "utf-8",
      })
      const { writeFile } = await import("node:fs/promises")
      await writeFile(join(tempDir, "skills", relPath), content, "utf-8")
    }

    // No memory/db files in git (gitignored), create empty memory dir
    await mkdir(join(tempDir, "memory"), { recursive: true })

    // Create snapshot from the temp dir
    const tempMgr = new SnapshotManager(tempDir, SNAPSHOTS_DIR)
    if (phase === "pre") {
      await tempMgr.snapshotPre(runId, { benchmark, split, model })
    } else {
      await tempMgr.snapshotPost(runId, { benchmark, split, model })
    }

    const manifest = await mgr.getManifest(runId, phase)
    console.log(`  Created ${phase} snapshot: ${runId}`)
    console.log(`  Agents (${manifest.agents.length}): ${manifest.agents.map((a) => a.id).join(", ")}`)
    console.log(`  Skills (${manifest.skills.length}): ${manifest.skills.map((s) => s.id).join(", ")}`)
    console.log(`  Memory files: ${manifest.memoryFiles.length}`)
    console.log(`  Run ID: ${runId}`)
  } finally {
    await rm(tempDir, { recursive: true, force: true })
  }
}

async function cmdList(mgr: SnapshotManager) {
  const snapshots = await mgr.listSnapshots()
  if (snapshots.length === 0) {
    console.log("No snapshots found.")
    return
  }

  console.log(`Found ${snapshots.length} snapshot(s):\n`)
  for (const id of snapshots) {
    let preInfo = ""
    let postInfo = ""
    try {
      const pre = await mgr.getManifest(id, "pre")
      preInfo = `  pre:  ${pre.agents.length} agents, ${pre.skills.length} skills, ${pre.memoryFiles.reduce((s, m) => s + m.entries, 0)} mem entries`
    } catch {
      preInfo = "  pre:  (none)"
    }
    try {
      const post = await mgr.getManifest(id, "post")
      postInfo = `  post: ${post.agents.length} agents, ${post.skills.length} skills, ${post.memoryFiles.reduce((s, m) => s + m.entries, 0)} mem entries`
    } catch {
      postInfo = "  post: (none)"
    }
    console.log(`  ${id}`)
    console.log(preInfo)
    console.log(postInfo)
    console.log()
  }
}

async function cmdDiff(mgr: SnapshotManager, args: string[]) {
  const flags = parseFlags(args)
  const runId = flags["run-id"]
  if (!runId) {
    console.error("Error: --run-id is required")
    process.exit(1)
  }

  console.log(`Generating diff for: ${runId}\n`)

  const diff = await mgr.generateDiff(runId)

  console.log("═══ Agent Changes ═══")
  if (diff.agents.added.length > 0) console.log(`  Added:     ${diff.agents.added.join(", ")}`)
  if (diff.agents.removed.length > 0) console.log(`  Removed:   ${diff.agents.removed.join(", ")}`)
  if (diff.agents.modified.length > 0) {
    console.log(`  Modified:`)
    for (const m of diff.agents.modified) {
      console.log(`    ${m.id} (${m.versionPre} → ${m.versionPost})`)
      for (const c of m.changes) console.log(`      ${c}`)
    }
  }
  if (diff.agents.unchanged.length > 0) console.log(`  Unchanged: ${diff.agents.unchanged.join(", ")}`)

  console.log("\n═══ Skill Changes ═══")
  if (diff.skills.added.length > 0) console.log(`  Added:     ${diff.skills.added.join(", ")}`)
  if (diff.skills.removed.length > 0) console.log(`  Removed:   ${diff.skills.removed.join(", ")}`)
  if (diff.skills.modified.length > 0) {
    console.log(`  Modified:`)
    for (const m of diff.skills.modified) {
      console.log(`    ${m.id} (${m.versionPre} → ${m.versionPost})`)
      for (const c of m.changes) console.log(`      ${c}`)
    }
  }
  if (diff.skills.unchanged.length > 0) console.log(`  Unchanged: ${diff.skills.unchanged.join(", ")}`)

  console.log("\n═══ Memory Changes ═══")
  console.log(`  Total entries added: ${diff.memory.totalEntriesAdded}`)
  if (diff.memory.post.length > 0) {
    console.log(`  Post-run memory:`)
    for (const m of diff.memory.post) {
      const pre = diff.memory.pre.find((p) => p.agent === m.agent)
      const delta = pre ? m.entries - pre.entries : m.entries
      console.log(`    ${m.agent}: ${m.entries} entries (+${delta})`)
    }
  }

  console.log("\n═══ Database Changes ═══")
  console.log(`  memory.db:       ${formatSize(diff.databases.memoryDbSizePre)} → ${formatSize(diff.databases.memoryDbSizePost)}`)
  console.log(`  vector_store.db: ${formatSize(diff.databases.vectorStoreDbSizePre)} → ${formatSize(diff.databases.vectorStoreDbSizePost)}`)

  console.log(`\n  Diff saved to: snapshots/${runId}/diff.json`)
}

async function cmdShow(mgr: SnapshotManager, args: string[]) {
  const flags = parseFlags(args)
  const runId = flags["run-id"]
  const phase = (flags.phase ?? "pre") as "pre" | "post"

  if (!runId) {
    console.error("Error: --run-id is required")
    process.exit(1)
  }

  const manifest = await mgr.getManifest(runId, phase)

  console.log(`═══ Snapshot: ${runId} (${phase}) ═══\n`)
  console.log(`  Timestamp:  ${manifest.timestamp}`)
  console.log(`  Benchmark:  ${manifest.benchmark}`)
  console.log(`  Split:      ${manifest.split}`)
  console.log(`  Model:      ${manifest.model}`)
  console.log(`  Git:        ${manifest.gitCommit} (${manifest.gitBranch})`)

  console.log(`\n  Agents (${manifest.agents.length}):`)
  for (const a of manifest.agents) {
    console.log(`    ${a.id.padEnd(30)} role=${a.role.padEnd(12)} v${a.version}  ${formatSize(a.sizeBytes)}`)
  }

  console.log(`\n  Skills (${manifest.skills.length}):`)
  for (const s of manifest.skills) {
    const auto = s.autoGenerated ? " [auto]" : ""
    console.log(`    ${s.id.padEnd(40)} v${s.version}  ${formatSize(s.sizeBytes)}${auto}`)
  }

  console.log(`\n  Memory (${manifest.memoryFiles.length} files):`)
  for (const m of manifest.memoryFiles) {
    console.log(`    ${m.agent.padEnd(30)} ${m.entries} entries  ${formatSize(m.sizeBytes)}`)
  }

  console.log(`\n  Databases:`)
  console.log(`    memory.db:       ${manifest.hasMemoryDb ? "yes" : "no"}`)
  console.log(`    vector_store.db: ${manifest.hasVectorStoreDb ? "yes" : "no"}`)
}

function formatSize(bytes: number): string {
  if (bytes === 0) return "0 B"
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function printUsage() {
  console.log(`
Snapshot CLI — create, list, and compare agenttree snapshots.

Commands:
  create           Create a snapshot of the current workspace state
    --benchmark    Benchmark name (default: alfworld)
    --split        Data split (default: train)
    --model        Model name (default: gpt-4o-mini)
    --phase        pre | post (default: pre)
    --run-id       Existing run ID (for adding post to existing pre)

  create-from-git  Create a snapshot from a git commit
    --commit       Git commit hash (required)
    --benchmark    Benchmark name
    --split        Data split
    --model        Model name
    --phase        pre | post (default: pre)
    --label        Label for the snapshot (default: commit hash)

  list             List all snapshots

  diff             Generate and display diff between pre and post
    --run-id       Run ID (required)

  show             Show details of a snapshot phase
    --run-id       Run ID (required)
    --phase        pre | post (default: pre)
  `)
}

main().catch((err) => {
  console.error("Error:", err)
  process.exit(1)
})
