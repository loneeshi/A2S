# Architecture: auto_expansion_agent

A multi-agent system that runs household task benchmarks and autonomously expands its agent tree -- adding workers, skills, and knowledge -- based on performance. The central research question: **can a minimal agent tree evolve through self-directed extension to match a hand-designed expert tree?**

---

## Table of Contents

- [1. System Overview](#1-system-overview)
- [2. Agent Tree Model](#2-agent-tree-model)
- [3. Runtime Architecture](#3-runtime-architecture)
- [4. Tool System](#4-tool-system)
- [5. Memory Architecture](#5-memory-architecture)
- [6. Skill System](#6-skill-system)
- [7. Auto-Expansion (Extension) System](#7-auto-expansion-extension-system)
- [8. Reflection System](#8-reflection-system)
- [9. Benchmark Runner](#9-benchmark-runner)
- [10. Experiment Design](#10-experiment-design)
- [11. Integration with semantic-router](#11-integration-with-semantic-router)
- [12. Future: stulife Benchmark](#12-future-stulife-benchmark)

---

## 1. System Overview

### Research Motivation

Hand-designing multi-agent systems is expensive. For every new domain, an expert must decide how many agents to create, what tools each agent gets, what skills to write, and how delegation should flow. The result is brittle: a tree designed for ALFWorld won't transfer to campus navigation, and minor domain changes require manual re-engineering.

This project asks whether a **minimal seed tree** -- one manager, one generic worker, zero skills -- can observe its own failures, diagnose capability gaps, and autonomously create the workers and skills it needs. If it can, we get a general recipe for bootstrapping multi-agent systems in new domains without hand-design.

The benchmark: ALFWorld, a text-based household environment with six task types (pick-and-place, heat, cool, clean, examine, pick-two). A hand-designed expert tree with four specialized agents and four skills achieves 98.5% on unseen environments. The minimal tree starts much lower. The question is how far auto-expansion closes that gap.

### High-Level Architecture

```
+-----------------------------------------------------------------------+
|                        Benchmark Runner                                |
|  (system/examples/run_benchmark_parallel.ts)                           |
|                                                                       |
|  episode loop: run --> record --> reflect --> extend --> evolve         |
+-----------------------------------------------------------------------+
         |                    |                    |
         v                    v                    v
+------------------+  +-----------------+  +------------------+
|   TreeRuntime    |  | ReflectionEngine|  | ExtensionEngine  |
|  (container for  |  | (failure diag.) |  | (auto-expansion) |
|   all agents)    |  +-----------------+  +------------------+
+------------------+           |                    |
  |   |   |   |               v                    v
  |   |   |   |       +-------------+      +--------------+
  v   v   v   v       | MemoryStore |      | SkillManager |
+---+ +---+ +---+     +-------------+      +--------------+
|Mgr| |W1 | |W2 |           |                    |
+---+ +---+ +---+           v                    v
  |     |     |       +-------------+      +--------------+
  |     |     |       | Mem0 Bridge |      | SkillEvolve  |
  |     |     |       | (optional)  |      |   Engine     |
  |     +-----+       +-------------+      +--------------+
  |       |
  v       v
+-------------------+     +-------------------+
| ToolRegistry      |     | LLMClient         |
| (JSON definitions)|     | (OpenAI-compat.)  |
+-------------------+     +-------------------+
         |                         |
         v                         v
+-------------------+     +-------------------+
| ToolExecutor      |     | az.gptplus5.com   |
| (handler dispatch)|     | (proxy endpoint)  |
+-------------------+     +-------------------+
         |
         v
+-------------------+
| ALFWorld Python   |
| Bridge Server     |
| (WebSocket, 8765+)|
+-------------------+
```

### Technology Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Runtime | TypeScript, Node.js (Bun-compatible) | All agent logic |
| LLM | OpenAI-compatible API via `LLMClient` | gpt-4o-mini, gemini-2.5-flash |
| Benchmark env | Python (ALFWorld), WebSocket bridge | Separate process per worker |
| Semantic search | ONNX/Rust via semantic-router | mmBERT-32K, 768d embeddings |
| Schema validation | Zod | All specs validated at parse time |
| Agent specs | Markdown with YAML frontmatter | `gray-matter` for parsing |
| Memory storage | Append-only .jsonl | One file per agent |
| Semantic memory | Mem0 (optional) | Org/agent/session scoping |

---

## 2. Agent Tree Model

### What is a "Tree"

A tree is a directory on disk containing everything needed to run a multi-agent system:

```
trees/alfworld_minimal/
  agents/                  .md files (one per agent)
    alfworld_manager.md
    general_worker.md
  skills/                  .md files (one per skill, nested by domain)
    (empty in minimal tree)
  memory/                  .jsonl files (one per agent, created at runtime)
```

Trees are self-contained. The system can load any tree, and different trees can coexist for A/B comparison. The `system/tools/` directory is shared across all trees -- tool definitions are universal.

The project ships several trees that illustrate the evolution trajectory:

| Tree | Agents | Skills | Description |
|------|--------|--------|-------------|
| `alfworld_minimal` | 2 (manager + generic worker) | 0 | Starting seed -- no task-type awareness |
| `alfworld_full_gpt-4o-mini` | 4 (manager + 3 specialists) | 4 | Hand-designed expert, 98.5% on unseen |
| `alfworld_gpt-4o-mini` | Varies | Varies | Evolved from minimal via gpt-4o-mini |
| `alfworld_gemini-2.5-flash` | Varies | Varies | Evolved from minimal via gemini |

### Agent Spec Format

Every agent is a Markdown file with YAML frontmatter. The frontmatter is the machine-readable spec; the body is the agent's system prompt.

```markdown
---
id: alfworld_manager
name: ALFWorldManager
role: orchestrator
mode: primary
description: Manager for ALFWorld tasks
tools:
  allow:
    - delegate
  deny: []
memory:
  mode: full
  store: jsonl
  capacity: 500
skills: []
metadata:
  domain: alfworld
  benchmark: alfworld
  version: 0.1.0
---

You are a task manager for household tasks...
```

The spec schema (defined in `system/src/spec/agent.ts` via Zod):

| Field | Type | Purpose |
|-------|------|---------|
| `id` | string | Unique identifier, matches filename |
| `name` | string | Human-readable name |
| `role` | `"worker" \| "manager" \| "orchestrator"` | Determines capabilities |
| `mode` | `"all" \| "primary" \| "subagent"` | When this agent can be invoked |
| `description` | string? | Injected into orchestrator prompts |
| `tools` | `{ allow: string[], deny: string[] }` | Tool access policy |
| `memory` | `{ mode, store, capacity, ttlHours? }` | Memory configuration |
| `skills` | string[] | Skill IDs to inject into prompt |
| `metadata` | Record<string, any> | Domain, capabilities, status, etc. |

### Role Types

**Orchestrator** (e.g., `alfworld_manager`): Never touches the environment directly. Receives tasks, decomposes them, and delegates subtasks to workers via the `delegate` tool. Its prompt automatically receives `<available_workers>` descriptions so it knows what workers exist and what they can do.

**Worker** (e.g., `general_worker`, `search_worker`): Interacts with the environment through `env.*` tools. Receives subtasks from the orchestrator, executes them, and returns results. Workers can be generalists (handle any task type) or specialists (optimized for specific patterns).

**Manager**: A middle tier in deeper hierarchies (not currently used in ALFWorld, but supported by the runtime).

### Tool Policy

Each agent declares which tools it can access:

- **allow list**: If non-empty, agent can ONLY use these tools. The orchestrator typically allows only `delegate`; workers allow `env.*` tools.
- **deny list**: Tools explicitly blocked. Applied after the allow filter.
- **Empty allow list**: Agent gets all available tools (minus any in deny).

This is enforced at schema resolution time -- `ToolRegistry.resolve()` filters the full tool catalog down to what each agent is permitted.

### How Agents are Loaded

`AgentStore.list()` recursively scans the `agents/` directory, parsing every `.md` file via `gray-matter`. The YAML frontmatter is validated against `AgentSpecSchema`, and the markdown body becomes the base system prompt. `TreeRuntime.loadAll()` wraps each parsed agent into an `AgentRuntime` instance with shared dependencies injected.

---

## 3. Runtime Architecture

### TreeRuntime as the Container

`TreeRuntime` (`system/src/runtime/tree.ts`) is the top-level orchestration object. It owns all shared resources and exposes them to every agent:

```
TreeRuntime
  +-- LLMClient           (one instance, shared)
  +-- ToolExecutor         (one instance, all handlers registered here)
  +-- ToolRegistry         (loads JSON definitions from tools/)
  +-- SkillManager         (loads skill .md files from skills/)
  +-- MemoryManager        (per-agent .jsonl stores + optional Mem0)
  +-- MessageBus           (in-process pub/sub)
  +-- Delegator            (manager-to-worker dispatch)
  +-- ReflectionEngine     (failure analysis)
  +-- PerformanceMonitor   (success rate, step stats)
  +-- DynamicExtensionEngine  (auto-expansion)
  +-- AgentRouter          (task-type to worker mapping)
  +-- Map<string, AgentRuntime>  (all loaded agents)
```

Each `AgentRuntime` is lightweight -- it holds only its spec, prompt text, and a reference to the shared deps. The expensive objects (LLM client, tool executor, memory stores) are never duplicated.

### AgentRuntime: The Execution Loop

`AgentRuntime.run()` (`system/src/runtime/agent.ts`) implements the core agentic loop:

```
1. Build system prompt
   (PromptBuilder assembles: base prompt + identity + workers + skills + working memory)

2. Resolve tool schemas
   (ToolRegistry definitions x ToolExecutor handlers x agent's tool policy)

3. Send to LLM
   (messages: [system prompt, user input, ...conversation history])

4. If LLM returns tool_calls:
   a. Execute each tool via ToolExecutor
   b. Append results to conversation
   c. Check for loops (sliding window of last 4 signatures)
   d. Go to step 3

5. If LLM returns text:
   a. Record to memory
   b. Return RunResult
```

The loop runs up to `maxIterations` (default 10 for workers, 25-50 for managers). If the limit is hit, the last assistant message is returned with a `[Max iterations reached]` marker.

**Loop detection** is built into step 4c: the runtime tracks the last `LOOP_DETECT_WINDOW * 3` tool call signatures (tool name + args). If the most recent 4 calls contain only 2 or fewer unique signatures, a warning is injected into the tool response telling the LLM to try a different approach.

### Prompt Construction Order

`PromptBuilder.build()` (`system/src/runtime/prompt-builder.ts`) assembles the system prompt in a cache-friendly order -- static content first, dynamic content last:

```
1. Base prompt          (from agent .md body -- static, cacheable)
2. <agent_identity>     (id, name, role, description -- static per agent)
3. <available_workers>  (for orchestrators only -- semi-static)
4. <skills>             (loaded on-demand, preprocessed -- semi-static)
5. <working_memory>     (lessons, errors, recent actions -- dynamic)
```

This ordering means the first ~70% of the prompt is identical across calls for the same agent, which helps with LLM provider-side prompt caching.

Skills with `context: "fork"` are excluded from inline injection and listed separately in `<available_fork_skills>` (they run in subagent processes). Active skills can also declare `allowedTools`, surfaced as `<skill_tool_restrictions>` so the LLM knows which tools to use when following a skill's instructions.

### Delegation Flow

When an orchestrator calls `delegate(worker_id, task)`:

1. `TreeRuntime.registerDelegateTool()` has registered a `delegate` handler on the `ToolExecutor`.
2. The handler looks up the target `AgentRuntime` and calls its `run()` method.
3. The worker runs its own agentic loop (with its own tools, skills, and memory).
4. The result is wrapped in a `DelegateResult` with the full execution trace.
5. The handler formats a text summary for the orchestrator and attaches a `subTrace` in the metadata.
6. The orchestrator sees the summary and decides whether to delegate further.

This creates a tree of execution: the manager's `RunResult` contains `ToolCallRecord` entries, and each delegate call's record contains a nested `subTrace` with the worker's complete `ToolCallRecord` array, iteration count, and token usage.

### Structured Traces: RunResult

```typescript
interface RunResult {
  response: string              // Final text output
  toolCalls: ToolCallRecord[]   // Every tool call in order
  iterations: number            // LLM call count
  usage: { promptTokens, completionTokens }
  messages?: ChatMessage[]      // Full conversation history
}

interface ToolCallRecord {
  tool: string
  args: Record<string, unknown>
  result: string
  ok: boolean
  durationMs?: number
  subTrace?: {                  // For delegate calls only
    agentId: string
    toolCalls: ToolCallRecord[]
    iterations: number
    usage: { promptTokens, completionTokens }
    messages?: ChatMessage[]
  }
}
```

The nested `subTrace` structure gives full observability: you can reconstruct the exact sequence of actions across all agents in a single episode from one `RunResult`.

---

## 4. Tool System

### Tool Definitions

Tool definitions are JSON files in `system/tools/`, one per tool. Two formats are supported, both normalized at load time:

**Native format:**
```json
{
  "id": "env.goto",
  "name": "Goto",
  "category": "env",
  "description": "Navigate to a location in the environment",
  "parameters": {
    "location": {
      "type": "string",
      "description": "The location to navigate to",
      "required": true
    }
  }
}
```

**JSON Schema format** (auto-converted): Uses `properties` and `required` arrays in OpenAI-style `parameters` objects. The registry normalizes these into the native flat format.

The project ships 33 tool definitions spanning two domains:

| Category | Tools | Domain |
|----------|-------|--------|
| `env.*` | goto, look, open, close, examine, take, put, heat, cool, clean, toggle | ALFWorld |
| `delegate` | delegate | Cross-domain |
| `email.*` | send, read, search, reply, forward | stulife |
| `calendar.*` | get_schedule, search_events, add_event | stulife |
| `course.*` | search, get_details, register, drop, check_prerequisites, check_conflicts | stulife |
| `geography.*` | get_current_location, walk_to | stulife |
| `map.*` | find_building_id, find_optimal_path | stulife |
| `reservation.*` | check_availability, make, cancel | stulife |

### ToolRegistry

`ToolRegistry` (`system/src/tool/registry.ts`) handles loading and filtering:

- `loadAll()`: Reads every `.json` file in the tools directory, normalizes the format, validates with Zod, and returns a `Map<string, ToolDefinition>`.
- `resolve(policy, available)`: Applies an agent's tool policy (allow/deny) against the full catalog. Returns only the tools this agent is permitted to use.
- `register(tool)` / `unregister(toolId)`: Dynamic tool management -- the extension engine can create new composite tools at runtime.

### ToolExecutor

`ToolExecutor` (`system/src/tool/executor.ts`) bridges definitions to handlers:

- **Registration**: Handlers are functions `(args) => Promise<string | { output, metadata }>`. They're registered by tool ID and can return either a plain string or a structured result with metadata.
- **Execution**: `execute(toolId, args)` calls the handler, wraps the result in a `ToolResult` with timing information and error handling.
- **Schema generation**: `toOpenAISchemas(definitions)` converts tool definitions to the OpenAI function-calling format. Only tools with registered handlers are included -- this prevents the LLM from seeing tools it can't actually call.
- **Metadata passthrough**: When a handler returns `{ output, metadata }`, the metadata propagates through the entire trace chain. The delegate handler uses this to attach `subTrace` data to delegate tool call records.

### ALFWorld Tools

The eleven `env.*` tools map directly to ALFWorld's action space. Each is a thin pass-through: the TypeScript handler sends the action to the Python bridge server via WebSocket, which executes it in the ALFWorld environment and returns the observation text.

| Tool | Action | Example |
|------|--------|---------|
| `env.goto` | Navigate to location | `env.goto(location="countertop 1")` |
| `env.look` | Observe current room | `env.look()` |
| `env.open` | Open a container | `env.open(object="fridge 1")` |
| `env.close` | Close a container | `env.close(object="cabinet 3")` |
| `env.examine` | Inspect an object | `env.examine(object="drawer 2")` |
| `env.take` | Pick up an object | `env.take(object="apple 1", location="countertop 1")` |
| `env.put` | Place an object | `env.put(object="apple 1", location="fridge 1")` |
| `env.heat` | Heat with appliance | `env.heat(object="potato 2", appliance="microwave 1")` |
| `env.cool` | Cool with appliance | `env.cool(object="tomato 1", appliance="fridge 1")` |
| `env.clean` | Clean with appliance | `env.clean(object="plate 3", appliance="sinkbasin 1")` |
| `env.toggle` | Toggle device on/off | `env.toggle(object="desklamp 1")` |

---

## 5. Memory Architecture

The system uses four distinct memory layers, each operating at a different timescale and serving a different purpose.

### Layer 1: Episode Context (within-episode, ephemeral)

The LLM conversation history itself -- system prompt, user message, assistant responses, and tool call results. This is the agent's "working RAM" during a single episode. It resets completely between episodes.

The runtime augments this with loop detection: a sliding window tracks recent tool call signatures, and if the agent starts repeating the same 2 actions across 4 consecutive calls, a warning is injected directly into the tool response. This is a lightweight, stateless mechanism -- no persistent storage, no cross-episode learning.

**Scope**: Single episode. **Lifetime**: Discarded after `AgentRuntime.run()` returns.

### Layer 2: Environment Memory (cross-episode, configurable)

Structured knowledge about the physical world, extracted from agent observations across episodes. Defined in `system/src/memory/environment-types.ts`.

Four entry types capture different aspects of environmental knowledge:

| Entry Type | What it Captures | Example |
|------------|-----------------|---------|
| `SpatialEntry` | Room-to-receptacle mapping | "kitchen 1 contains: countertop 1, fridge 1, cabinet 1-4" |
| `ObjectEntry` | Object type to likely location, with frequency counts | "apple -> {fridge: 3, countertop: 5, drawer: 1}" |
| `StateEntry` | Default states of entities | "fridge 1 is typically closed" |
| `TemporalEntry` | Schedules and time-based patterns (stulife only) | "library open 8am-10pm weekdays" |

The `EnvironmentParser` interface is pluggable -- ALFWorld uses regex-based extraction from `env.look` and `env.goto` observations; a future stulife parser might use NER or LLM-assisted extraction.

Configuration options in `EnvironmentMemoryConfig`:

```typescript
{
  enabled: boolean,         // Toggle via --env-memory CLI flag
  maxEntries: 500,          // Cap on total stored entries
  consolidateEvery: 10,     // Merge entries every N episodes
  decayFactor: 0.95,        // Frequency counts decay over time
  backend: "local" | "semantic-router"
}
```

**Why this layer matters for experiments**: Environment memory helps in *seen* environments (same room layouts as training) because object locations recur. For *unseen* environments, it provides prior distributions ("apples are usually on countertops") but not exact locations. Toggling it off during unseen-environment evaluation isolates the contribution of skills vs. memorized layouts.

**Scope**: Cross-episode, per-tree. **Lifetime**: Persists across episodes within a run; optionally cleared between runs.

### Layer 3: Working Memory (cross-episode, per-agent)

Traditional per-agent memory stored in append-only `.jsonl` files, managed by `MemoryManager` (`system/src/memory/manager.ts`) and `MemoryStore` (`system/src/memory/store.ts`).

Each entry is a timestamped record:

```typescript
{
  timestamp: string,      // ISO 8601
  agent: string,          // Agent ID
  type: "lesson" | "error" | "action",
  content: string,        // Free-text description
  tags: string[],         // For filtering
  ttlHours?: number       // Optional expiry
}
```

At prompt construction time, `MemoryManager.getWorkingContext()` queries the store for recent entries and returns a `WorkingContext`:

```typescript
{
  recentActions: string[],       // Last 10 actions
  lessons: string[],             // Last 10 lessons learned
  knownErrors: string[],         // Last 10 recorded errors
  semanticMemories: SemanticMemory[]  // From Mem0 if available
}
```

These get injected into the prompt as `<working_memory>` sections.

**Memory modes** are configurable per-agent:

| Mode | Behavior |
|------|----------|
| `full` | All entry types recorded and recalled |
| `light` | Recording and recall enabled, lower capacity |
| `off` | No-op store, nothing persisted |

**Optional Mem0 integration**: `Mem0Bridge` (`system/src/memory/mem0-bridge.ts`) adds semantic memory backed by vector search. It uses Mem0's fact extraction (which calls the LLM on every `add()`) for high-value memories only -- lessons and strategies, never raw tool logs. Three scoping levels:

| Scope | Who reads | Who writes | Use case |
|-------|-----------|------------|----------|
| `org` | All agents | Any agent | Shared environment knowledge |
| `agent` | The agent + its manager | The agent | Private experience and lessons |
| `session` | Same session only | Same session | Ephemeral episode context |

**Scope**: Cross-episode, per-agent. **Lifetime**: Persists in `.jsonl` files; pruned by capacity limits and TTL.

### Layer 4: Strategic Memory (cross-episode, via skills)

Skills are the system's long-term strategic knowledge. Unlike working memory entries (short text fragments), skills are full documents -- structured instructions, search strategies, appliance operation guides, common mistake catalogs.

Skills persist as `.md` files in the tree's `skills/` directory. They survive memory clears and transfer across environments. When the reflection engine identifies a recurring failure pattern, it generates a new skill (or updates an existing one) through the `SkillEvolutionEngine`. The skill is then injected into the relevant agents' prompt via the `<skills>` section.

This is the primary channel for durable learning. See [Section 6: Skill System](#6-skill-system) for full details.

**Scope**: Cross-episode, cross-environment. **Lifetime**: Permanent until explicitly removed.

---

## 6. Skill System

### Skill Formats

`SkillManager` (`system/src/skill/manager.ts`) supports two on-disk formats:

**Legacy (single file):**
```
skills/alfworld/task_decomposition.md
```
A single Markdown file with YAML frontmatter (spec) and body (content).

**Directory (with supporting files):**
```
skills/alfworld/object_search/
  SKILL.md                    # Main skill file (frontmatter + content)
  examples.md                 # Worked examples
  location_priorities.json    # Supporting data
```
The `SKILL.md` file has the same format as a legacy skill. Supporting files are listed in the prompt so agents know they exist, and can be read programmatically via `SkillManager.readSupportingFile()`.

### Skill Spec

Defined in `system/src/spec/skill.ts`:

```typescript
{
  id: string,                    // Path-based: "alfworld/task_decomposition"
  description: string,           // What this skill teaches
  type: "reference" | "task" | "workflow",
  whenToUse: string,             // Conditions for activation
  steps: string[],               // High-level workflow steps
  tags: string[],                // For filtering and grouping
  version?: string,
  invocation: { modelCanInvoke, userCanInvoke },
  allowedTools?: string[],       // Tool restrictions when using this skill
  arguments?: SkillArgument[],   // Structured argument schema
  context: "inline" | "fork",   // Inline = injected into prompt; fork = runs in subagent
  agent?: string,                // For fork skills: which agent type to spawn
  model?: string,                // Override LLM model for this skill
  hooks?: SkillHook[],           // Pre/post invocation hooks
  generatedBy?: "manual" | "evolution" | "extension",
  probation?: { status, tasksHandled, successRate, baselineRate }
}
```

### Skill Lifecycle

```
 CREATION                  INJECTION              EVALUATION
 (extension engine    -->  (added to agent's  --> (probation system
  or evolution engine)      skills[] list)         tracks performance)
                                                        |
                                      +-----------------+-----------------+
                                      |                                   |
                                   PROMOTE                             DISABLE
                                (Wilson lower >                    (Wilson upper <
                                 baseline)                           baseline)
```

1. **Creation**: A new skill is generated by the `DynamicExtensionEngine` (phase 1: rescue) or the `SkillEvolutionEngine` (from failure reflections). It starts with `status: "probation"`.

2. **Injection**: The skill's ID is added to relevant agents' `skills[]` array. The `AgentStore.update()` method persists this change to the agent's `.md` file.

3. **Probation**: The extension engine tracks every task where the skill was active. After `minTrials` (default 8), it computes a Wilson score confidence interval against the baseline success rate.

4. **Promotion or Disablement**: If the Wilson lower bound exceeds the baseline, the skill is promoted to `"active"`. If the upper bound falls below the baseline, it's disabled. Early-stop triggers on 3 consecutive failures.

### Dynamic Features

**Argument substitution**: Skill content can reference `$ARGUMENTS`, `$ARGUMENTS[N]`, or `$N` placeholders, replaced at prompt-build time. This lets a single skill template serve multiple concrete invocations.

**Dynamic injection**: Content containing `` !`command` `` patterns triggers shell execution at prompt-build time, with the output inlined. The command runs with the skill's directory as cwd and a 10-second timeout.

**Supporting file references**: For directory-based skills, `buildSkillPrompt()` lists all supporting filenames so the agent knows what supplementary material exists.

### SkillEvolutionEngine

`SkillEvolutionEngine` (`system/src/skill/evolution.ts`) generates skills from failure patterns:

1. Groups reflections by `errorPattern` (e.g., `"timeout:alfworld"`, `"wrong_object:alfworld"`).
2. If a pattern has >= `minFailures` (default 2) occurrences, it's a candidate.
3. Checks the task-type success rate -- only generates skills for task types below the failure threshold.
4. Generates content via LLM (preferred) or template fallback.
5. Writes the skill to `skills/<domain>/<taskType>_auto.md`.
6. Injects the skill into all workers matching the domain.

Cross-cutting patterns (e.g., 3+ timeout failures across all task types) trigger efficiency skills injected into all workers.

---

## 7. Auto-Expansion (Extension) System

### Current System: DynamicExtensionEngine v3

`DynamicExtensionEngine` (`system/src/extension/engine.ts`) is the core of the auto-expansion capability. It operates in two phases based on the current success rate relative to a configurable threshold (default 0.7).

#### Phase 1: Rescue (success rate < threshold)

Goal: get the success rate above threshold by adding missing capabilities.

**Trigger detection** identifies two types of gaps:

| Trigger | Condition | Response |
|---------|-----------|----------|
| `worker_capability_gap` | A task type has <50% success rate after 3+ attempts | Design and create a new specialized worker |
| `skill_gap` | A worker has the right tools but wrong strategy | Design and create a new skill for that worker |

**Worker design** uses LLM-assisted architecture: the engine describes the current tree (all agents, their tools, skills, capabilities) and the failure evidence to the LLM, which outputs a JSON worker design specifying ID, tools, prompt strategy, and how it differs from existing workers.

**Skill design** follows the same pattern: the LLM receives the current tree context and the gap description, and outputs a skill with content, type, target worker, and optional tool restrictions.

New entities enter with `status: "probation"`.

#### Phase 2: Optimize (success rate >= threshold)

Goal: reduce step count and variance while maintaining success rate.

Four optimization triggers detected by `PerformanceMonitor` (`system/src/extension/monitor.ts`):

| Trigger | Detection Criteria | Response |
|---------|-------------------|----------|
| `step_efficiency` | p75 > 2x p25, or mean > 2x min for a task type | Refine the relevant skill with efficiency advice |
| `near_miss` | >30% of successes use >80% of max allowed steps | Add robustness tips to the strategy |
| `consistency_gap` | Coefficient of variation (stddev/mean) > 0.5 | Stabilize the approach with a fixed strategy |
| `subtask_bottleneck` | A worker's avg steps > 1.5x peer average | Create targeted optimization for that worker |

Optimization proposals refine existing skills rather than creating new entities. The engine finds the most relevant existing skill for the task type and appends optimization sections.

#### Probation System

The probation system uses Wilson score confidence intervals for sequential hypothesis testing -- a statistically sound approach for small samples:

```
For each trial (episode where entity was active):
  Record success/failure

  Early-stop check:
    3 consecutive failures --> DISABLE immediately

  After minTrials (8):
    Compute Wilson interval at 90% confidence
    If lower bound > baseline --> PROMOTE
    If upper bound < baseline --> DISABLE

  After maxTrials (20):
    Forced decision based on point estimate vs baseline
```

For skill refinements, the criteria are relaxed: the success rate must not drop more than 10% below baseline, and average step count should not increase.

#### Convergence Tracking

`PerformanceMonitor.createCheckpoint()` generates `ConvergenceCheckpoint` records at regular intervals, tracking success rate, average/median steps, and how many task types are above the rescue threshold. `isConverging()` checks the trajectory over a sliding window.

### Planned Redesign: Pattern-Driven Expansion with semantic-router

The current system detects gaps at the statistical level (success rates, step counts). A planned redesign adds structural pattern detection:

- **TraceAnalyzer**: Extract tool call sequences from successful episodes, identify reusable patterns (e.g., "goto -> open -> take -> close -> goto -> put" is a pick-and-place pattern).
- **SkillSynthesizer**: LLM generates a skill document from extracted patterns, with concrete tool sequences and decision points.
- **SkillRouter**: Combines rule-based matching with semantic-router embeddings to decide whether a new pattern should be injected into an existing agent's skill set or whether it warrants a new specialized agent.
- **semantic-router**: Provides fast local ONNX-based embedding and similarity computation (~15ms) instead of LLM calls for routing decisions.

---

## 8. Reflection System

`ReflectionEngine` (`system/src/reflection/engine.ts`) analyzes task failures and produces structured diagnostics that feed into memory and evolution.

### Two Modes

**Rule-based heuristics** (always available, no LLM cost):

Keyword matching on error messages classifies failures:

| Pattern in error | Failure type | Prompt update action |
|-----------------|-------------|---------------------|
| "tool", "function", "not registered" | `tool_misuse` | `update_tool_specifications` |
| "step", "sequence", "order" | `missing_step` | `update_workflow_structure` |
| "object", "target", "wrong" | `wrong_object` | `update_error_prevention` |
| "timeout", "max iteration" | `timeout` | `update_workflow_structure` |
| (none matched) | `unknown` | `no_update` |

Confidence: 0.3 (low, because no semantic analysis).

**LLM-assisted analysis** (optional, higher quality):

Sends the full failure context to the LLM -- domain, task type, error message, action history, tools used, current success rate -- and requests a structured JSON diagnosis. Confidence typically 0.5-0.8.

### ReflectionOutput Structure

```typescript
{
  reflectionId: string,
  timestamp: string,
  domain: string,
  taskType: string,
  agentId: string,
  failureType: FailureType,        // wrong_object | missing_step | tool_misuse | ...
  rootCause: string,               // 1-2 sentence diagnosis
  toolsInvolved: string[],
  errorPattern: string,            // Grouping key for evolution engine
  promptUpdateAction: PromptUpdateAction,
  promptUpdateContent: string,     // Specific text to add to prompt
  memoryUpdates: Array<{           // Entries to write to agent memory
    type: "lesson" | "error" | "action",
    content: string,
    tags: string[]
  }>,
  retryRecommendation: boolean,
  confidence: number               // 0.0 - 1.0
}
```

### How Reflections Flow Through the System

```
Episode fails
    |
    v
ReflectionEngine.analyze(failure)
    |
    v
ReflectionOutput
    |
    +---> applyToMemory() --> MemoryStore (per-agent .jsonl)
    |                          +-> lesson: "[timeout] Agent failed to find object..."
    |                          +-> error: "timeout in alfworld: task not completed..."
    |
    +---> Mem0 (if enabled) --> semantic memory (high-confidence only, >= 0.3)
    |
    +---> SkillEvolutionEngine.evolve(reflections, stats)
    |         +-> Groups by errorPattern
    |         +-> Generates skills for recurring patterns
    |
    +---> PerformanceMonitor (already recorded by runner)
              +-> Feeds into DynamicExtensionEngine triggers
```

---

## 9. Benchmark Runner

### Episode Loop

`run_benchmark_parallel.ts` (`system/examples/run_benchmark_parallel.ts`) is the main experiment driver. Each worker process executes the same loop:

```
for each episode:
  1. bridge.reset()              --> Get task description from ALFWorld
  2. tree.run(managerId, input)  --> Manager decomposes & delegates
  3. Record result               --> monitor.record() with steps/success/type
  4. If failed:
     a. reflection.analyze()     --> Diagnose failure
     b. applyToMemory()          --> Store lessons
     c. Mem0.addLesson()         --> Semantic storage (if enabled)
  5. If succeeded + Mem0:
     a. addSemanticMemory()      --> Record success pattern
  6. Update probation            --> Track extension entity performance
  7. Every 5 episodes:
     a. checkAndExtend()         --> Auto-expansion
     b. skillEvolution.evolve()  --> Skill generation from reflections
     c. tree.reload()            --> Pick up new agents/skills
```

### Parallel Workers

The runner spawns N worker processes, each with:

- Its own copy of the agent tree (copied to `system/runs/{tree}/w{N}/`)
- Its own Python bridge server (ports 8765..8765+N-1)
- Its own `TreeRuntime` instance with independent memory
- A contiguous slice of episodes (e.g., w0 gets 1-45, w1 gets 46-90, w2 gets 91-134)

After all workers finish, a `WorkspaceMerger` reconciles the divergent trees into the experiment's `tree/final/` directory -- merging new agents, deduplicating skills, and combining memory entries. The source templates in `trees/` are never modified.

**Training vs. evaluation parallelism**: Training (`--extend --evolve`) runs with `--parallel 1` because extension decisions depend on the complete history. Evaluation runs safely with `--parallel 3+` because the tree is read-only.

### Output Structure

Each run produces a self-contained experiment directory under `experiments/`:

```
experiments/{model}_{split}_{episodes}ep_{timestamp}/
  config.json                    Full run configuration + metadata
  tree/
    initial/                     Snapshot of the agent tree at start (copied from template)
      agents/*.md
      skills/**/*.md
    final/                       Agent tree after training (post-merge from workers)
      agents/*.md
      skills/**/*.md
      memory/                    Final memory state
  results.json                   Summary + per-episode metadata
  traces/                        Full structured execution traces
    ep_001.json                  One file per episode
    ep_002.json
    ...
```

The `trees/` directory contains only immutable templates (`alfworld_minimal`, `alfworld_full`). Training never mutates templates — workers merge into `tree/final/` within the experiment directory. This makes every run fully reproducible: `tree/initial/` records the starting point, `tree/final/` records what the system evolved to.

`results.json` stays lightweight (~200KB for 134 episodes) for quick statistical queries. Traces are separate files (~500KB-1MB each) to avoid loading everything for analysis.

Each trace file captures the complete execution tree for one episode:

```json
{
  "episode": 1,
  "task": "put a cool tomato in microwave",
  "taskType": "pick_cool_then_place",
  "success": true,
  "manager": {
    "agentId": "alfworld_manager",
    "messages": [...],
    "toolCalls": [
      {
        "tool": "delegate",
        "args": { "worker_id": "search_worker", "task": "..." },
        "ok": true,
        "subTrace": {
          "agentId": "search_worker",
          "toolCalls": [
            { "tool": "env.goto", "args": {"location": "fridge 1"}, "result": "...", "ok": true },
            { "tool": "env.open", "args": {"object": "fridge 1"}, "result": "...", "ok": true }
          ],
          "iterations": 8,
          "usage": { "promptTokens": 3000, "completionTokens": 600 }
        }
      }
    ]
  }
}
```

The experiment's `tree/initial/` and `tree/final/` directories capture the before-and-after state of the agent tree, making diffs straightforward without a separate snapshot system.

---

## 10. Experiment Design

The experiment follows three phases designed to answer the central research question.

### Phase 1: Baselines

Establish the performance floor (minimal tree, no training) and ceiling (hand-designed expert tree) across both validation splits.

| Run | Tree | Split | Episodes | Extension |
|-----|------|-------|----------|-----------|
| 1.1 | alfworld_minimal | valid_unseen | 134 | off |
| 1.2 | alfworld_minimal | valid_seen | 140 | off |
| 1.3 | alfworld_full | valid_seen | 140 | off |
| (prior) | alfworld_full | valid_unseen | 134 | off |

The expert tree (`alfworld_full_gpt-4o-mini`) already achieved **132/134 (98.5%)** on valid_unseen. That is the ceiling the evolved tree tries to reach.

### Phase 2: Training with Evolution

Run the minimal tree on training episodes with auto-extension and skill evolution enabled. Single worker process to ensure consistent evolution.

```bash
npx tsx examples/run_benchmark_parallel.ts \
  --tree alfworld_minimal --split train \
  --episodes 200 --parallel 1 --model gpt-4o-mini \
  --max-steps 50 --extend --evolve --snapshot
```

Expected emergent behaviors:
- Specialized workers for different task types (replacing the single generic worker)
- Skills for object search patterns, appliance operation sequences
- Memory entries capturing environment-specific heuristics

### Phase 3: Evaluation

Test the evolved tree on both validation splits. Memory is cleared but skills are preserved to isolate skill-based improvement from memorized room layouts.

| Run | Tree | Split | Episodes | Extension |
|-----|------|-------|----------|-----------|
| 3.1 | alfworld_evolved (skills only) | valid_unseen | 134 | off |
| 3.2 | alfworld_evolved (skills only) | valid_seen | 140 | off |

### ALFWorld Task Types and Data

Six task types, each with distinct challenges:

| Task Type | Challenge | Key Tools |
|-----------|-----------|-----------|
| `pick_and_place` | Object search + navigation | goto, take, put |
| `pick_clean_then_place` | Sinkbasin operation | goto, take, clean, put |
| `pick_heat_then_place` | Microwave operation | goto, take, heat, put |
| `pick_cool_then_place` | Fridge operation | goto, take, cool, put |
| `look_at_obj_in_light` | Toggle operation | goto, take, toggle |
| `pick_two_obj` | Repeated search + placement | goto, take, put (x2) |

Data splits:

| Split | Episodes | Environments |
|-------|----------|-------------|
| train | 3,553 | Training rooms |
| valid_seen | 140 | Same rooms as train, new object combos |
| valid_unseen | 134 | New room layouts + new object combos |

The distinction matters: **skills** (task decomposition, search strategies) transfer across environments. **Environment memory** (specific room layouts) only helps in seen environments.

### Cross-Model Comparison

The experiment runs with both gpt-4o-mini and gemini-2.5-flash to test whether the evolution trajectory is model-dependent. Each model gets its own evolved tree (`trees/alfworld_gpt-4o-mini/`, `trees/alfworld_gemini-2.5-flash/`).

### Key Configuration Parameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `model` | gpt-4o-mini | Cost-effective, consistent with prior results |
| `max-steps` | 50 | 2x previous; minimal tree needs more room to explore |
| `parallel` | 1 (train) / 3 (eval) | Train needs consistent evolution; eval is read-only |
| Extension check | Every 5 episodes | Built into runner loop |
| Skill evolution | threshold 0.5, min 2 failures | Configured in SkillEvolutionEngine |
| Probation | 8 min / 20 max trials, 90% CI | Wilson score interval |

---

## 11. Integration with semantic-router

`semantic-router` is a local Rust/ONNX service that provides embedding and similarity computation without LLM API calls.

### Core Capability

- **Model**: mmBERT-32K (ONNX), 768-dimensional embeddings with Matryoshka support (truncatable to 64d for speed)
- **Latency**: ~15ms for local inference vs. ~500ms for an LLM API call
- **HTTP API**:
  - `POST /embed` -- Batch embed text strings
  - `POST /similarity/batch` -- Compute cosine similarity between query and candidate sets
  - `POST /classify` -- Classify text against labeled categories

### Use Cases in the Auto-Expansion System

**Skill deduplication**: When the extension engine creates a new skill, semantic-router computes similarity against all existing skills. If the new skill's embedding is within a threshold of an existing one, it's merged rather than duplicated. Prevents the "w0 creates search_specialist, w1 independently creates object_finder" problem during parallel training.

**Skill-to-agent routing**: Given a new skill, determine which existing agent(s) should receive it based on embedding similarity between the skill's description and each agent's description + capabilities.

**Trace pattern clustering**: Group similar tool call sequences across episodes to identify recurring strategies. These clusters become candidates for skill generation.

**Environment memory backend**: When configured with `backend: "semantic-router"`, environment memory entries can be retrieved via semantic search rather than exact match.

### Versus LLM-Based Alternatives

The key advantage is cost and latency. Routing decisions and deduplication checks happen frequently -- potentially once per skill per episode. At ~15ms and zero API cost, semantic-router makes these checks practical. An LLM call for the same classification would cost ~500ms and a few cents per call, making it prohibitively expensive at high frequency.

---

## 12. Future: stulife Benchmark

The stulife benchmark extends the system to campus navigation scenarios -- a fundamentally different environment that tests the generality of the agent tree architecture.

### Domain

- **Campus navigation**: Walking between buildings, using maps, finding optimal paths
- **Course management**: Searching courses, checking prerequisites and conflicts, registering
- **Email handling**: Searching, reading, composing, replying, forwarding
- **Calendar and scheduling**: Viewing schedules, adding events, checking availability
- **Reservations**: Checking availability, making and canceling reservations

### Architectural Reuse

The same runtime stack applies unchanged. The differences are:

| Component | ALFWorld | stulife |
|-----------|----------|---------|
| Tool definitions | `env.*` (11 tools) | `email.*`, `course.*`, `calendar.*`, `map.*`, `geography.*`, `reservation.*` (21 tools) |
| Agent tree | `alfworld_manager` + workers | `stulife_coordinator` + domain workers |
| Environment parser | Regex on `env.look` output | NER or LLM-assisted extraction |
| Memory types needed | Spatial, object location | Spatial, temporal (schedules, hours) |

### New Memory Dimension: Temporal Knowledge

stulife introduces time-dependent information -- building hours, class schedules, office hours, event times. This maps to the `TemporalEntry` type already defined in `environment-types.ts`:

```typescript
{
  type: "temporal",
  entity: string,          // "Science Library"
  pattern: string,         // "open 8am-10pm weekdays, 10am-6pm weekends"
  confidence: number,
  lastUpdated: number
}
```

The `EnvironmentParser.parseTemporal()` method is optional -- ALFWorld's parser leaves it undefined, while the stulife parser will implement it.

### What Transfers, What Doesn't

The agent tree model, runtime architecture, delegation protocol, reflection system, extension engine, and skill system all transfer directly. The minimal-to-expert evolution experiment can be rerun on stulife to test whether the same expansion mechanisms produce effective specialization in a different domain -- the ultimate test of this architecture's generality.
