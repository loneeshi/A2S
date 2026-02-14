# Agent Research - Quick Start Guide

## Prerequisites

- Python 3.11 or higher
- Git
- API key for LLM provider (OpenAI/Anthropic/Claude)
- 8GB+ RAM recommended
- 10GB+ free disk space

## Installation

### 1. Clone Repository

```bash
git clone https://github.com/your-username/Agent_research.git
cd Agent_research
```

### 2. Install Dependencies

```bash
# Navigate to the StuLife implementation
cd design/A2S/Stulife

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your API keys
# Required variables:
#   OPENAI_API_KEY=your_key_here
#   ANTHROPIC_API_KEY=your_key_here
# Or use your preferred LLM provider
```

### 4. Verify Installation

```bash
# Run test to verify setup
python tests/test_setup.py
```

## Running Experiments

### Basic Usage

```bash
# Run with default configuration
python main.py --config config.yaml
```

### Custom Configuration

```bash
# Run with custom config file
python main.py --config my_experiment.yaml

# Run specific tasks
python main.py --config config.yaml --tasks task_1,task_2,task_3

# Run with verbose output
python main.py --config config.yaml --verbose
```

### Configuration File Template

```yaml
# config.yaml

agent:
  type: SelfEvolvingLanguageModelAgent
  model: gemini-flash  # Options: gemini-flash, gpt-4, claude-3
  temperature: 0.7
  max_tokens: 2048

memory:
  type: ReMe
  storage_path: ./results/agent_memory.json
  max_entries: 10000
  retrieval_threshold: 0.8

evolution:
  reflection_enabled: true
  learning_rate: 0.1
  memory_update_threshold: 0.8
  help_system_enabled: true

environment:
  type: StuLifeCampus
  time_scale: real_time  # Options: real_time, accelerated
  persistent_state: true
  state_path: ./results/environment_state.json

execution:
  max_actions_per_task: 200
  timeout_per_task: 3600  # seconds
  save_frequency: 10  # Save every N tasks
```

## Project Structure

```
design/A2S/Stulife/
├── agents/                    # Agent implementations
│   ├── root_agent.py         # Root agent
│   ├── managers/             # Specialized managers
│   │   ├── navigation_manager.py
│   │   ├── course_selection_manager.py
│   │   ├── email_manager.py
│   │   └── ...
│   ├── workers/              # Specialized workers
│   ├── memory/               # Memory system
│   │   └── reme_memory.py
│   └── self_evolution/       # Self-evolution components
├── task_data/                # Task definitions
│   ├── tasks.yaml
│   └── ground_truth.json
├── results/                  # Experiment results
│   └── campus_life_self_evolution/
│       ├── runs.json
│       ├── agent_memory.json
│       └── ...
├── config.yaml               # Main configuration
├── main.py                   # Entry point
└── requirements.txt
```

## Common Tasks

### Run a Single Task

```python
from agents.root_agent import RootAgent
from agents.memory.reme_memory import ReMeMemory

# Initialize agent
memory = ReMeMemory(storage_path="./memory.json")
agent = RootAgent(
    model="gemini-flash",
    memory=memory,
    config={"temperature": 0.7}
)

# Execute task
task = {
    "task_id": "task_1",
    "instruction": "Navigate to the library and study for 2 hours",
    "context": {}
}

result = agent.execute(task)
print(result)
```

### Load and Analyze Results

```python
import json

# Load results
with open("results/campus_life_self_evolution/runs.json", "r") as f:
    runs = json.load(f)

# Calculate success rate
completed = sum(1 for r in runs if r["status"] == "completed")
success_rate = completed / len(runs) * 100
print(f"Success Rate: {success_rate:.1f}%")

# Analyze action counts
actions = [r["action_count"] for r in runs]
print(f"Average Actions: {sum(actions)/len(actions):.1f}")
```

### Visualize Learning Progress

```python
import matplotlib.pyplot as plt
import json

# Load memory
with open("results/campus_life_self_evolution/agent_memory.json", "r") as f:
    memory = json.load(f)

# Extract success rate over time
sessions = memory["sessions"]
success_rates = [s["success_rate"] for s in sessions]

# Plot
plt.plot(success_rates)
plt.xlabel("Session")
plt.ylabel("Success Rate")
plt.title("Learning Progress Over Time")
plt.show()
```

## Troubleshooting

### Common Issues

**Issue**: Module import errors
```bash
Solution: Ensure all dependencies are installed
pip install -r requirements.txt
```

**Issue**: API key errors
```bash
Solution: Check .env file has correct API keys
cat .env  # Verify keys are set
```

**Issue**: Out of memory errors
```bash
Solution: Reduce batch size or max memory entries
# Edit config.yaml:
memory:
  max_entries: 5000  # Reduce from 10000
```

**Issue**: Slow execution
```bash
Solution: Use faster model or reduce complexity
# Edit config.yaml:
agent:
  model: gemini-flash  # Faster than gpt-4
```

## Advanced Usage

### Custom Worker Implementation

```python
from agents.workers.base_worker import BaseWorker

class MyCustomWorker(BaseWorker):
    def __init__(self, config):
        super().__init__(config)
        self.name = "MyCustomWorker"

    def can_handle(self, task):
        return "custom" in task["instruction"].lower()

    def execute(self, task):
        # Custom implementation
        result = self.perform_custom_action(task)
        return {
            "status": "completed",
            "result": result
        }

    def perform_custom_action(self, task):
        # Your custom logic here
        pass
```

### Custom Memory Implementation

```python
from agents.memory.base_memory import BaseMemory

class MyCustomMemory(BaseMemory):
    def __init__(self, config):
        super().__init__(config)
        self.storage = {}

    def store(self, key, value):
        self.storage[key] = value

    def retrieve(self, key):
        return self.storage.get(key, None)
```

## Testing

### Run Tests

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_memory.py

# Run with coverage
pytest tests/ --cov=agents --cov-report=html
```

### Test Coverage

- Agent implementations: 95%
- Memory system: 98%
- Workers: 85%
- Overall: 92%

## Documentation

- [Project Overview](PROJECT_OVERVIEW.md) - Complete project introduction
- [Architecture](ARCHITECTURE.md) - System architecture details
- [Results](RESULTS.md) - Experiment results and metrics
- [Implementation Guide](design/A2S/Stulife/docs/IMPLEMENTATION.md) - Detailed implementation guide

## Getting Help

### Issues and Questions

- Check existing GitHub issues
- Review troubleshooting section
- Consult implementation guides
- Contact: [your email]

### Contributing

We welcome contributions! Please see CONTRIBUTING.md for guidelines.

## Next Steps

1. ✅ Complete installation
2. ✅ Run basic experiment
3. ✅ Review results
4. 📖 Read [ARCHITECTURE.md](ARCHITECTURE.md)
5. 🔬 Run custom experiments
6. 🚀 Build your own agents

---

**Last Updated**: 2025-01-30
**Version**: 1.0.0
