/**
 * Parallel Benchmark Runner — runs episodes across N workers concurrently.
 *
 * Architecture:
 *   1. Spawn N Python bridge servers (ports 8765..8765+N-1)
 *   2. Create N isolated worker dirs: system/runs/{tree}/w0, w1, ... (copy agents/skills from tree, tools from system/)
 *   3. Each worker has its own TreeRuntime + BenchmarkBridge (independent memory)
 *   4. Episodes distributed contiguously across workers
 *   5. Each worker runs: episode → record → reflect → extend → evolve skills
 *   6. After all episodes: merge worker dirs into experiments/{run_id}/tree/final/
 *
 * Output layout:
 *   experiments/{run_id}/
 *     config.json        ← full run configuration + metadata
 *     tree/
 *       initial/         ← snapshot of agent tree at start (agents/, skills/)
 *       final/           ← agent tree after training (agents/, skills/, memory/)
 *     traces/            ← per-episode execution traces
 *     results.json       ← config + summary + per-episode results
 *
 * Directory layout:
 *   auto_expansion_agent/
 *     system/           ← framework code (this file lives in system/examples/)
 *       src/            ← TypeScript runtime
 *       tools/          ← shared tool definitions
 *       bridge/         ← Python bridge
 *       runs/           ← temp worker dirs
 *     trees/            ← agent tree definitions
 *       alfworld_full/  ← agents/, skills/, memory/
 *       alfworld_minimal/
 *     experiments/      ← self-contained experiment runs
 *
 * Usage:
 *   npx tsx examples/run_benchmark_parallel.ts --tree alfworld_full --benchmark alfworld --episodes 134 --parallel 3
 *   npx tsx examples/run_benchmark_parallel.ts --tree alfworld_minimal --extend --evolve --split eval_out_of_distribution
 *
 * Options:
 *   --tree        tree name under trees/             (required)
 *   --benchmark   alfworld | stulife                 (default: alfworld)
 *   --episodes    total number of episodes           (default: 10)
 *   --parallel    number of concurrent workers        (default: 3)
 *   --model       LLM model name                     (default: gpt-4o-mini)
 *   --max-steps   max tool calls per episode          (default: 50)
 *   --extend      enable auto-extension               (default: false)
 *   --evolve      enable skill evolution              (default: false, implies --extend)
 *   --mem0        enable Mem0 semantic memory          (default: false)
 *   --split       ALFWorld split                      (default: train)
 *   --no-auto-start  don't auto-start Python servers
 *   --base-port   first server port                   (default: 8765)
 *   --cleanup     delete worker dirs after merge      (default: false)
 *   --env-memory  enable environment memory            (default: false)
 *   --per-type N  stratified sampling: N episodes per task type (overrides --episodes)
 */

import { TreeRuntime } from "../src/runtime/tree"
import { BenchmarkBridge } from "../src/bridge/client"
import { SkillEvolutionEngine } from "../src/skill/evolution"
import { WorkspaceMerger } from "../src/utils/merge"
import { SkillManager } from "../src/skill/manager"
import { Mem0Bridge } from "../src/memory/mem0-bridge"
import { EnvironmentMemory, ALFWorldParser } from "../src/memory"
import type { EnvironmentMemoryConfig } from "../src/memory"
import { join, resolve } from "node:path"
import { cp, mkdir, rm, writeFile } from "node:fs/promises"
import type { ReflectionOutput } from "../src/reflection/types"

// ─── Path resolution ────────────────────────────────────────────────────

const SYSTEM_DIR = join(import.meta.dirname ?? __dirname, "..")
const PROJECT_ROOT = join(SYSTEM_DIR, "..")
const TREES_DIR = join(PROJECT_ROOT, "trees")
const TOOLS_DIR = join(SYSTEM_DIR, "tools")
const RUNS_DIR = join(SYSTEM_DIR, "runs")
const EXPERIMENTS_DIR = join(PROJECT_ROOT, "experiments")

import type { RunResult } from "../src/runtime/types"

// ─── Config ────────────────────────────────────────────────────────────

interface Config {
  tree: string
  benchmark: "alfworld" | "stulife"
  episodes: number
  parallel: number
  model: string
  maxSteps: number
  extend: boolean
  evolve: boolean
  mem0: boolean
  split: string
  autoStart: boolean
  basePort: number
  cleanup: boolean
  envMemory: boolean
  perType: number
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
  /** Full RunResult from the manager agent, stored separately in traces/ */
  runResult?: RunResult
}

