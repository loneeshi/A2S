# ALFWorld Benchmark — Setup & Testing

## Prerequisites

1. **Python 3.11** with the `skilltree_py311` conda environment (or equivalent)
2. **ALFWorld dataset** downloaded and extracted
3. **API key** for LLM calls (OpenAI-compatible endpoint)

## Environment Setup

### 1. Install ALFWorld

```bash
conda activate skilltree_py311
pip install alfworld
```

### 2. Download ALFWorld Data

```bash
export ALFWORLD_DATA="$HOME/.cache/alfworld"
alfworld-download
```

Or manually set `ALFWORLD_DATA` to point to an existing dataset directory containing `json_2.1.1/` and `logic/`.

### 3. Configure API Key

```bash
# Option A: export directly
export OPENAI_API_KEY="sk-..."
export OPENAI_BASE_URL="https://api.openai.com/v1"

# Option B: add to .env file in project root
echo 'OPENAI_API_KEY=sk-...' >> .env
echo 'OPENAI_BASE_URL=https://api.openai.com/v1' >> .env
```

## Smoke Run (Quick Validation)

The fastest way to validate the full pipeline — 2 episodes, max 15 steps:

```bash
bash scripts/smoke_run.sh
```

For simulated mode (no real ALFWorld env needed):

```bash
bash scripts/smoke_run.sh --simulated
```

## Full Benchmark Run

```bash
python scripts/run_benchmark.py \
    --benchmark alfworld \
    --task_id test-001 \
    --workspace_id local-ws \
    --agent_id agent-001 \
    --num_episodes 5 \
    --max_steps 30
```

### CLI Options

| Flag | Default | Description |
|------|---------|-------------|
| `--benchmark` | *required* | Benchmark name (`alfworld`, `stulife`, `webshop`) |
| `--task_id` | *required* | Unique task identifier |
| `--workspace_id` | *required* | Swarm-IDE workspace ID |
| `--agent_id` | *required* | Root agent ID |
| `--num_episodes` | `5` | Number of episodes to run |
| `--max_steps` | `30` | Max steps per episode |
| `--model` | `gemini-2.5-flash` | LLM model override |

## Integrated Test Script (standalone)

For standalone testing without the Swarm-IDE event protocol:

```bash
python scripts/test_alfworld_integrated.py --num_episodes 3 --split train
```

## Results

Results are persisted to `results/<benchmark_name>/` as:
- `<run_id>.json` — Full run data
- `<run_id>.csv` — Episode-level CSV
- `<run_id>_summary.txt` — Human-readable summary

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ImportError: alfworld` | `pip install alfworld` in your conda env |
| `FileNotFoundError: ALFWorld config paths missing` | Set `ALFWORLD_DATA` env var to the dataset root |
| `OPENAI_API_KEY not found` | Export or add to `.env` |
| `Connection timeout` on LLM calls | Check `OPENAI_BASE_URL`, increase timeout |
| Slow resets (>5s) | Ensure `controller.load_receps: True` in `alfworld_config.yaml` |
| `alfworld_config.yaml` not found | The file is at `benchmarks/alfworld/alfworld_config.yaml` — verify `$ALFWORLD_DATA` paths inside it |

## Architecture

```
run_benchmark.py
  ├── Phase 0: check_environment() — fail-fast validation
  ├── Phase 1: AgentTreeGenerator → build agent tree from benchmark_intro.yaml
  ├── Phase 2: Run episodes (AlfworldAdapter + ALFWorldAgent)
  │     ├── adapter.reset() → get task
  │     ├── agent.select_action() → LLM picks from admissible commands
  │     ├── adapter.step(action) → execute in environment
  │     └── ResultsRecorder.record_episode() → persist per-episode data
  ├── Phase 3: DynamicExtensionEngine → extend tree if performance is low
  └── Phase 4: ResultsRecorder.finalize_run() → save JSON/CSV/summary
```
