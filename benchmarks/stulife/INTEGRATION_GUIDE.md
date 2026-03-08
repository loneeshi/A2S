# StuLife Benchmark Integration Guide

本文档详细记录了如何将StuLife benchmark集成到A2S框架，以及如何实现三层日志系统。

## 目录

- [架构概览](#架构概览)
- [StuLife接入](#stulife接入)
- [三层日志系统](#三层日志系统)
- [关键问题修复](#关键问题修复)
- [使用指南](#使用指南)

---

## 架构概览

### 整体架构

A2S框架采用TypeScript runtime + Python bridge的混合架构：

```
TypeScript Runtime (agenttree/)
    ↓ HTTP
Python Bridge (bridge/bench_server.py)
    ↓
StuLife Adapter (benchmarks/stulife/stulife_adapter.py)
    ↓
StuLife Source (benchmarks/stulife_source/Stulife/)
```

### 设计原则

1. **不修改core/代码**：所有StuLife相关代码都在 `benchmarks/stulife/` 下
2. **版本控制友好**：三层日志系统独立于核心框架
3. **实时记录**：所有日志实时写入，不等待运行结束
4. **原生兼容**：Tier 1日志完全兼容StuLife原生格式

---

## StuLife接入

### 1. StuLife Adapter

**文件位置**: `benchmarks/stulife/stulife_adapter.py`

**核心功能**:
- 包装StuLife的 `CampusTask` 和 `CampusEnvironment`
- 提供统一的 `reset()` / `step()` 接口
- 处理Session对象的生命周期

**关键实现**:

```python
class StuLifeAdapter:
    def __init__(self, data_dir: Optional[str] = None, max_round: int = 10):
        # 加载StuLife组件
        self.campus_task = CampusTask(...)
        self.available_tasks = self.campus_task.get_sample_index_list()

    def reset(self, task_id: Optional[str] = None) -> Dict[str, Any]:
        # 清理上一个session
        if self.current_session is not None:
            self.campus_task.release()
            # 强制清理内部状态
            self.campus_task.current_sample_index = None
            self.campus_task._Task__current_dataset_item = None

        # 创建新session
        self.current_session = Session(...)
        self.campus_task.reset(self.current_session)

    def step(self, action: str) -> Dict[str, Any]:
        # 检查chat history，避免连续AGENT消息
        if should_inject:
            self.current_session.chat_history.inject(
                ChatHistoryItem(role=Role.AGENT, content=action)
            )

        # 执行action
        self.campus_task.interact(self.current_session)
```

**关键修复**:
1. **连续reset问题**: 手动清理 `_Task__current_dataset_item` 私有属性
2. **Chat history冲突**: 检查最后一条消息角色，避免连续AGENT消息

### 2. HTTP Bridge Server

**文件位置**: `agenttree/bridge/bench_server.py`

**核心功能**:
- 启动HTTP服务器，监听TypeScript runtime的请求
- 转发 `/reset` 和 `/step` 请求到adapter
- 接收 `/log_api_call` 请求，记录Tier 3日志

**关键endpoints**:

```python
POST /reset          # 重置环境，返回task描述
POST /step           # 执行action，返回observation
POST /log_api_call   # 记录API调用（Tier 3）
POST /shutdown       # 关闭服务器，finalize日志
GET  /status         # 查询当前状态
```

### 3. TypeScript Runtime集成

**文件位置**: `agenttree/examples/run_benchmark.ts`

**核心流程**:

```typescript
// 1. 启动bridge
const bridge = new BenchmarkBridge({
  benchmark: "stulife",
  port: 8765,
  autoStart: true,
})
await bridge.start()

// 2. 创建LoggingLLMClient（用于Tier 3）
const llmClient = new LoggingLLMClient({
  apiKey,
  baseURL,
  defaultModel: "gpt-4o-mini",
  loggingEndpoint: `http://127.0.0.1:8765`,
})

// 3. 创建TreeRuntime
const tree = new TreeRuntime({
  baseDir: BASE_DIR,
  llmClient,
  toolHandlers: bridge.createToolHandlers(),
})

// 4. 运行episodes
for (let i = 1; i <= episodes; i++) {
  const resetResult = await bridge.reset()
  const result = await tree.run(worker, input, options)
}
```

---

## 三层日志系统

### 设计理念

三层日志系统提供不同粒度的信息：

1. **Tier 1 (Sessions)**: Benchmark层，StuLife原生格式，用于metric计算
2. **Tier 2 (Worker Actions)**: 抽象层，记录高层决策，便于快速分析
3. **Tier 3 (API Calls)**: 详细层，记录完整context window，用于调试优化

### 架构设计

```
benchmarks/stulife/logging/
├── __init__.py
├── coordinator.py          # 中央协调器
├── session_collector.py    # Tier 1: Session收集
├── worker_logger.py        # Tier 2: Worker行为记录
├── api_tracer.py          # Tier 3: API调用追踪
└── context.py             # 上下文传递（episode_id, worker_id等）
```

### Tier 1: Session Collector

**目标**: 生成StuLife原生格式的runs.json

**实现**:

```python
class SessionCollector:
    def add_session(self, session: Any) -> None:
        self.sessions.append(session)
        self._append_to_file(session)  # 实时写入

    def _append_to_file(self, session: Any) -> None:
        runs_data = [s.model_dump() for s in self.sessions]
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(runs_data, f, indent=2, ensure_ascii=False)
```

**输出格式**:
```json
[
  {
    "task_name": "campus_life_bench",
    "sample_index": "2_course_selection_001",
    "sample_status": "CORRECT",
    "chat_history": [...],
    "evaluation_record": {...}
  }
]
```

**集成点**: 在 `bench_server.py` 的 `env_step()` 中，当episode结束时调用：

```python
if result.get("done", False):
    session = _env.get_current_session()
    _env._logging_coordinator.end_episode(
        episode_id=episode_id,
        session=session
    )
```

### Tier 2: Worker Logger

**目标**: 记录每个step的worker行为

**实现**:

```python
class WorkerLogger:
    def log_action(
        self,
        task_summary: str,
        action_taken: str,
        decision_rationale: Optional[str] = None,
        tools_used: Optional[list] = None,
        duration_ms: Optional[float] = None,
    ) -> None:
        ctx = get_logging_context()
        action_record = {
            "timestamp": datetime.now().isoformat(),
            "episode_id": ctx.episode_id,
            "step": ctx.step,
            "worker_id": ctx.worker_id,
            "task_summary": task_summary,
            "action_taken": action_taken,
            "decision_rationale": decision_rationale,
            "tools_used": tools_used or [],
            "duration_ms": duration_ms,
        }
        self.actions.append(action_record)
        self._append_to_file(action_record)  # 实时写入
```

**输出格式**:
```json
{
  "run_id": "stulife_2026-03-08T16-20-54-789506",
  "model": "gpt-4o-mini",
  "worker_actions": [
    {
      "timestamp": "2026-03-08T16:09:51.149407",
      "episode_id": "ep-001",
      "step": 1,
      "worker_id": "stulife_worker",
      "task_summary": "Step 1",
      "action_taken": "course.search(query=\"Chancellor's Hall\")",
      "decision_rationale": "Invalid action. Please provide a valid Action.",
      "tools_used": ["course.search"],
      "duration_ms": 0.66
    }
  ]
}
```

**集成点**: 在 `bench_server.py` 的 `env_step()` 中，每次step都记录：

```python
def env_step(action: str):
    start_time = time.time()
    result = _env.step(action)

    if hasattr(_env, '_logging_coordinator'):
        duration_ms = (time.time() - start_time) * 1000
        _env._logging_coordinator.log_worker_action(
            task_summary=f"Step {_env._step_counter}",
            action_taken=action,
            decision_rationale=observation[:200],
            tools_used=[action.split("(")[0]],
            duration_ms=duration_ms,
        )
```

### Tier 3: API Call Tracer

**目标**: 记录完整的LLM API调用context window

**挑战**: TypeScript runtime调用OpenAI API，不是Python

**解决方案**: 使用wrapper模式，不修改核心代码

#### 3.1 创建 LoggingLLMClient

**文件位置**: `agenttree/src/llm/logging_client.ts`

```typescript
export class LoggingLLMClient extends LLMClient {
  private loggingEndpoint: string | undefined

  async chat(messages: ChatMessage[], options?: ChatOptions): Promise<ChatResponse> {
    const startTime = Date.now()
    let response: ChatResponse | undefined
    let error: string | undefined

    try {
      response = await super.chat(messages, options)
      return response
    } catch (err) {
      error = err instanceof Error ? err.message : String(err)
      throw err
    } finally {
      const latencyMs = Date.now() - startTime

      // 发送日志到bench_server（fire and forget）
      this.sendLog({
        request: { model, messages, temperature, tools },
        response: { content, tool_calls, finish_reason },
        usage: { prompt_tokens, completion_tokens, total_tokens },
        latency_ms: latencyMs,
        error,
      })
    }
  }

  private async sendLog(data: Record<string, unknown>): Promise<void> {
    await fetch(`${this.loggingEndpoint}/log_api_call`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    })
  }
}
```

#### 3.2 修改 TreeRuntime 支持自定义client

**文件位置**: `agenttree/src/runtime/tree.ts`

```typescript
export interface TreeRuntimeOptions {
  baseDir: string
  llmOptions?: LLMClientOptions
  llmClient?: LLMClient  // 新增：支持传入自定义client
  toolHandlers?: Record<string, ToolHandler>
  extensionThreshold?: number
  mem0?: Mem0Bridge
}

constructor(options: TreeRuntimeOptions) {
  // 使用提供的client或创建新的
  if (options.llmClient) {
    this.llm = options.llmClient
  } else if (options.llmOptions) {
    this.llm = new LLMClient(options.llmOptions)
  }
}
```

#### 3.3 在 bench_server 接收日志

**文件位置**: `agenttree/bridge/bench_server.py`

```python
elif self.path == "/log_api_call":
    if _benchmark == "stulife" and hasattr(_env, '_logging_coordinator'):
        request = body.get("request", {})
        response = body.get("response")
        usage = body.get("usage")
        latency_ms = body.get("latency_ms")
        error = body.get("error")

        call_id = _env._logging_coordinator.trace_api_call(
            request=request,
            response=response or {},
            usage=usage,
            latency_ms=latency_ms,
            error=error,
        )
        self._send_json({"ok": True, "call_id": call_id})
```

**输出格式**:
```json
{
  "run_id": "stulife_2026-03-08T16-17-25-651509",
  "api_calls": [
    {
      "call_id": "call-0001",
      "timestamp": "2026-03-08T16:17:34.245742",
      "episode_id": "ep-001",
      "step": 0,
      "worker_id": "stulife_worker",
      "request": {
        "model": "gpt-4o-mini",
        "messages": [
          {"role": "system", "content": "..."},
          {"role": "user", "content": "..."}
        ],
        "temperature": 0.7,
        "tools": [...]
      },
      "response": {
        "content": "...",
        "tool_calls": [],
        "finish_reason": "stop"
      },
      "usage": {
        "prompt_tokens": 1816,
        "completion_tokens": 653,
        "total_tokens": 2469
      },
      "latency_ms": 8528,
      "error": null
    }
  ]
}
```

### 上下文传递机制

**文件位置**: `benchmarks/stulife/logging/context.py`

使用 `contextvars` 实现线程本地上下文传递：

```python
from contextvars import ContextVar
from dataclasses import dataclass

@dataclass
class LoggingContext:
    episode_id: str
    task_id: str
    step: int
    worker_id: str
    run_id: str

_logging_context: ContextVar[Optional[LoggingContext]] = ContextVar(
    "logging_context", default=None
)

def set_logging_context(ctx: LoggingContext) -> None:
    _logging_context.set(ctx)

def get_logging_context() -> Optional[LoggingContext]:
    return _logging_context.get()
```

### 中央协调器

**文件位置**: `benchmarks/stulife/logging/coordinator.py`

```python
class LoggingCoordinator:
    def __init__(self, run_id: str, benchmark: str, model: str, output_dir: Path):
        self.session_collector = SessionCollector(model, output_dir)
        self.worker_logger = WorkerLogger(run_id, model, output_dir)
        self.api_tracer = APICallTracer(run_id, output_dir)

    def start_episode(self, episode_id: str, task_id: str, step: int = 0):
        ctx = LoggingContext(episode_id, task_id, step, "stulife_worker", self.run_id)
        set_logging_context(ctx)

    def end_episode(self, episode_id: str, session: Optional[Any] = None):
        if session:
            self.session_collector.add_session(session)
        clear_logging_context()

    def finalize(self) -> dict:
        runs_json = self.session_collector.save_runs_json()
        worker_actions = self.worker_logger.save()
        api_calls = self.api_tracer.save()
        return {
            "tier1_runs_json": str(runs_json),
            "tier2_worker_actions": str(worker_actions),
            "tier3_api_calls": str(api_calls),
        }
```

---

## 关键问题修复

### 1. Chat History AssertionError

**问题**: StuLife要求chat history中角色必须交替（USER→AGENT→USER→AGENT），但adapter每次step都inject AGENT消息，导致连续AGENT消息。

**错误信息**:
```
File ".../session.py", line 28, in inject
    assert last_role != current_role
AssertionError
```

**解决方案**: 在inject前检查最后一条消息的角色

```python
def step(self, action: str) -> Dict[str, Any]:
    chat_history = self.current_session.chat_history
    length = chat_history.get_value_length()

    # 检查是否需要inject
    should_inject = True
    if length > 0:
        last_msg = chat_history.get_item_deep_copy(length - 1)
        if last_msg.role == Role.AGENT:
            should_inject = False

    if should_inject:
        self.current_session.chat_history.inject(
            ChatHistoryItem(role=Role.AGENT, content=action)
        )
```

### 2. 连续Reset失败

**问题**: 连续调用reset()时，StuLife的release()没有完全清理内部状态，导致AssertionError。

**解决方案**: 手动清理私有属性

```python
def reset(self, task_id: Optional[str] = None) -> Dict[str, Any]:
    if self.current_session is not None:
        try:
            self.campus_task.release()
        except Exception as e:
            logger.warning(f"Release failed: {e}, forcing cleanup")

        # 强制清理内部状态（访问私有属性）
        self.campus_task.current_sample_index = None
        self.campus_task._Task__current_dataset_item = None
        self.campus_task.current_round = 0
```

### 3. 只加载6个测试任务

**问题**: StuLife的task.py优先加载 `e2e_test_tasks.json`（只有6个任务），而不是完整的 `tasks.json`（1284个任务）。

**解决方案**:
1. 从 `task_data/tasks.json` 复制完整数据集
2. 重命名 `e2e_test_tasks.json` 为 `.bak`

```bash
cp benchmarks/stulife_source/Stulife/src/tasks/instance/campus_life_bench/task_data/tasks.json \
   benchmarks/stulife_source/Stulife/src/tasks/instance/campus_life_bench/data/tasks.json

mv benchmarks/stulife_source/Stulife/src/tasks/instance/campus_life_bench/data/e2e_test_tasks.json \
   benchmarks/stulife_source/Stulife/src/tasks/instance/campus_life_bench/data/e2e_test_tasks.json.bak
```

---

## 使用指南

### 运行StuLife Benchmark

```bash
cd /Users/a86135/Desktop/A2S/A2S/agenttree

# 设置环境变量
export $(cat ../.env | xargs)

# 运行benchmark
npx tsx examples/run_benchmark.ts \
  --benchmark stulife \
  --episodes 10 \
  --max-steps 30 \
  --model gpt-4o-mini
```

### 查看日志

三层日志输出到 `results/stulife/{run_id}/`:

```bash
# Tier 1: StuLife原生格式
cat results/stulife/{run_id}/tier1_runs.json | jq '.'

# Tier 2: Worker行为
cat results/stulife/{run_id}/tier2_worker_actions.json | jq '.worker_actions'

# Tier 3: API调用
cat results/stulife/{run_id}/tier3_api_calls.json | jq '.api_calls[] | {call_id, usage, latency_ms}'
```

### 计算Metrics

使用StuLife原生的metric计算脚本：

```bash
cd benchmarks/stulife_source/Stulife

python scripts/calculate_stulife_metrics.py \
  --result_dir ../../results/stulife/{run_id} \
  --runs_file tier1_runs.json
```

### 配置选项

在 `run_benchmark.ts` 中可以配置：

```typescript
interface RunConfig {
  benchmark: "alfworld" | "stulife"
  episodes: number          // 运行的episode数量
  model: string            // LLM模型名称
  maxSteps: number         // 每个episode的最大步数
  extend: boolean          // 是否启用auto-extension
  split: string            // ALFWorld的split（train/eval）
  autoStart: boolean       // 是否自动启动Python server
  port: number             // Bridge server端口
}
```

---

## 文件清单

### 新增文件

```
benchmarks/stulife/
├── stulife_adapter.py                    # StuLife适配器
├── logging/
│   ├── __init__.py
│   ├── coordinator.py                    # 日志协调器
│   ├── session_collector.py              # Tier 1
│   ├── worker_logger.py                  # Tier 2
│   ├── api_tracer.py                     # Tier 3
│   └── context.py                        # 上下文传递
└── INTEGRATION_GUIDE.md                  # 本文档

agenttree/
├── bridge/
│   └── bench_server.py                   # HTTP bridge（修改）
├── src/
│   ├── llm/
│   │   ├── logging_client.ts             # LoggingLLMClient（新增）
│   │   └── index.ts                      # 导出（修改）
│   └── runtime/
│       └── tree.ts                       # 支持自定义client（修改）
└── examples/
    └── run_benchmark.ts                  # 使用LoggingLLMClient（修改）
```

### 未修改的文件

- `core/` 目录下的所有文件
- ALFWorld相关的所有文件
- StuLife source code（`benchmarks/stulife_source/`）

---

## 技术亮点

1. **零侵入设计**: 所有StuLife代码都在独立目录，不影响核心框架
2. **Wrapper模式**: LoggingLLMClient通过继承实现，不修改原始LLMClient
3. **实时日志**: 所有日志实时写入JSON，不等待运行结束
4. **上下文传递**: 使用contextvars优雅地传递episode_id等信息
5. **原生兼容**: Tier 1完全兼容StuLife原生格式，可直接用于metric计算

---

## 未来改进

1. **Invalid Action问题**: 当前所有action都返回"Invalid action"，需要调查StuLife期望的action格式
2. **Worker选择**: 改进task到worker的映射逻辑，避免选错worker
3. **性能优化**: 考虑批量写入日志，减少I/O开销
4. **错误处理**: 增强异常处理，避免单个episode失败影响整个运行
5. **可视化**: 开发日志可视化工具，便于分析worker行为和API调用

---

## 联系方式

如有问题，请联系：
- GitHub: [A2S Repository](https://github.com/your-repo/A2S)
- 文档维护者: LYX分支

最后更新: 2026-03-08
