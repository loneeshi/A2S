/**
 * Demo script — shows the full agenttree runtime pipeline:
 *
 *   1. Create a TreeRuntime from the workspace
 *   2. Register mock tool handlers (simulating ALFWorld)
 *   3. Load all agents from agents/ directory
 *   4. Run a single agent directly
 *   5. Use delegation (coordinator → worker)
 *   6. Show messaging history
 *   7. Show performance monitoring
 *   8. Show reflection on failure
 *
 * Usage:
 *   npx tsx examples/demo.ts
 *
 * Note: Requires OPENAI_API_KEY env var, or set a custom baseURL.
 *       Without a real LLM, the tool-calling loop won't work,
 *       but the wiring is validated.
 */

import { TreeRuntime } from "../src/runtime/tree"
import { join } from "node:path"

const SYSTEM_DIR = join(import.meta.dirname ?? __dirname, "..")
const PROJECT_ROOT = join(SYSTEM_DIR, "..")
const TREES_DIR = join(PROJECT_ROOT, "trees")
const TOOLS_DIR = join(SYSTEM_DIR, "tools")

const MOCK_ENV_STATE = {
  location: "kitchen",
  inventory: [] as string[],
  objects: new Map([
    ["apple 1", "countertop 2"],
    ["plate 1", "sinkbasin 1"],
    ["fridge 1", "kitchen"],
    ["microwave 1", "kitchen"],
    ["countertop 1", "kitchen"],
    ["countertop 2", "kitchen"],
    ["sinkbasin 1", "kitchen"],
  ]),
}

function mockToolHandlers(): Record<string, (args: Record<string, unknown>) => Promise<string>> {
  return {
    "env.look": async (args) => {
      const target = args.target as string | undefined
      if (target) {
        const loc = MOCK_ENV_STATE.objects.get(target)
        return loc
          ? `You see ${target} at ${loc}.`
          : `You don't see ${target} nearby.`
      }
      const visible = [...MOCK_ENV_STATE.objects.entries()]
        .filter(([, loc]) => loc === MOCK_ENV_STATE.location || loc.includes(MOCK_ENV_STATE.location))
        .map(([obj, loc]) => `${obj} (on ${loc})`)
      return `You are in the ${MOCK_ENV_STATE.location}. You see: ${visible.join(", ")}.`
    },

    "env.goto": async (args) => {
      const target = args.target as string
      MOCK_ENV_STATE.location = target
      return `You move to ${target}.`
    },

    "env.take": async (args) => {
      const obj = args.object as string
      const from = args.receptacle as string
      const currentLoc = MOCK_ENV_STATE.objects.get(obj)
      if (!currentLoc || !currentLoc.includes(from.split(" ")[0])) {
        return `Error: ${obj} is not at ${from}.`
      }
      MOCK_ENV_STATE.objects.delete(obj)
      MOCK_ENV_STATE.inventory.push(obj)
      return `You pick up ${obj} from ${from}.`
    },

    "env.put": async (args) => {
      const obj = args.object as string
      const to = args.receptacle as string
      const idx = MOCK_ENV_STATE.inventory.indexOf(obj)
      if (idx < 0) return `Error: You are not holding ${obj}.`
      MOCK_ENV_STATE.inventory.splice(idx, 1)
      MOCK_ENV_STATE.objects.set(obj, to)
      return `You put ${obj} in/on ${to}.`
    },

    "env.open": async (args) => {
      return `You open ${args.receptacle}.`
    },

    "env.close": async (args) => {
      return `You close ${args.receptacle}.`
    },

    "env.clean": async (args) => {
      return `You clean ${args.object} using ${args.receptacle}.`
    },

    "env.heat": async (args) => {
      return `You heat ${args.object} using ${args.receptacle}.`
    },

    "env.cool": async (args) => {
      return `You cool ${args.object} using ${args.receptacle}.`
    },

    "env.toggle": async (args) => {
      return `You toggle ${args.object}.`
    },

    "env.examine": async (args) => {
      return `You examine ${args.target}. It looks normal.`
    },
  }
}

