/**
 * Quick debug — checks if tool registration and schema generation work.
 *
 * Usage: npx tsx examples/debug_tools.ts
 */

import { TreeRuntime } from "../src/runtime/tree"
import { BenchmarkBridge } from "../src/bridge/client"
import { join } from "node:path"

const BASE_DIR = join(import.meta.dirname ?? __dirname, "..")

async function main() {
  const bridge = new BenchmarkBridge({
    benchmark: "alfworld",
    port: 8765,
    autoStart: false,
  })

  const handlers = bridge.createToolHandlers()
  console.log("Bridge handler keys:", Object.keys(handlers))

  const tree = new TreeRuntime({
    baseDir: BASE_DIR,
    llmOptions: { apiKey: "test", defaultModel: "gpt-4o-mini" },
    toolHandlers: handlers,
  })

  await tree.loadAll()
  console.log("\nAgents:", tree.listIds())

  const executor = tree.getToolExecutor()
  console.log("\nExecutor handlers:", executor.list())

  const agent = tree.get("manipulation_worker")!
  console.log("\nAgent tools policy:", agent.spec.tools)

  const { ToolRegistry } = await import("../src/tool/registry")
  const registry = new ToolRegistry(join(BASE_DIR, "tools"))

  try {
    const allTools = await registry.loadAll()
    console.log("\nRegistry loaded tools:", [...allTools.keys()])

    const resolved = registry.resolve(agent.spec.tools, allTools)
    console.log("\nResolved for manipulation_worker:", resolved.map(t => t.id))

    const schemas = executor.toOpenAISchemas(resolved)
    console.log("\nOpenAI schemas count:", schemas.length)
    if (schemas.length > 0) {
      console.log("First schema:", JSON.stringify(schemas[0], null, 2))
    }
  } catch (err) {
    console.error("\nRegistry load error:", err)
  }
}

main().catch(console.error)
