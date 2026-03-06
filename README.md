# A2S — Auto-Expansion Agent Cluster

A multi-agent runtime framework where agent trees **auto-generate** from benchmark descriptions, **auto-expand** based on performance feedback, and **evolve skills** through a memory-driven learning loop.

## Results

**ALFWorld** (30 episodes, gpt-4o-mini, max 50 steps):

| Task Type | Success |
|-----------|---------|
| pick_and_place | 12/15 (80%) |
| pick_clean_then_place | 4/7 (57%) |
| pick_cool_then_place | 1/2 (50%) |
| pick_heat_then_place | 1/3 (33%) |
| examine | 1/3 (33%) |
| **Total** | **19/30 (63.3%)** |

## How It Works

```
Read benchmark → Generate agent tree → Run episodes → Record performance
       ↑                                                       ↓
  Evolve skills ← Reflect on failures ← Extend tree if underperforming
```

1. **Agent Tree Generation** — Read benchmark description, create orchestrator + specialized workers
2. **Episode Execution** — LLM selects actions via tool calling, interacts with environment
3. **Performance Monitoring** — Track per-agent, per-task-type success rates
4. **Dynamic Extension** — Add/specialize/replicate workers when success rate drops
5. **Reflection** — Batch-analyze failures → structured output → memory update
6. **Skill Evolution** — Auto-generate new skills from failure patterns, inject into underperforming agents

## Architecture

The runtime (`agenttree/`) is TypeScript, filesystem-based (agents `.md`, tools `.json`, skills `.md`, memory `.jsonl`):

```
agenttree/
├── agents/          # Agent specs (frontmatter + prompt body)
├── skills/          # Skill definitions
├── tools/           # Tool JSON schemas (32 definitions)
├── bridge/          # Python ALFWorld server + launcher
├── examples/        # Benchmark runners + debug scripts
├── src/
│   ├── spec/        # Zod schemas (agent, skill, memory)
│   ├── parser/      # Frontmatter parser (gray-matter)
│   ├── tool/        # ToolRegistry + ToolExecutor
│   ├── memory/      # JSONL MemoryStore + MemoryManager
│   ├── skill/       # SkillManager + SkillEvolutionEngine
│   ├── llm/         # OpenAI-compatible client
│   ├── runtime/     # AgentRuntime, PromptBuilder, TreeRuntime
│   ├── messaging/   # MessageBus + Delegator
│   ├── reflection/  # Failure analysis engine
│   ├── extension/   # PerformanceMonitor + DynamicExtensionEngine
│   ├── bridge/      # BenchmarkBridge client
│   └── utils/       # WorkspaceMerger
├── package.json
└── tsconfig.json
benchmarks/
├── alfworld/        # ALFWorld adapter + config
└── stulife/         # StuLife benchmark intro
```

## Quick Start

```bash
# Prerequisites: Node.js, Python 3.12 with alfworld installed

# Install dependencies
cd agenttree && npm install

# Set environment
export OPENAI_API_KEY="your-key"
export OPENAI_BASE_URL="https://api.openai.com/v1"  # or your relay

# Run ALFWorld benchmark (3 parallel workers, 30 episodes)
npx tsx examples/run_benchmark_parallel.ts \
  --parallel 3 --episodes 30 --max-steps 50 \
  --extend --evolve
```

### Runner Options

| Flag | Default | Description |
|------|---------|-------------|
| `--parallel N` | 1 | Number of parallel workers |
| `--episodes N` | 30 | Total episodes to run |
| `--max-steps N` | 50 | Max steps per episode |
| `--extend` | off | Enable dynamic tree extension |
| `--evolve` | off | Enable skill evolution |
| `--cleanup` | off | Kill bridge servers after run |
| `--base-port N` | 8765 | Starting port for bridge servers |

## Dependencies

**Node.js** (runtime):
- `gray-matter` — frontmatter parsing
- `zod` — schema validation
- `undici` — HTTP proxy support

**Python** (ALFWorld bridge):
- `alfworld` — environment
- `pyyaml` — config parsing

## License

MIT
