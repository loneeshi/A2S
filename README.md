<<<<<<< HEAD
# Auto-Expansion Agent Cluster Framework

一个基于 few-shot 的自动化 Agent 集群扩展框架，支持在测试过程中动态生成和优化 agent tree。

## 核心特性

- **📖 Benchmark 介绍系统**：结构化的 benchmark 元数据，agent 可以通过阅读理解任务类型
- **🌳 自动 Tree 生成**：混合初始化（描述文件 + 环境探索）
- **🔧 动态扩展机制**：测试中基于性能反馈自动扩展、修正、调整 agent tree
- **💾 Prompt 缓存优化**：所有 agent prompts 采用 cache-optimized 结构，提高推理速度

## 架构概览

```
├── benchmarks/              # Benchmark 定义（仅元数据）
├── core/                     # 框架核心
│   ├── generator/           # Tree 生成器
│   ├── optimizer/            # 动态优化器
│   ├── prompts/             # 缓存优化 prompts
│   └── discovery/           # 发现引擎（来自 A2S）
├── configs/                  # 配置文件
├── tests/                    # 测试（仅核心测试）
└── scripts/                  # 实用脚本
```

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 运行 StuLife benchmark
python scripts/run_benchmark.py --benchmark stulife

# 3. 查看缓存命中率
python scripts/evaluate_cache_hits.py
```

## 项目状态

✅ 仓库结构已创建
✅ .gitignore 已配置
⏳ 核心框架开发中...

## 仓库信息

- **本地路径**: `/Users/dp/Agent_research/design/auto_expansion_agent/`
- **远程仓库**: https://github.com/loneeshi/A2S
=======
# Agent Research - Lifelong Learning AI Agents

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Status](https://img.shields.io/badge/Status-Active-success.svg)

## Overview

This repository contains research on **AI Agent Development** focused on **lifelong learning** and **autonomous decision-making**. The project implements advanced AI agent architectures that can learn from experience, adapt to new situations, and continuously improve their performance over time.

## Key Features

- **🧠 Hierarchical Agent Architecture**: Root Agent → Specialized Managers → Workers
- **💾 Three-Layer Memory System**: Task/Tool/Personal memory (ReMe)
- **🔄 Self-Evolution Framework**: Continuous improvement through reflection
- **🎯 LLM-Based Routing**: Reasoning-based task distribution
- **🚀 High Performance**: 92.3% success rate on 1,284 campus life tasks

## Quick Start

```bash
# Clone repository
git clone https://github.com/your-username/Agent_research.git
cd Agent_research/design/A2S/Stulife

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Run experiment
python main.py --config config.yaml
```

For detailed instructions, see [version_docs/QUICK_START.md](version_docs/QUICK_START.md).

## Project Structure

```
Agent_research/
├── benchmarks/           # Evaluation frameworks
│   ├── LifelongAgentBench/  # Lifelong learning benchmark
│   └── ELL-StuLife/         # Campus environment benchmark
├── design/              # Core implementations
│   └── A2S/              # Agent-to-Skills framework
│       └── Stulife/      # Campus life implementation
│           ├── agents/      # Agent implementations
│           ├── results/     # Experiment results
│           │   └── campus_life_self_evolution/
│           └── task_data/   # Task definitions
├── version_docs/        # Version records and documentation
└── docs/                # Additional documentation
```

## Documentation

- [Project Overview](version_docs/PROJECT_OVERVIEW.md) - Complete project introduction
- [Architecture](version_docs/ARCHITECTURE.md) - System architecture details
- [Results](version_docs/RESULTS.md) - Experiment results and metrics
- [Quick Start](version_docs/QUICK_START.md) - Getting started guide

## Key Results

**Campus Life Self-Evolution (v1.0.0):**
- **Tasks**: 1,284 campus life tasks
- **Success Rate**: 92.3%
- **Execution Time**: 5-15 minutes (vs 30min-4h baseline)
- **Action Count**: 50-150 actions (vs 200-2000 baseline)

### Breakthrough Features

- **Empty Instruction Tasks**: Agents autonomously determine what to do via calendar
- **Self-Directed Learning**: No external prompting for routine tasks
- **Continuous Improvement**: Performance increases through reflection
- **Meta-Learning**: Knowledge transfers to novel situations

## Architecture

### A2S Framework (Agent-to-Skills)

```
Root Agent
    ├── NavigationManager (5 workers)
    ├── CourseSelectionManager (4 workers)
    ├── EmailManager (3 workers)
    ├── CalendarManager (3 workers)
    └── ReservationManager (3 workers)
```

### ReMe Memory System

```
ReMe (Remember Me):
├── Task Memory (strategies, patterns)
├── Tool Memory (capabilities, effectiveness)
└── Personal Memory (preferences, insights)
```

## Technology Stack

- Python 3.11+
- LangChain (agent framework)
- OpenAI/Anthropic/Claude APIs (LLM)
- YAML (configuration)
- JSON (memory storage)

## Benchmarks

### ELL-StuLife Benchmark

A comprehensive evaluation framework simulating university campus life:

- **1,284 tasks** covering 4 years of student life
- **142 empty instruction tasks** testing autonomous behavior
- **Persistent world state** with dynamic subsystems
- **Calendar-driven execution** requiring self-directed scheduling

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

[Your License Here]

## Citation

If you use this code in your research, please cite:

```bibtex
@software{agent_research_2025,
  title={Agent Research: Lifelong Learning AI Agents},
  author={[Your Name]},
  year={2025},
  url={https://github.com/your-username/Agent_research}
}
```

## Contact

[Your Contact Information]

---

**Version**: 1.0.0 | **Status**: Active Research | **Last Updated**: 2025-01-30
>>>>>>> 24010b0 (feat: add utility scripts)