function parseArgs(): Config {
  const args = process.argv.slice(2)
  const c: Config = {
    tree: "",
    benchmark: "alfworld",
    episodes: 10,
    parallel: 3,
    model: "gpt-4o-mini",
    maxSteps: 50,
    extend: false,
    evolve: false,
    mem0: false,
    split: "train",
    autoStart: true,
    basePort: 8765,
    cleanup: false,
    envMemory: false,
    perType: 0,
  }
  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case "--tree":        c.tree = args[++i]; break
      case "--benchmark":   c.benchmark = args[++i] as "alfworld" | "stulife"; break
      case "--episodes":    c.episodes = parseInt(args[++i], 10); break
      case "--parallel":    c.parallel = parseInt(args[++i], 10); break
      case "--model":       c.model = args[++i]; break
      case "--max-steps":   c.maxSteps = parseInt(args[++i], 10); break
      case "--extend":      c.extend = true; break
      case "--evolve":      c.evolve = true; c.extend = true; break
      case "--mem0":        c.mem0 = true; break
      case "--split":       c.split = args[++i]; break
      case "--no-auto-start": c.autoStart = false; break
      case "--base-port":   c.basePort = parseInt(args[++i], 10); break
      case "--cleanup":     c.cleanup = true; break
      case "--env-memory":  c.envMemory = true; break
      case "--per-type":    c.perType = parseInt(args[++i], 10); break
    }
  }
  if (!c.tree) {
    console.error("Error: --tree <name> is required (e.g. --tree alfworld_full)")
    console.error("Available trees:")
    try {
      const { readdirSync } = require("node:fs")
      const entries = readdirSync(TREES_DIR, { withFileTypes: true })
      for (const e of entries) {
        if (e.isDirectory()) console.error(`  - ${e.name}`)
      }
    } catch { /* ignore */ }
    process.exit(1)
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
  envMemory: EnvironmentMemory | null
  reflections: ReflectionOutput[]
  results: EpisodeResult[]
}

async function createWorkerDir(workerId: number, treeDir: string, treeName: string): Promise<string> {
  const dir = join(RUNS_DIR, treeName, `w${workerId}`)
  await rm(dir, { recursive: true, force: true })
  await mkdir(dir, { recursive: true })

  // Copy agents/skills from the tree
  for (const sub of ["agents", "skills"]) {
    try {
      await cp(join(treeDir, sub), join(dir, sub), { recursive: true })
    } catch {
      await mkdir(join(dir, sub), { recursive: true })
    }
  }

  // Copy tools from system/tools/ (shared across all trees)
  await cp(TOOLS_DIR, join(dir, "tools"), { recursive: true })

  // Create empty memory dir
  await mkdir(join(dir, "memory"), { recursive: true })

  return dir
}

