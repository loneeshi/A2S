/**
 * Parallel Benchmark Runner — runs episodes across N workers concurrently.
 *
 * Architecture:
 *   1. Spawn N Python bridge servers (ports 8765..8765+N-1)
 *   2. Create N isolated baseDirs: runs/w0, runs/w1, ... (copy agents/skills/tools)
 *   3. Each worker has its own TreeRuntime + BenchmarkBridge (independent memory)
 *   4. Episodes distributed round-robin across workers
 *   5. Each worker runs: episode → record → reflect → extend → evolve skills
 *   6. After all episodes: merge worker dirs back into main workspace
 *
 * Usage:
 *   npx tsx examples/run_benchmark_parallel.ts --benchmark alfworld --episodes 30 --parallel 3
 *   npx tsx examples/run_benchmark_parallel.ts --benchmark alfworld --episodes 10 --parallel 3 --extend --no-auto-start
 *
 * Options:
 *   --benchmark   alfworld | stulife            (default: alfworld)
 *   --episodes    total number of episodes      (default: 10)
 *   --parallel    number of concurrent workers   (default: 3)
 *   --model       LLM model name                (default: gpt-4o-mini)
 *   --max-steps   max tool calls per episode     (default: 30)
 *   --extend      enable auto-extension          (default: false)
 *   --evolve      enable skill evolution          (default: false, implies --extend)
 *   --split       ALFWorld split                 (default: train)
 *   --no-auto-start  don't auto-start Python servers (connect to existing)
 *   --base-port   first server port              (default: 8765)
 *   --cleanup     delete worker dirs after merge   (default: false)
 */

import { TreeRuntime } from "../src/runtime/tree"
import { BenchmarkBridge } from "../src/bridge/client"
import { SkillEvolutionEngine } from "../src/skill/evolution"
import { WorkspaceMerger } from "../src/utils/merge"
import { SkillManager } from "../src/skill/manager"
import { join } from "node:path"
import { cp, mkdir, rm, writeFile, appendFile } from "node:fs/promises"
import type { ReflectionOutput } from "../src/reflection/types"

const BASE_DIR = join(import.meta.dirname ?? __dirname, "..")
const PROJECT_ROOT = join(BASE_DIR, "..")
const RUNS_DIR = join(BASE_DIR, "runs")

// ─── Config ────────────────────────────────────────────────────────────

interface Config {
  benchmark: "alfworld" | "stulife"
  episodes: number
  parallel: number
  model: string
  maxSteps: number
  extend: boolean
  evolve: boolean
  split: string
  autoStart: boolean
  basePort: number
  cleanup: boolean
}

interface EpisodeResult {
  workerId: number
  episode: number
  task: string
  taskType: string
  success: boolean
  steps: number
  agentUsed: string
  error?: string
}

function parseArgs(): Config {
  const args = process.argv.slice(2)
  const c: Config = {
    benchmark: "alfworld",
    episodes: 10,
    parallel: 3,
    model: "gpt-4o-mini",
    maxSteps: 50,
    extend: false,
    evolve: false,
    split: "train",
    autoStart: true,
    basePort: 8765,
    cleanup: false,
  }
  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case "--benchmark":   c.benchmark = args[++i] as "alfworld" | "stulife"; break
      case "--episodes":    c.episodes = parseInt(args[++i], 10); break
      case "--parallel":    c.parallel = parseInt(args[++i], 10); break
      case "--model":       c.model = args[++i]; break
      case "--max-steps":   c.maxSteps = parseInt(args[++i], 10); break
      case "--extend":      c.extend = true; break
      case "--evolve":      c.evolve = true; c.extend = true; break
      case "--split":       c.split = args[++i]; break
      case "--no-auto-start": c.autoStart = false; break
      case "--base-port":   c.basePort = parseInt(args[++i], 10); break
      case "--cleanup":     c.cleanup = true; break
    }
  }
  return c
}

// ─── Task classification ───────────────────────────────────────────────

function guessTaskType(task: string): string {
  const l = task.toLowerCase()
  if (l.includes("clean")) return "pick_clean_then_place"
  if (l.includes("heat")) return "pick_heat_then_place"
  if (l.includes("cool")) return "pick_cool_then_place"
  if (l.includes("put") || l.includes("place")) return "pick_and_place"
  if (l.includes("examine") || l.includes("look") || l.includes("find")) return "examine"
  if (l.includes("toggle") || l.includes("turn")) return "toggle"
  return "unknown"
}

// ─── Worker setup ──────────────────────────────────────────────────────

