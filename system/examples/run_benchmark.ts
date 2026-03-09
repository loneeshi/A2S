/**
 * Benchmark Runner — runs the full agenttree pipeline against real benchmarks.
 *
 * Connects TreeRuntime to a live benchmark environment via BenchmarkBridge:
 *   1. Start BenchmarkBridge (spawns bench_server.py)
 *   2. Register real tool handlers that map env.* calls → benchmark step()
 *   3. Load all agents
 *   4. For each episode: reset → delegate task to workers → step until done
 *   5. Record results, reflect on failures, auto-extend tree if needed
 *
 * Usage:
 *   OPENAI_API_KEY=sk-... npx tsx examples/run_benchmark.ts --benchmark alfworld --episodes 5
 *   OPENAI_API_KEY=sk-... npx tsx examples/run_benchmark.ts --benchmark stulife --episodes 3
 *
 * Options:
 *   --benchmark  alfworld | stulife        (required)
 *   --episodes   number of episodes        (default: 5)
 *   --model      LLM model name            (default: gpt-4o-mini)
 *   --max-steps  max tool calls per episode (default: 20)
 *   --extend     enable auto-extension     (default: false)
 *   --split      ALFWorld split            (default: train)
 *   --no-auto-start  don't auto-start Python server (connect to existing one)
 *   --port       server port               (default: 8765)
 */

import { TreeRuntime } from "../src/runtime/tree"
import { BenchmarkBridge } from "../src/bridge/client"
import { join } from "node:path"

const SYSTEM_DIR = join(import.meta.dirname ?? __dirname, "..")
const PROJECT_ROOT = join(SYSTEM_DIR, "..")
const TREES_DIR = join(PROJECT_ROOT, "trees")
const TOOLS_DIR = join(SYSTEM_DIR, "tools")

interface RunConfig {
  benchmark: "alfworld" | "stulife"
  episodes: number
  model: string
  maxSteps: number
  extend: boolean
  split: string
  autoStart: boolean
  port: number
}

interface EpisodeResult {
  episode: number
  task: string
  success: boolean
  steps: number
  agentUsed: string
  error?: string
}

function parseArgs(): RunConfig {
  const args = process.argv.slice(2)
  const config: RunConfig = {
    benchmark: "alfworld",
    episodes: 5,
    model: "gpt-4o-mini",
    maxSteps: 20,
    extend: false,
    split: "train",
    autoStart: true,
    port: 8765,
  }

  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case "--benchmark":
        config.benchmark = args[++i] as "alfworld" | "stulife"
        break
      case "--episodes":
        config.episodes = parseInt(args[++i], 10)
        break
      case "--model":
        config.model = args[++i]
        break
      case "--max-steps":
        config.maxSteps = parseInt(args[++i], 10)
        break
      case "--extend":
        config.extend = true
        break
      case "--split":
        config.split = args[++i]
        break
      case "--no-auto-start":
        config.autoStart = false
        break
      case "--port":
        config.port = parseInt(args[++i], 10)
        break
    }
  }

  return config
}

function selectCoordinator(benchmark: string): string {
  return benchmark === "stulife" ? "stulife_coordinator" : "task_coordinator"
}

function selectWorker(benchmark: string, task: string): string {
  if (benchmark === "alfworld") {
    const lower = task.toLowerCase()
    if (lower.includes("clean")) return "manipulation_worker"
    if (lower.includes("heat")) return "manipulation_worker"
    if (lower.includes("cool")) return "manipulation_worker"
    if (lower.includes("put") || lower.includes("place")) return "manipulation_worker"
    if (lower.includes("look") || lower.includes("find") || lower.includes("examine"))
      return "perception_worker"
    if (lower.includes("toggle") || lower.includes("turn on") || lower.includes("turn off"))
      return "interaction_worker"
    return "manipulation_worker"
  }

  if (benchmark === "stulife") {
    const lower = task.toLowerCase()
    if (lower.includes("email") || lower.includes("mail") || lower.includes("send") || lower.includes("reply"))
      return "email_worker"
    if (lower.includes("course") || lower.includes("register") || lower.includes("class") || lower.includes("enroll"))
      return "course_worker"
    if (lower.includes("calendar") || lower.includes("schedule") || lower.includes("reserve") || lower.includes("reservation") || lower.includes("room"))
      return "calendar_worker"
    return "calendar_worker"
  }

  return "manipulation_worker"
}