async function createWorker(
  workerId: number,
  config: Config,
  treeDir: string,
  skipEpisodes: number = 0,
  mem0?: Mem0Bridge,
): Promise<Worker> {
  const dir = await createWorkerDir(workerId, treeDir, config.tree)
  const port = config.basePort + workerId

  const bridge = new BenchmarkBridge({
    benchmark: config.benchmark,
    port,
    autoStart: config.autoStart,
    split: config.split,
    skip: skipEpisodes,
    projectRoot: PROJECT_ROOT,
    stratifiedPerType: config.perType > 0 ? config.perType : undefined,
  })

  const apiKey = process.env.OPENAI_API_KEY!
  const baseURL = process.env.OPENAI_BASE_URL || undefined

  const tree = new TreeRuntime({
    baseDir: dir,
    toolsDir: join(dir, "tools"),
    llmOptions: { apiKey, baseURL, defaultModel: config.model },
    toolHandlers: bridge.createToolHandlers(),
    extensionThreshold: config.extend ? 0.5 : undefined,
    maxSteps: config.maxSteps,
    mem0,
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

  let envMemory: EnvironmentMemory | null = null
  if (config.envMemory) {
    envMemory = new EnvironmentMemory(
      { enabled: true, maxEntries: 500, consolidateEvery: 10, decayFactor: 0.95, backend: "local" },
      new ALFWorldParser(),
    )
    const envMemPath = join(dir, "memory", "environment.json")
    await envMemory.load(envMemPath)
  }

  return {
    id: workerId,
    dir,
    tree,
    bridge,
    skillEvolution,
    envMemory,
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

  let mem0Hint = ""
  const memMgr = worker.tree.getMemoryManager()
  if (memMgr.hasMem0()) {
    const memories = await memMgr.searchForManager(task, 3)
    if (memories.length > 0) {
      mem0Hint = `\n\n<past_experience>\n${memories.map((m) => `- ${m.content}`).join("\n")}\n</past_experience>`
    }
  }

  let envHint = ""
  if (worker.envMemory) {
    worker.envMemory.resetEpisodeState()
    const envRecall = worker.envMemory.recall(task)
    if (envRecall) {
      envHint = `\n\n<environment_knowledge>\n${envRecall}\n</environment_knowledge>`
    }
  }

  const input = `Task: ${task}${admissibleHint}${mem0Hint}${envHint}\n\nDecompose this task into subtasks and delegate to your workers. Pass environment state between workers.`

  let steps = 0
  let success = false
  let error: string | undefined
  let managerRunResult: RunResult | undefined

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
    managerRunResult = result
  } catch (err) {
    error = err instanceof Error ? err.message : String(err)
  }

  logLine(`${success ? "✓" : "✗"} (${steps} delegate calls)`)

  if (worker.envMemory && managerRunResult) {
    for (const tc of managerRunResult.toolCalls) {
      if (tc.subTrace) {
        for (const stc of tc.subTrace.toolCalls) {
          if (stc.tool.startsWith("env.")) {
            const action = `${stc.tool.replace("env.", "")} ${Object.values(stc.args).join(" ")}`.trim()
            worker.envMemory.observe(action, stc.result, episodeNum)
          }
        }
      }
    }
  }

  worker.tree.monitor.record({
    taskId: `ep_${episodeNum}`,
    taskType,
    agentUsed: managerId,
    success,
    steps,
    delegateCalls: steps,
    errorMessage: success ? undefined : (error ?? `Task not completed in ${steps} steps`),
    metadata: { episode: episodeNum },
  })

  return { workerId: worker.id, episode: episodeNum, task, taskType, success, steps, agentUsed: managerId, error, runResult: managerRunResult }
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
    const episodeStart = Date.now()
    const result = await runEpisode(worker, ep, config)
    worker.results.push(result)

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

      const memMgr = worker.tree.getMemoryManager()
      if (memMgr.hasMem0()) {
        for (const r of refs) {
          if (r.confidence >= 0.3) {
            await memMgr.addLesson(
              r.agentId,
              `[${r.taskType}] ${r.rootCause}`,
              { errorPattern: r.errorPattern, failureType: r.failureType },
            )
          }
        }
      }
    }

    if (result.success) {
      const memMgr = worker.tree.getMemoryManager()
      if (memMgr.hasMem0()) {
        await memMgr.addSemanticMemory(
          "alfworld_manager",
          `Successfully completed ${result.taskType} task: "${result.task}" in ${result.steps} delegation steps.`,
          { taskType: result.taskType, steps: result.steps },
        )
      }
    }

    if (config.extend) {
      const probation = worker.tree.extension.getProbationEntities()
      if (probation.length > 0) {
        const involvedWorkers = worker.tree.monitor.getWorkersSince(episodeStart)
        for (const entity of probation) {
          if (entity.type === "worker") {
            const workerResults = involvedWorkers.filter((w) => w.workerId === entity.entityId)
            for (const wr of workerResults) {
              worker.tree.extension.updateProbation(entity.entityId, wr.success, result.taskType, result.steps)
            }
          } else if (entity.type === "skill" || entity.type === "skill_refinement") {
            worker.tree.extension.updateProbation(entity.entityId, result.success, result.taskType, result.steps)
          }
        }
      }
    }

    const CHECK_INTERVAL = 5
    if (config.extend && worker.results.length % CHECK_INTERVAL === 0 && worker.results.length >= CHECK_INTERVAL) {
      const newAgents = await worker.tree.checkAndExtend()
      if (newAgents > 0) {
        console.log(`  [w${worker.id}] extended tree: +${newAgents} agent(s)`)
        worker.tree.registerDelegateTool({
          managerId: "alfworld_manager",
          successCheck: () => worker.bridge.getIsDone(),
          runOptions: { maxIterations: 25, model: config.model },
        })
      }

      if (worker.skillEvolution && worker.reflections.length >= 2) {
        const stats = worker.tree.monitor.getStats()
        const evolved = await worker.skillEvolution.evolve(worker.reflections, stats)
        if (evolved.length > 0) {
          console.log(`  [w${worker.id}] evolved skills: ${evolved.map((e) => e.skillId).join(", ")}`)
          await worker.tree.reload()
          worker.tree.registerDelegateTool({
            managerId: "alfworld_manager",
            successCheck: () => worker.bridge.getIsDone(),
            runOptions: { maxIterations: 25, model: config.model },
          })
        }
        worker.reflections = []
      }
    }

    if (worker.envMemory && worker.results.length % 10 === 0 && worker.results.length > 0) {
      worker.envMemory.consolidate()
      const envMemPath = join(worker.dir, "memory", "environment.json")
      await worker.envMemory.save(envMemPath)
    }

    await worker.tree.getMemoryManager().pruneAll()
  }

  if (worker.envMemory) {
    const envMemPath = join(worker.dir, "memory", "environment.json")
    await worker.envMemory.save(envMemPath)
    const stats = worker.envMemory.stats()
    console.log(`  [w${worker.id}] env memory: ${stats.spatial} spatial, ${stats.objects} objects, ${stats.states} states`)
  }

  if (config.autoStart) {
    await worker.bridge.stop()
  }
}