interface Worker {
  id: number
  dir: string
  tree: TreeRuntime
  bridge: BenchmarkBridge
  skillEvolution: SkillEvolutionEngine | null
  reflections: ReflectionOutput[]
  results: EpisodeResult[]
}

async function createWorkerDir(workerId: number): Promise<string> {
  const dir = join(RUNS_DIR, `w${workerId}`)
  await rm(dir, { recursive: true, force: true })
  await mkdir(dir, { recursive: true })

  // Copy agents, skills, tools (lightweight — only .md and .json files)
  for (const sub of ["agents", "skills", "tools"]) {
    try {
      await cp(join(BASE_DIR, sub), join(dir, sub), { recursive: true })
    } catch {
      await mkdir(join(dir, sub), { recursive: true })
    }
  }

  // Create empty memory dir
  await mkdir(join(dir, "memory"), { recursive: true })

  return dir
}

async function createWorker(
  workerId: number,
  config: Config,
  skipEpisodes: number = 0,
): Promise<Worker> {
  const dir = await createWorkerDir(workerId)
  const port = config.basePort + workerId

  const bridge = new BenchmarkBridge({
    benchmark: config.benchmark,
    port,
    autoStart: config.autoStart,
    split: config.split,
    skip: skipEpisodes,
    projectRoot: PROJECT_ROOT,
  })

  const apiKey = process.env.OPENAI_API_KEY!
  const baseURL = process.env.OPENAI_BASE_URL || undefined

  const tree = new TreeRuntime({
    baseDir: dir,
    llmOptions: { apiKey, baseURL, defaultModel: config.model },
    toolHandlers: bridge.createToolHandlers(),
    extensionThreshold: config.extend ? 0.5 : undefined,
  })

  tree.registerDelegateTool({
    managerId: "alfworld_manager",
    successCheck: () => bridge.getIsDone(),
    runOptions: { maxIterations: 25, model: config.model },
  })

  const skillEvolution = config.evolve
    ? new SkillEvolutionEngine({
        baseDir: dir,
        skillManager: new SkillManager(join(dir, "skills")),
        llm: tree.getLLM(),
        failureThreshold: 0.5,
        minFailures: 2,
      })
    : null

  return {
    id: workerId,
    dir,
    tree,
    bridge,
    skillEvolution,
    reflections: [],
    results: [],
  }
}

// ─── Episode execution ─────────────────────────────────────────────────

function selectManager(benchmark: string): string {
  if (benchmark === "alfworld") return "alfworld_manager"
  if (benchmark === "stulife") return "stulife_coordinator"
  return "alfworld_manager"
}

async function runEpisode(
  worker: Worker,
  episodeNum: number,
  config: Config,
): Promise<EpisodeResult> {
  const resetResult = await worker.bridge.reset()
  const task = resetResult.task
  const taskType = guessTaskType(task)
  const managerId = selectManager(config.benchmark)

  const admissible = resetResult.admissible_commands
  const admissibleHint =
    admissible.length > 0
      ? `\n\nAdmissible commands: ${admissible.slice(0, 15).join(", ")}${admissible.length > 15 ? ` ... +${admissible.length - 15} more` : ""}`
      : ""
  const input = `Task: ${task}${admissibleHint}\n\nDecompose this task into subtasks and delegate to your workers. Pass environment state between workers.`

  let steps = 0
  let success = false
  let error: string | undefined

  const logLine = (msg: string) =>
    console.log(`  [w${worker.id}] ep${episodeNum}: ${msg}`)

  logLine(`${taskType} → ${managerId}`)

  try {
    const result = await worker.tree.run(managerId, input, {
      maxIterations: config.maxSteps,
      model: config.model,
      onToolCall: (name) => {
        steps++
        if (name === "delegate") logLine(`  delegate #${steps}`)
      },
    })
    success = worker.bridge.getIsDone()
  } catch (err) {
    error = err instanceof Error ? err.message : String(err)
  }

  logLine(`${success ? "✓" : "✗"} (${steps} delegate calls)`)

  worker.tree.monitor.record({
    taskId: `ep_${episodeNum}`,
    taskType,
    agentUsed: managerId,
    success,
    errorMessage: success ? undefined : (error ?? `Task not completed in ${steps} steps`),
    metadata: { episode: episodeNum },
  })

  return { workerId: worker.id, episode: episodeNum, task, taskType, success, steps, agentUsed: managerId, error }
}

// ─── Worker loop ───────────────────────────────────────────────────────