function formatAdmissible(commands: string[]): string {
  if (commands.length === 0) return ""
  return `\n\nAdmissible commands: ${commands.slice(0, 15).join(", ")}` +
    (commands.length > 15 ? ` ... and ${commands.length - 15} more` : "")
}

async function runEpisode(
  tree: TreeRuntime,
  bridge: BenchmarkBridge,
  config: RunConfig,
  episodeNum: number,
): Promise<EpisodeResult> {
  const resetResult = await bridge.reset()
  const task = resetResult.task
  const coordinator = selectCoordinator(config.benchmark)
  const worker = selectWorker(config.benchmark, task)

  console.log(`\n--- Episode ${episodeNum} ---`)
  console.log(`  Task: ${task.slice(0, 120)}`)
  console.log(`  Worker: ${worker}`)

  const admissibleHint = formatAdmissible(resetResult.admissible_commands)
  const input = `Task: ${task}${admissibleHint}\n\nSolve this task step by step. Use your tools to interact with the environment. When you believe the task is complete, state your conclusion.`

  let steps = 0
  let success = false
  let error: string | undefined

  try {
    if (tree.has(coordinator)) {
      const result = await tree.delegate({
        from: coordinator,
        to: worker,
        input,
        metadata: { taskType: guessTaskType(task), episode: episodeNum },
        runOptions: {
          maxIterations: config.maxSteps,
          model: config.model,
          onToolCall: (name, args) => {
            steps++
            console.log(`    [${steps}] ${name}(${JSON.stringify(args).slice(0, 60)})`)
          },
          onToolResult: (_name, output) => {
            const line = output.slice(0, 80).replace(/\n/g, " ")
            console.log(`         → ${line}`)
          },
        },
      })

      success = result.success && bridge.getIsDone()
      if (!result.success) error = result.error
      steps = result.toolCalls?.length ?? steps

      console.log(`  Result: ${success ? "SUCCESS" : "FAIL"} (${steps} steps)`)
      if (!success && bridge.getIsDone()) {
        success = true
        console.log(`  (Bridge reports task completed)`)
      }
      if (result.output) {
        console.log(`  Output: ${result.output.slice(0, 120)}`)
      }
    } else {
      const result = await tree.run(worker, input, {
        maxIterations: config.maxSteps,
        model: config.model,
        onToolCall: (name, args) => {
          steps++
          console.log(`    [${steps}] ${name}(${JSON.stringify(args).slice(0, 60)})`)
        },
        onToolResult: (_name, output) => {
          const line = output.slice(0, 80).replace(/\n/g, " ")
          console.log(`         → ${line}`)
        },
      })

      steps = result.toolCalls.length
      success = bridge.getIsDone()

      console.log(`  Result: ${success ? "SUCCESS" : "FAIL"} (${steps} steps)`)
      console.log(`  Output: ${result.response.slice(0, 120)}`)
    }
  } catch (err) {
    error = err instanceof Error ? err.message : String(err)
    console.log(`  ERROR: ${error.slice(0, 120)}`)
  }

  return { episode: episodeNum, task, success, steps, agentUsed: worker, error }
}

function guessTaskType(task: string): string {
  const lower = task.toLowerCase()
  if (lower.includes("clean")) return "pick_clean_then_place"
  if (lower.includes("heat")) return "pick_heat_then_place"
  if (lower.includes("cool")) return "pick_cool_then_place"
  if (lower.includes("put") || lower.includes("place")) return "pick_and_place"
  if (lower.includes("look") || lower.includes("find") || lower.includes("examine")) return "examine"
  if (lower.includes("toggle") || lower.includes("turn")) return "toggle"
  if (lower.includes("email") || lower.includes("mail")) return "email"
  if (lower.includes("course") || lower.includes("register")) return "course"
  if (lower.includes("reserve") || lower.includes("room")) return "reservation"
  if (lower.includes("schedule") || lower.includes("calendar")) return "calendar"
  return "unknown"
}

