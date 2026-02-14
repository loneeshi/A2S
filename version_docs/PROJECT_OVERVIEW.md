# Agent Research - Project Overview

## Introduction

This repository contains research on **AI Agent Development** focused on **lifelong learning** and **autonomous decision-making**. The project implements advanced AI agent architectures that can learn from experience, adapt to new situations, and continuously improve their performance over time.

## Project Vision

To create AI agents that demonstrate:
- **Autonomous Behavior**: Make decisions without explicit instructions
- **Lifelong Learning**: Learn from experience and retain knowledge
- **Self-Improvement**: Continuously enhance capabilities through reflection
- **General Intelligence**: Apply learned skills to novel situations

## Core Components

### 1. A2S Framework (Agent-to-Skills)

The flagship implementation of a hierarchical agent architecture:

**Architecture:**
```
Root Agent
    ├── NavigationManager
    │   ├── WalkingWorker
    │   ├── NavigationWorker
    │   └── PathPlanningWorker
    ├── CourseSelectionManager
    │   ├── CourseQueryWorker
    │   ├── RegistrationWorker
    │   └── ScheduleWorker
    ├── EmailManager
    │   ├── SendEmailWorker
    │   ├── ReadEmailWorker
    │   └── SearchEmailWorker
    └── [20+ more specialized workers]
```

**Key Innovations:**
- **LLM-Based Task Routing**: Uses reasoning rather than keyword matching
- **Hierarchical Skill Tree**: Organizes capabilities into specialized managers
- **Dynamic Tool Discovery**: Agents can autonomously discover new capabilities
- **Meta-Learning Engine**: Enables few-shot adaptation to new tasks

### 2. ReMe Memory System

A three-layer memory architecture for lifelong learning:

```
ReMe (Remember Me) System:
├── Task Memory
│   ├── Completed task histories
│   ├── Success/failure patterns
│   └── Strategy templates
├── Tool Memory
│   ├── Tool capabilities
│   ├── Usage patterns
│   └── Effectiveness metrics
└── Personal Memory
    ├── User preferences
    ├── Long-term goals
    └── Reflection insights
```

### 3. Self-Evolution Framework

Enables continuous improvement through:

- **Reflection Agent**: Analyzes task outcomes and generates insights
- **Help System**: Discovers tools and capabilities autonomously
- **Meta-Learning**: Extracts transferrable knowledge from experience
- **Performance Tracking**: Monitors improvement over time

## Benchmarks

### ELL-StuLife Benchmark

A comprehensive evaluation framework simulating university campus life:

- **1,284 tasks** covering 4 years of student life
- **142 empty instruction tasks** testing autonomous behavior
- **Persistent world state** with dynamic subsystems
- **Calendar-driven execution** requiring self-directed scheduling

**Task Categories:**
- Navigation (campus movement)
- Course selection and registration
- Email communication
- Calendar management
- Facility reservations
- Quiz and exam completion

### LifelongAgentBench

A general framework for evaluating lifelong learning capabilities:

- **Experience Exploration**: Learn from new situations
- **Long-term Memory**: Retain knowledge over time
- **Skill Learning**: Acquire new capabilities
- **Knowledge Internalization**: Convert experience to wisdom

## Key Results

### Performance Metrics

**Campus Life Self-Evolution (v1.0.0):**
- Task execution time: 5-15 minutes (vs 30min-4h before optimization)
- Action count: 50-150 actions per task (vs 200-2000 previously)
- Success rate: Significant improvement through self-evolution
- Memory efficiency: Structured storage with fast retrieval

### Breakthrough Findings

1. **Empty Instruction Tasks**: Agents can autonomously determine what to do by checking their calendar
2. **Self-Directed Learning**: No external prompting required for routine tasks
3. **Continuous Improvement**: Performance increases through reflection and memory
4. **Meta-Learning**: Knowledge transfers to novel situations

## Technology Stack

**Core Technologies:**
- Python 3.11+
- LangChain (agent framework)
- OpenAI/Anthropic/Claude APIs (LLM)
- YAML (configuration)
- JSON (memory storage)

**Development Tools:**
- Git (version control)
- Pre-commit (code quality)
- Black (code formatting)
- MyPy (type checking)
- PyTest (testing)

## Project Structure

```
Agent_research/
├── benchmarks/
│   ├── LifelongAgentBench/     # Lifelong learning framework
│   └── ELL-StuLife/             # Campus environment benchmark
├── design/
│   ├── A2S/                     # Agent-to-Skills framework
│   │   ├── Stulife/             # Campus life implementation
│   │   │   ├── agents/          # Agent implementations
│   │   │   ├── results/         # Experiment results
│   │   │   │   └── campus_life_self_evolution/
│   │   │   └── task_data/       # Task definitions
│   │   └── [other designs]
│   └── [other designs]
├── version_docs/                # Version records (this directory)
├── docs/                        # Additional documentation
├── logs/                        # Execution logs
└── [project files]
```

## Quick Start

1. **Install Dependencies:**
   ```bash
   cd design/A2S/Stulife
   pip install -r requirements.txt
   ```

2. **Configure Environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. **Run an Experiment:**
   ```bash
   python main.py --config config.yaml
   ```

For detailed instructions, see [QUICK_START.md](QUICK_START.md).

## Research Significance

This work contributes to:

- **Autonomous AI Agents**: Moving beyond reactive to proactive behavior
- **Lifelong Learning**: Enabling continuous improvement over time
- **Memory Systems**: Structured approaches to knowledge retention
- **Hierarchical Reasoning**: Organized problem-solving at scale

## Publications and References

- ELL-StuLife Benchmark Documentation
- Self-Evolution Framework Guide
- ReMe Memory System Specification
- Implementation Summary Documents

## Contributing

[Your contribution guidelines]

## License

[Your license information]

## Contact

[Your contact information]

---

**Last Updated:** 2025-01-30
**Version:** 1.0.0
**Status:** Active Research
