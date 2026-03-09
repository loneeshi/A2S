/**
 * Minimal 1-episode test — directly runs manipulation_worker against ALFWorld.
 * Prints detailed debug info at each step.
 *
 * Usage: npx tsx examples/debug_episode.ts
 */

import { TreeRuntime } from "../src/runtime/tree"
import { BenchmarkBridge } from "../src/bridge/client"
import { join } from "node:path"

const SYSTEM_DIR = join(import.meta.dirname ?? __dirname, "..")
const PROJECT_ROOT = join(SYSTEM_DIR, "..")
const TREES_DIR = join(PROJECT_ROOT, "trees")
const TOOLS_DIR = join(SYSTEM_DIR, "tools")

async function main() {
  const apiKey = process.env.OPENAI_API_KEY
  if (!apiKey) { console.error("Need OPENAI_API_KEY"); process.exit(1) }

  const bridge = new BenchmarkBridge({
    benchmark: "alfworld",
    port: 8765,
    autoStart: false,
  })

  console.log("Waiting for bridge (server must be running)...")
  // Just verify the server is reachable, don't start it
  for (let i = 0; i < 10; i++) {
    try {
      const r = await fetch("http://127.0.0.1:8765/health")
      if (r.ok) break
    } catch { /* retry */ }
    await new Promise(r => setTimeout(r, 1000))
    if (i === 9) { console.error("Bridge not reachable"); process.exit(1) }
  }
  console.log("Bridge connected.")

  const resetResult = await bridge.reset()
  console.log("\n=== RESET ===")
  console.log("Raw task:", JSON.stringify(resetResult.task).slice(0, 200))
  console.log("Admissible:", resetResult.admissible_commands.slice(0, 5), "...")

  const handlers = bridge.createToolHandlers()
  const treeName = process.argv[2] || "alfworld_full"
  const tree = new TreeRuntime({
    baseDir: join(TREES_DIR, treeName),
    toolsDir: TOOLS_DIR,
    llmOptions: {
      apiKey,
      baseURL: process.env.OPENAI_BASE_URL || undefined,
      defaultModel: "gpt-4o-mini",
    },
    toolHandlers: handlers,
  })

  const count = await tree.loadAll()
  console.log(`\nLoaded ${count} agents`)

  const executor = tree.getToolExecutor()
  console.log("Executor handlers:", executor.list().filter(h => h.startsWith("env.")))

  const agent = tree.get("manipulation_worker")!
  console.log("Agent:", agent.spec.id, "tools:", agent.spec.tools.allow)

  // Build the input like the runner does
  const task = resetResult.task
  const admissibleHint = resetResult.admissible_commands.length > 0
    ? `\n\nAdmissible commands: ${resetResult.admissible_commands.slice(0, 15).join(", ")}`
    : ""
  const input = `Task: ${task}${admissibleHint}\n\nSolve this task step by step. Use your tools to interact with the environment. When you believe the task is complete, state your conclusion.`

  console.log("\n=== INPUT TO AGENT ===")
  console.log(input.slice(0, 500))

  console.log("\n=== RUNNING AGENT ===")
  try {
    const result = await tree.run("manipulation_worker", input, {
      maxIterations: 15,
      model: "gpt-4o-mini",
      temperature: 0.3,
      onIteration: (i) => console.log(`\n--- Iteration ${i} ---`),
      onToolCall: (name, args) => {
        console.log(`  TOOL CALL: ${name}(${JSON.stringify(args)})`)
      },
      onToolResult: (name, output, ok) => {
        console.log(`  RESULT [${ok ? "ok" : "err"}]: ${output.slice(0, 120)}`)
        console.log(`  Done? ${bridge.getIsDone()}`)
      },
    })

    console.log("\n=== RESULT ===")
    console.log("Response:", result.response.slice(0, 300))
    console.log("Tool calls:", result.toolCalls.length)
    console.log("Iterations:", result.iterations)
    console.log("Bridge done?", bridge.getIsDone())
  } catch (err) {
    console.error("\n=== ERROR ===")
    console.error(err)
  }

  // Don't shutdown the server — leave it running for next test
  console.log("\nDone. (Server left running)")
}

main().catch(console.error)
