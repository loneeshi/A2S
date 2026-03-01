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
