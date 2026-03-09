# StuLife Benchmark Integration

StuLife 是一个校园生活模拟 benchmark，包含邮件、日历、选课、地图导航等多个系统。

## 快速开始

### 运行完整 Benchmark

```bash
cd /Users/a86135/Desktop/A2S/A2S
./benchmarks/stulife/scripts/run_benchmark.sh
```

默认运行 10 episodes，每个最多 50 步。

### 自定义参数

```bash
# 运行 20 episodes，每个最多 60 步
./benchmarks/stulife/scripts/run_benchmark.sh 20 60

# 运行 5 episodes，每个最多 40 步
./benchmarks/stulife/scripts/run_benchmark.sh 5 40
```

### 快速测试（2 episodes）

```bash
./benchmarks/stulife/scripts/quick_test.sh
```

### 验证结果

```bash
./benchmarks/stulife/scripts/validate_results.sh [results_dir]
```

如果不提供 results_dir，会自动使用最新的结果目录。

## 目录结构

```
benchmarks/stulife/
├── README.md                    # 本文件
├── stulife_adapter.py           # StuLife 适配器（薄包装层）
├── stulife_source/              # StuLife 源码
├── scripts/                     # 运行脚本
│   ├── run_benchmark.sh         # 主运行脚本 ⭐
│   ├── quick_test.sh            # 快速测试
│   └── validate_results.sh      # 结果验证
├── docs/                        # 文档
│   ├── STULIFE_INTEGRATION_ANALYSIS.md           # 接入分析报告
│   ├── STULIFE_INTEGRATION_CORRECTNESS_PROOF.md  # 正确性证明
│   ├── FIXES_SUMMARY.md                          # 修复总结
│   └── README_BENCHMARK.md                       # 详细运行指南
└── logging/                     # 三层日志系统
    ├── logging_coordinator.py
    ├── tier1_logger.py
    ├── tier2_logger.py
    └── tier3_logger.py
```

## 结果文件

运行后，结果保存在 `results/stulife/stulife_YYYY-MM-DDTHH-MM-SS-NNNNNN/`:

- **tier1_runs.json**: StuLife 原生格式的 session 数据（包含完整 chat_history 和 evaluation_record）
- **tier2_worker_actions.json**: Worker 行为日志
- **tier3_api_calls.json**: API 调用日志（token 使用量、延迟等）

## 环境要求

- Node.js >= 16
- Python >= 3.8
- `.env` 文件包含 `OPENAI_API_KEY`

## 架构说明

我们采用**薄包装层（Thin Wrapper）**设计：

1. 直接使用 StuLife 源码，不修改原始代码
2. 提供简单的 reset/step 接口
3. 所有核心逻辑（工具执行、评估）由 StuLife 控制
4. 生成的数据与 StuLife 原生格式 100% 兼容

详细说明请参考 `docs/STULIFE_INTEGRATION_CORRECTNESS_PROOF.md`。

## 故障排除

### Port 8765 already in use

脚本会自动清理端口，如果仍有问题：

```bash
lsof -ti:8765 | xargs kill -9
```

### tier1_runs.json 为空

这个问题已修复。如果仍然出现，确保使用最新代码并重新编译：

```bash
cd agenttree && npm run build
```

### OPENAI_API_KEY not set

检查 `.env` 文件：

```bash
cat .env | grep OPENAI_API_KEY
```

## 更多信息

- 详细运行指南: `docs/README_BENCHMARK.md`
- 接入分析报告: `docs/STULIFE_INTEGRATION_ANALYSIS.md`
- 正确性证明: `docs/STULIFE_INTEGRATION_CORRECTNESS_PROOF.md`
- 修复历史: `docs/FIXES_SUMMARY.md`
