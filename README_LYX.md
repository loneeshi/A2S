# StuLife Integration - LYX Branch

本分支包含StuLife benchmark的完整集成和三层日志系统实现。

## 快速开始

```bash
cd agenttree
export $(cat ../.env | xargs)
npx tsx examples/run_benchmark.ts --benchmark stulife --episodes 5 --max-steps 30
```

## 主要功能

✅ **StuLife Benchmark集成**
- 完整的1284个tasks
- TypeScript runtime + Python bridge架构
- 修复了chat history和连续reset问题

✅ **三层日志系统**
- Tier 1: StuLife原生Session格式 (`tier1_runs.json`)
- Tier 2: Worker行为记录 (`tier2_worker_actions.json`)
- Tier 3: 完整API调用追踪 (`tier3_api_calls.json`)
- 所有日志实时写入JSON格式

✅ **零侵入设计**
- 不修改core/代码
- 使用wrapper模式实现API logging
- 完全兼容现有ALFWorld benchmark

## 详细文档

查看完整的集成指南：
- [INTEGRATION_GUIDE.md](benchmarks/stulife/INTEGRATION_GUIDE.md)

## 日志输出

```
results/stulife/{run_id}/
├── tier1_runs.json          # StuLife原生格式，可用于metric计算
├── tier2_worker_actions.json # Worker决策记录，便于快速分析
└── tier3_api_calls.json      # 完整API context，用于调试优化
```

## 关键修改

### 新增文件
- `agenttree/src/llm/logging_client.ts` - LoggingLLMClient wrapper
- `benchmarks/stulife/stulife_adapter.py` - StuLife适配器
- `benchmarks/stulife/logging/` - 三层日志系统
- `benchmarks/stulife/INTEGRATION_GUIDE.md` - 详细文档

### 修改文件
- `agenttree/src/runtime/tree.ts` - 支持自定义LLM client
- `agenttree/bridge/bench_server.py` - 添加日志接收endpoint
- `agenttree/examples/run_benchmark.ts` - 使用LoggingLLMClient

## 技术亮点

1. **Wrapper模式**: LoggingLLMClient继承LLMClient，不修改原始代码
2. **实时日志**: 所有日志实时写入，不等待运行结束
3. **上下文传递**: 使用contextvars优雅传递episode_id等信息
4. **原生兼容**: Tier 1完全兼容StuLife格式，可直接计算metrics

## 分支信息

- **分支名**: LYX
- **基于**: main分支（已merge最新远程代码）
- **状态**: 可用于生产环境
- **最后更新**: 2026-03-08

## 联系方式

如有问题，请查看 [INTEGRATION_GUIDE.md](benchmarks/stulife/INTEGRATION_GUIDE.md) 或提交issue。
