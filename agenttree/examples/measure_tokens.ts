/**
 * Token measurement — runs 1 episode and reports exact token usage per iteration.
 * Usage: npx tsx examples/measure_tokens.ts
 */

import { TreeRuntime } from "../src/runtime/tree"
import { BenchmarkBridge } from "../src/bridge/client"
import { LLMClient } from "../src/llm/client"
import { join } from "node:path"

const BASE_DIR = join(import.meta.dirname ?? __dirname, "..")

async function main() {
  const apiKey = process.env.OPENAI_API_KEY!
  const baseURL = process.env.OPENAI_BASE_URL || undefined

  const bridge = new BenchmarkBridge({
    benchmark: "alfworld",
    port: 8765,
    autoStart: false,
  })

  for (let i = 0; i < 5; i++) {
    try {
      const r = await fetch("http://127.0.0.1:8765/health")
      if (r.ok) break
    } catch { /* retry */ }
    await new Promise(r => setTimeout(r, 1000))
  }

  const tree = new TreeRuntime({
    baseDir: BASE_DIR,
    llmOptions: { apiKey, baseURL, defaultModel: "gpt-4o-mini" },
    toolHandlers: bridge.createToolHandlers(),
  })
  await tree.loadAll()

  const resetResult = await bridge.reset()
  const task = resetResult.task
  const admissible = resetResult.admissible_commands.slice(0, 15).join(", ")
  const input = `Task: ${task}\n\nAdmissible commands: ${admissible}\n\nSolve this task step by step using your tools.`

  console.log("Task:", task.split("\n").pop()?.trim())
  console.log("")

  let totalInput = 0
  let totalOutput = 0
  let steps = 0

  const result = await tree.run("manipulation_worker", input, {
    maxIterations: 30,
    model: "gpt-4o-mini",
    temperature: 0.3,
    onToolCall: (name) => {
      steps++
      process.stdout.write(`  [${steps}] ${name} → `)
    },
    onToolResult: (_name, output) => {
      console.log(output.slice(0, 50).replace(/\n/g, " "))
    },
  })

  totalInput = result.usage.promptTokens
  totalOutput = result.usage.completionTokens

  console.log("\n=== TOKEN USAGE ===")
  console.log(`  Iterations: ${result.iterations}`)
  console.log(`  Tool calls: ${result.toolCalls.length}`)
  console.log(`  Total input tokens:  ${totalInput}`)
  console.log(`  Total output tokens: ${totalOutput}`)
  console.log(`  Avg input/iteration:  ${Math.round(totalInput / result.iterations)}`)
  console.log(`  Avg output/iteration: ${Math.round(totalOutput / result.iterations)}`)
  console.log(`  Done: ${bridge.getIsDone()}`)
  console.log(`  Won:  ${result.response.includes("SUCCESS") || bridge.getIsDone()}`)

  // Estimate system prompt size
  const systemPromptChars = task.length + 500 // rough: agent .md + identity + skills
  console.log(`\n  Estimated system prompt: ~${Math.round(systemPromptChars / 4)} tokens`)
}

main().catch(console.error)