async function main() {
  console.log("=== AgentTree Runtime Demo ===\n")

  const apiKey = process.env.OPENAI_API_KEY ?? "sk-demo-key"
  const hasRealKey = apiKey !== "sk-demo-key"

  const tree = new TreeRuntime({
    baseDir: join(TREES_DIR, "alfworld_full"),
    toolsDir: TOOLS_DIR,
    llmOptions: {
      apiKey,
      defaultModel: "gpt-4o-mini",
    },
    toolHandlers: mockToolHandlers(),
  })

  console.log("1. Loading agents from workspace...")
  const count = await tree.loadAll()
  console.log(`   Loaded ${count} agents: ${tree.listIds().join(", ")}\n`)

  for (const agent of tree.list()) {
    const allowedTools = agent.spec.tools.allow
    console.log(
      `   [${agent.spec.role}] ${agent.spec.id} — ${agent.spec.description ?? "no description"}` +
        (allowedTools.length > 0 ? ` (tools: ${allowedTools.join(", ")})` : ""),
    )
  }
  console.log()

  console.log("2. Testing tool executor...")
  const executor = tree.getToolExecutor()
  const lookResult = await executor.execute("env.look", {})
  console.log(`   env.look() → ${lookResult.output}\n`)

  console.log("3. Testing MessageBus...")
  tree.bus.subscribe("manipulation_worker", (msg) => {
    console.log(`   [bus] ${msg.from} → ${msg.to}: ${msg.content.slice(0, 80)}`)
  })
  await tree.bus.send({
    from: "task_coordinator",
    to: "manipulation_worker",
    type: "info",
    content: "Prepare for a pick-and-place task",
  })
  console.log(`   Message history: ${tree.bus.getHistory().length} messages\n`)

  console.log("4. Testing PerformanceMonitor...")
  tree.monitor.record({
    taskId: "t1",
    taskType: "pick_and_place",
    agentUsed: "manipulation_worker",
    success: true,
  })
  tree.monitor.record({
    taskId: "t2",
    taskType: "pick_clean_then_place",
    agentUsed: "manipulation_worker",
    success: false,
    errorMessage: "Wrong object picked",
  })
  const stats = tree.monitor.getStats()
  console.log(`   Stats: ${stats.totalTasks} tasks, ${stats.successRate.toFixed(2)} success rate`)
  console.log(`   By task type:`, Object.fromEntries(
    Object.entries(stats.byTaskType).map(([k, v]) => [k, `${v.rate.toFixed(2)}`]),
  ))
  console.log()

  console.log("5. Testing ReflectionEngine...")
  const reflections = await tree.reflection.analyzeBatch([
    {
      domain: "manipulation",
      taskType: "pick_clean_then_place",
      agentId: "manipulation_worker",
      errorMessage: "Wrong object picked — took apple 2 instead of apple 1",
      actionHistory: ["env.look({})", 'env.goto({target:"countertop 2"})', 'env.take({object:"apple 2"})'],
      toolsUsed: ["env.look", "env.goto", "env.take"],
      successRate: 0.5,
    },
  ])
  for (const r of reflections) {
    console.log(`   Reflection: [${r.failureType}] ${r.rootCause.slice(0, 80)}`)
    console.log(`   → Action: ${r.promptUpdateAction}, confidence: ${r.confidence}`)
  }
  console.log()

  if (hasRealKey) {
    console.log("6. Running agent with real LLM...")
    try {
      const result = await tree.run("navigation_worker", "Look around the kitchen and tell me what you see.", {
        maxIterations: 3,
        onToolCall: (name, args) => console.log(`   [tool] ${name}(${JSON.stringify(args).slice(0, 60)})`),
        onToolResult: (name, output) => console.log(`   [result] ${name} → ${output.slice(0, 60)}`),
      })
      console.log(`   Response: ${result.response.slice(0, 200)}`)
      console.log(`   Iterations: ${result.iterations}, Tool calls: ${result.toolCalls.length}`)
    } catch (err) {
      console.log(`   Error: ${err instanceof Error ? err.message : err}`)
    }

    console.log("\n7. Testing delegation (coordinator → worker)...")
    try {
      const delegateResult = await tree.delegate({
        from: "task_coordinator",
        to: "manipulation_worker",
        input: "Pick up apple 1 from countertop 2 and put it in the fridge.",
        metadata: { taskType: "pick_and_place" },
        runOptions: { maxIterations: 5 },
      })
      console.log(`   Success: ${delegateResult.success}`)
      console.log(`   Output: ${delegateResult.output.slice(0, 200)}`)
    } catch (err) {
      console.log(`   Error: ${err instanceof Error ? err.message : err}`)
    }
  } else {
    console.log("6. Skipping LLM-dependent tests (no OPENAI_API_KEY set)")
    console.log("   Set OPENAI_API_KEY to test the full agent loop and delegation.\n")
  }

  console.log("=== Demo Complete ===")
  console.log(`\nFinal stats: ${tree.monitor.getStats().totalTasks} tasks tracked`)
  console.log(`Message history: ${tree.bus.getHistory().length} messages`)
}

main().catch(console.error)