async function runWorkerLoop(
  worker: Worker,
  episodes: number[],
  config: Config,
): Promise<void> {
  await worker.bridge.start()
  await worker.tree.loadAll()

  for (const ep of episodes) {
    const result = await runEpisode(worker, ep, config)
    worker.results.push(result)

    // Reflection + memory on failure (includes max-step timeout, not just exceptions)
    if (!result.success) {
      const agent = worker.tree.get(result.agentUsed)
      const errorMsg = result.error ?? `Timeout: task not completed within max iterations (${result.steps}/${config.maxSteps} steps used)`
      const failure = {
        domain: agent?.spec.metadata?.domain as string ?? "unknown",
        taskType: result.taskType,
        agentId: result.agentUsed,
        errorMessage: errorMsg,
        actionHistory: [],
        toolsUsed: [],
        successRate: worker.results.filter((r) => r.success).length / worker.results.length,
      }
      const refs = await worker.tree.reflection.analyzeBatch([failure])
      await worker.tree.reflection.applyToMemory(refs)
      worker.reflections.push(...refs)
    }

    // Extension + skill evolution check every N episodes
    const CHECK_INTERVAL = 5
    if (config.extend && worker.results.length % CHECK_INTERVAL === 0 && worker.results.length >= CHECK_INTERVAL) {
      const newAgents = await worker.tree.checkAndExtend()
      if (newAgents > 0) {
        console.log(`  [w${worker.id}] extended tree: +${newAgents} agent(s)`)
      }

      if (worker.skillEvolution && worker.reflections.length >= 2) {
        const stats = worker.tree.monitor.getStats()
        const evolved = await worker.skillEvolution.evolve(worker.reflections, stats)
        if (evolved.length > 0) {
          console.log(`  [w${worker.id}] evolved skills: ${evolved.map((e) => e.skillId).join(", ")}`)
          // Reload agents to pick up new skill assignments
          await worker.tree.reload()
        }
        // Clear reflections that have been processed
        worker.reflections = []
      }
    }
  }

  // Don't shut down bridge if not auto-started
  if (config.autoStart) {
    await worker.bridge.stop()
  }
}

// ─── Summary & merge ───────────────────────────────────────────────────

function printSummary(results: EpisodeResult[]): void {
  const total = results.length
  const wins = results.filter((r) => r.success).length
  console.log(`\n${"═".repeat(60)}`)
  console.log(`  Total:   ${wins}/${total} (${((wins / total) * 100).toFixed(1)}%)`)
  console.log(`  Steps:   avg ${(results.reduce((s, r) => s + r.steps, 0) / total).toFixed(1)}`)

  const byType = new Map<string, { wins: number; total: number }>()
  for (const r of results) {
    const e = byType.get(r.taskType) ?? { wins: 0, total: 0 }
    e.total++
    if (r.success) e.wins++
    byType.set(r.taskType, e)
  }
  console.log("\n  By task type:")
  for (const [type, s] of byType) {
    console.log(`    ${type.padEnd(25)} ${s.wins}/${s.total} (${((s.wins / s.total) * 100).toFixed(0)}%)`)
  }

  const byAgent = new Map<string, { wins: number; total: number }>()
  for (const r of results) {
    const e = byAgent.get(r.agentUsed) ?? { wins: 0, total: 0 }
    e.total++
    if (r.success) e.wins++
    byAgent.set(r.agentUsed, e)
  }
  console.log("\n  By agent:")
  for (const [agent, s] of byAgent) {
    console.log(`    ${agent.padEnd(25)} ${s.wins}/${s.total} (${((s.wins / s.total) * 100).toFixed(0)}%)`)
  }

  const byWorker = new Map<number, { wins: number; total: number }>()
  for (const r of results) {
    const e = byWorker.get(r.workerId) ?? { wins: 0, total: 0 }
    e.total++
    if (r.success) e.wins++
    byWorker.set(r.workerId, e)
  }
  console.log("\n  By worker:")
  for (const [wid, s] of byWorker) {
    console.log(`    w${wid}                       ${s.wins}/${s.total} (${((s.wins / s.total) * 100).toFixed(0)}%)`)
  }
}

// ─── Main ──────────────────────────────────────────────────────────────