// ─── Summary & merge ───────────────────────────────────────────────────

function printExtensionSummary(workers: Worker[]): void {
  const allHistory = workers.flatMap((w) => w.tree.extension.getHistory())
  if (allHistory.length === 0) return

  console.log("\n  Extension activity:")
  for (const record of allHistory) {
    const perf = `${(record.performance.successRate * 100).toFixed(0)}% (${record.performance.tasksHandled} tasks)`
    const baseline = `baseline ${(record.performance.baselineRate * 100).toFixed(0)}%`
    const status = record.status === "active" ? "✓ promoted" : record.status === "disabled" ? "✗ disabled" : "⏳ probation"
    console.log(`    ${record.type} ${record.entityId.padEnd(30)} ${status}  ${perf} vs ${baseline}`)
  }
}

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

  // Stratified sampling: override episodes count
  // ALFWorld train split has 6 task types (env merges pick_and_place_with_movable_recep into pick_and_place_simple)
  const ALFWORLD_TASK_TYPES = 6
  if (config.perType > 0) {
    config.episodes = config.perType * ALFWORLD_TASK_TYPES
  }

  const TREE_DIR = resolve(join(TREES_DIR, config.tree))

  console.log("═══ AgentTree Parallel Benchmark Runner ═══")
  console.log(`  Tree:      ${config.tree} (${TREE_DIR})`)
  console.log(`  Benchmark: ${config.benchmark}`)
  console.log(`  Split:     ${config.split}`)
  if (config.perType > 0) {
    console.log(`  Sampling:  stratified ${config.perType}/type × ${ALFWORLD_TASK_TYPES} types = ${config.episodes} episodes`)
  } else {
    console.log(`  Episodes:  ${config.episodes}`)
  }
  console.log(`  Workers:   ${config.parallel}`)
  console.log(`  Model:     ${config.model}`)
  console.log(`  Max steps: ${config.maxSteps}`)
  console.log(`  Extension: ${config.extend ? "on" : "off"}`)
  console.log(`  Skill evo: ${config.evolve ? "on" : "off"}`)
  console.log(`  Mem0:      ${config.mem0 ? "on" : "off"}`)
  console.log(`  Env mem:   ${config.envMemory ? "on" : "off"}`)
  console.log(`  Ports:     ${config.basePort}..${config.basePort + config.parallel - 1}`)

  const apiKey = process.env.OPENAI_API_KEY
  if (!apiKey) {
    console.error("\nError: OPENAI_API_KEY required.")
    process.exit(1)
  }

  let mem0: Mem0Bridge | undefined
  if (config.mem0) {
    const baseURL = process.env.OPENAI_BASE_URL || "https://api.openai.com/v1"
    mem0 = new Mem0Bridge({
      apiKey,
      baseUrl: baseURL,
      extractionModel: "gpt-4o-mini",
      embeddingModel: "text-embedding-ada-002",
      historyDbPath: join(TREE_DIR, "memory", "mem0_history.db"),
      collectionName: "a2s_benchmark",
    })
    console.log(`\n  Mem0 initialized (collection: a2s_benchmark)`)
  }

  // Distribute episodes contiguously
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
    const worker = await createWorker(i, config, TREE_DIR, skipGames, mem0)
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
  if (config.extend) {
    printExtensionSummary(workers)
  }
  if (mem0) {
    const mem0Stats = await mem0.stats()
    console.log(`\n  Mem0 stats: ${mem0Stats.org} org-level memories`)
  }

  // 4. Create experiment directory and snapshot initial tree
  const ts = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19)
  const modelSlug = config.model.replace(/[^a-zA-Z0-9_-]/g, "-")
  const runId = `${modelSlug}_${config.split}_${config.episodes}ep_${ts}`
  const experimentDir = join(EXPERIMENTS_DIR, runId)
  await mkdir(experimentDir, { recursive: true })

  const initialDir = join(experimentDir, "tree", "initial")
  const finalDir = join(experimentDir, "tree", "final")
  await mkdir(initialDir, { recursive: true })
  await mkdir(finalDir, { recursive: true })

  for (const sub of ["agents", "skills"]) {
    try {
      await cp(join(TREE_DIR, sub), join(initialDir, sub), { recursive: true })
    } catch {
      await mkdir(join(initialDir, sub), { recursive: true })
    }
    try {
      await cp(join(TREE_DIR, sub), join(finalDir, sub), { recursive: true })
    } catch {
      await mkdir(join(finalDir, sub), { recursive: true })
    }
  }

  console.log(`\n4. Experiment: ${experimentDir}`)
  console.log(`   Tree (initial): ${initialDir}/`)

  // 5. Merge workers into tree/final/
  console.log("\n5. Merging worker results into tree/final/...")
  const merger = new WorkspaceMerger(finalDir)

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

  // Copy memory from worker dirs into tree/final/memory/
  const finalMemoryDir = join(finalDir, "memory")
  await mkdir(finalMemoryDir, { recursive: true })
  for (const worker of workers) {
    try {
      await cp(join(worker.dir, "memory"), finalMemoryDir, { recursive: true })
    } catch {
      // worker may not have memory files
    }
  }
  console.log(`   Tree (final):   ${finalDir}/`)

  // 6. Save traces, results, and config
  const tracesDir = join(experimentDir, "traces")
  await mkdir(tracesDir, { recursive: true })
  for (const r of allResults) {
    if (!r.runResult) continue
    const epNum = String(r.episode).padStart(3, "0")
    const traceData = {
      episode: r.episode,
      task: r.task,
      taskType: r.taskType,
      success: r.success,
      manager: {
        agentId: r.agentUsed,
        messages: r.runResult.messages,
        toolCalls: r.runResult.toolCalls,
        iterations: r.runResult.iterations,
        usage: r.runResult.usage,
        response: r.runResult.response,
      },
    }
    await writeFile(join(tracesDir, `ep_${epNum}.json`), JSON.stringify(traceData, null, 2), "utf-8")
  }
  console.log(`   Traces:         ${tracesDir}/ (${allResults.filter((r) => r.runResult).length} files)`)

  const resultsPath = join(experimentDir, "results.json")
  const episodeSummaries = allResults.map(({ runResult, ...rest }) => rest)
  await writeFile(
    resultsPath,
    JSON.stringify(
      {
        config: { ...config, treeDir: TREE_DIR },
        timestamp: new Date().toISOString(),
        elapsedSeconds: parseFloat(elapsed),
        summary: {
          total: allResults.length,
          success: allResults.filter((r) => r.success).length,
          rate: allResults.filter((r) => r.success).length / allResults.length,
        },
        episodes: episodeSummaries,
        extension: config.extend
          ? {
              history: workers.flatMap((w) => w.tree.extension.getHistory()),
              monitorStats: workers.map((w) => ({
                workerId: w.id,
                stats: w.tree.monitor.getStats(),
              })),
            }
          : undefined,
        mem0: config.mem0
          ? { enabled: true, stats: await mem0!.stats() }
          : undefined,
        envMemory: config.envMemory
          ? {
              enabled: true,
              stats: workers.map((w) => ({
                workerId: w.id,
                ...(w.envMemory?.stats() ?? { spatial: 0, objects: 0, states: 0, temporal: 0, total: 0 }),
              })),
            }
          : undefined,
      },
      null,
      2,
    ),
    "utf-8",
  )
  console.log(`   Results:        ${resultsPath}`)

  const configPath = join(experimentDir, "config.json")
  await writeFile(
    configPath,
    JSON.stringify(
      {
        ...config,
        base_tree: config.tree,
        timestamp: new Date().toISOString(),
        experimentId: runId,
      },
      null,
      2,
    ),
    "utf-8",
  )
  console.log(`   Config:         ${configPath}`)

  // 7. Cleanup worker dirs
  if (config.cleanup) {
    console.log("\n7. Cleaning up worker directories...")
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