async function main() {
  const config = parseArgs()

  console.log("=== AgentTree Benchmark Runner ===")
  console.log(`  Benchmark: ${config.benchmark}`)
  console.log(`  Episodes:  ${config.episodes}`)
  console.log(`  Model:     ${config.model}`)
  console.log(`  Max steps: ${config.maxSteps}`)
  console.log(`  Extension: ${config.extend ? "enabled" : "disabled"}`)

  const apiKey = process.env.OPENAI_API_KEY
  if (!apiKey) {
    console.error("\nError: OPENAI_API_KEY environment variable is required.")
    process.exit(1)
  }

  console.log("\n1. Starting BenchmarkBridge...")
  const bridge = new BenchmarkBridge({
    benchmark: config.benchmark,
    port: config.port,
    autoStart: config.autoStart,
    split: config.split,
    projectRoot: PROJECT_ROOT,
  })

  try {
    await bridge.start()
    console.log("   Bridge connected.")
  } catch (err) {
    console.error(`   Bridge failed to start: ${err instanceof Error ? err.message : err}`)
    console.error("   Make sure Python 3 and required packages are available.")
    console.error(`   Try: python3 ${join(SYSTEM_DIR, "bridge", "bench_server.py")} --benchmark ${config.benchmark}`)
    process.exit(1)
  }

  console.log("\n2. Creating TreeRuntime...")
  const baseURL = process.env.OPENAI_BASE_URL || undefined
  const tree = new TreeRuntime({
    baseDir: join(TREES_DIR, "alfworld_full"),
    toolsDir: TOOLS_DIR,
    llmOptions: {
      apiKey,
      baseURL,
      defaultModel: config.model,
    },
    toolHandlers: bridge.createToolHandlers(),
    extensionThreshold: config.extend ? 0.5 : undefined,
  })

  const agentCount = await tree.loadAll()
  console.log(`   Loaded ${agentCount} agents: ${tree.listIds().join(", ")}`)

  console.log(`\n3. Running ${config.episodes} episodes...`)
  const results: EpisodeResult[] = []

  for (let i = 1; i <= config.episodes; i++) {
    const result = await runEpisode(tree, bridge, config, i)
    results.push(result)

    if (config.extend && i % 3 === 0) {
      console.log("\n  [Extension check]")
      const newAgents = await tree.checkAndExtend()
      if (newAgents > 0) {
        console.log(`  Extended tree with ${newAgents} new agent(s). Total: ${tree.listIds().length}`)
      } else {
        console.log("  No extension needed.")
      }
    }
  }

  console.log("\n=== Summary ===")
  const wins = results.filter((r) => r.success).length
  const total = results.length
  console.log(`  Success: ${wins}/${total} (${((wins / total) * 100).toFixed(1)}%)`)
  console.log(`  Avg steps: ${(results.reduce((s, r) => s + r.steps, 0) / total).toFixed(1)}`)

  const byType = new Map<string, { wins: number; total: number }>()
  for (const r of results) {
    const tt = guessTaskType(r.task)
    const entry = byType.get(tt) ?? { wins: 0, total: 0 }
    entry.total++
    if (r.success) entry.wins++
    byType.set(tt, entry)
  }
  console.log("\n  By task type:")
  for (const [type, stats] of byType) {
    console.log(`    ${type}: ${stats.wins}/${stats.total} (${((stats.wins / stats.total) * 100).toFixed(0)}%)`)
  }

  const byAgent = new Map<string, { wins: number; total: number }>()
  for (const r of results) {
    const entry = byAgent.get(r.agentUsed) ?? { wins: 0, total: 0 }
    entry.total++
    if (r.success) entry.wins++
    byAgent.set(r.agentUsed, entry)
  }
  console.log("\n  By agent:")
  for (const [agent, stats] of byAgent) {
    console.log(`    ${agent}: ${stats.wins}/${stats.total} (${((stats.wins / stats.total) * 100).toFixed(0)}%)`)
  }

  const monitorStats = tree.monitor.getStats()
  console.log(`\n  Performance monitor: ${monitorStats.totalTasks} tracked, ${monitorStats.successRate.toFixed(2)} rate`)

  console.log("\n4. Shutting down bridge...")
  if (config.autoStart) {
    await bridge.stop()
    console.log("   Bridge stopped.")
  } else {
    console.log("   Leaving external bridge running.")
  }
}

main().catch((err) => {
  console.error("Fatal error:", err)
  process.exit(1)
})