async function main() {
  const config = parseArgs()

  console.log("═══ AgentTree Parallel Benchmark Runner ═══")
  console.log(`  Benchmark: ${config.benchmark}`)
  console.log(`  Episodes:  ${config.episodes}`)
  console.log(`  Workers:   ${config.parallel}`)
  console.log(`  Model:     ${config.model}`)
  console.log(`  Max steps: ${config.maxSteps}`)
  console.log(`  Extension: ${config.extend ? "on" : "off"}`)
  console.log(`  Skill evo: ${config.evolve ? "on" : "off"}`)
  console.log(`  Ports:     ${config.basePort}..${config.basePort + config.parallel - 1}`)

  const apiKey = process.env.OPENAI_API_KEY
  if (!apiKey) {
    console.error("\nError: OPENAI_API_KEY required.")
    process.exit(1)
  }

  // Distribute episodes contiguously (for disjoint ALFWorld game coverage)
  // Worker 0: [1..ceil(N/P)], Worker 1: [ceil(N/P)+1..2*ceil(N/P)], etc.
  const assignments: number[][] = Array.from({ length: config.parallel }, () => [])
  const perWorker = Math.ceil(config.episodes / config.parallel)
  for (let ep = 1; ep <= config.episodes; ep++) {
    const workerIdx = Math.min(Math.floor((ep - 1) / perWorker), config.parallel - 1)
    assignments[workerIdx].push(ep)
  }

  console.log(`\n  Episode distribution:`)
  for (let i = 0; i < config.parallel; i++) {
    console.log(`    w${i}: episodes ${assignments[i][0]}..${assignments[i][assignments[i].length - 1]} (${assignments[i].length} total, skip ${i * perWorker} games)`)
  }

  // 1. Create workers
  console.log("\n1. Creating worker environments...")
  const workers: Worker[] = []
  for (let i = 0; i < config.parallel; i++) {
    const skipGames = i * perWorker
    const worker = await createWorker(i, config, skipGames)
    workers.push(worker)
    console.log(`   w${i}: ${worker.dir} (port ${config.basePort + i})`)
  }

  // 2. Run all workers in parallel
  console.log(`\n2. Running ${config.episodes} episodes across ${config.parallel} workers...\n`)
  const startTime = Date.now()

  await Promise.all(
    workers.map((worker, i) => runWorkerLoop(worker, assignments[i], config)),
  )

  const elapsed = ((Date.now() - startTime) / 1000).toFixed(1)

  // 3. Collect all results
  const allResults = workers.flatMap((w) => w.results).sort((a, b) => a.episode - b.episode)

  console.log(`\n3. All episodes complete in ${elapsed}s`)
  printSummary(allResults)

  // 4. Merge back
  console.log("\n4. Merging worker results back to main workspace...")
  const merger = new WorkspaceMerger(BASE_DIR)

  for (const worker of workers) {
    const mergeResult = await merger.mergeFrom(worker.dir, `w${worker.id}`)
    const parts: string[] = []
    if (mergeResult.memoryEntries > 0) parts.push(`${mergeResult.memoryEntries} memory entries`)
    if (mergeResult.agentsCopied.length > 0) parts.push(`${mergeResult.agentsCopied.length} new agents`)
    if (mergeResult.agentsRenamed.length > 0) parts.push(`${mergeResult.agentsRenamed.length} renamed agents`)
    if (mergeResult.skillsCopied.length > 0) parts.push(`${mergeResult.skillsCopied.length} new skills`)
    if (mergeResult.skillsDeduped.length > 0) parts.push(`${mergeResult.skillsDeduped.length} deduped skills`)
    if (parts.length > 0) {
      console.log(`   w${worker.id}: ${parts.join(", ")}`)
    } else {
      console.log(`   w${worker.id}: nothing new to merge`)
    }
  }

  // 5. Save results JSON
  const resultsDir = join(BASE_DIR, "results")
  await mkdir(resultsDir, { recursive: true })
  const ts = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19)
  const resultsPath = join(resultsDir, `${config.benchmark}_${ts}.json`)
  await writeFile(
    resultsPath,
    JSON.stringify(
      {
        config,
        timestamp: new Date().toISOString(),
        elapsedSeconds: parseFloat(elapsed),
        summary: {
          total: allResults.length,
          success: allResults.filter((r) => r.success).length,
          rate: allResults.filter((r) => r.success).length / allResults.length,
        },
        episodes: allResults,
      },
      null,
      2,
    ),
    "utf-8",
  )
  console.log(`\n   Results saved: ${resultsPath}`)

  // 6. Cleanup worker dirs
  if (config.cleanup) {
    console.log("\n5. Cleaning up worker directories...")
    for (const w of workers) {
      await rm(w.dir, { recursive: true, force: true })
      console.log(`   Removed ${w.dir}`)
    }
  } else {
    console.log(`\n   Worker dirs preserved at ${RUNS_DIR}/ (use --cleanup to remove)`)
  }

  console.log("\n═══ Done ═══")
}

main().catch((err) => {
  console.error("Fatal:", err)
  process.exit(1)
})
