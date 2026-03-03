# Agent Visualization Frontend

专业的 Agent 系统可视化界面，实现完整的"去黑箱化"体验。

## 🎯 功能特性

### 1. **Liquid Graph Canvas（流动拓扑画布）**
- ✅ 实时流动的 Agent 协作拓扑图
- ✅ 动态连线展示任务 Handoff
- ✅ 节点状态实时更新
- ✅ 活跃移交指示器
- ✅ 实时统计面板

### 2. **Agent Cognitive Inspector（智能体认知观察器）**
点击任意 Agent 节点，查看全透明报告：

- **Memory Monitor** - 实时局部记忆
  - Short-term Memory: 短期记忆
  - Long-term Memory: 长期知识
  - Working Memory: 当前任务上下文
  - 重要度评分

- **Prompt Cache Viewer** - 缓存可视化
  - 颜色标记：绿色（命中）、黄色（部分）、红色（未命中）
  - 缓存命中位置和百分比
  - Token 位置分布图
  - 性能优化建议

- **LLM Call History** - LLM 调用历史
- **Tool Calls** - 工具调用记录
- **Benchmark Context** - 环境上下文（ALFWorld 等）

### 3. **Timeline Scrubber（时间轴回溯器）**
- ✅ 拖动时间轴回溯历史状态
- ✅ 播放/暂停/速度控制
- ✅ 键盘快捷键支持
- ✅ 关键事件标记
- ✅ 严格因果分析模式
- ✅ 当前时刻活跃事件显示

## 🚀 快速开始（推荐流程）

### ⚡ 3 步快速启动

```bash
# 步骤 1: 生成追踪数据（后端）
cd /Users/dp/Agent_research/design/auto_expansion_agent
python examples/tracing_example.py
# 生成: results/traces/trace_*.json

# 步骤 2: 启动前端（开发模式）
cd frontend
npm install      # 首次运行需要安装依赖
npm run dev      # 启动开发服务器（热重载）

# 步骤 3: 加载数据
# 浏览器打开 http://localhost:5173
# 点击 "Load Agent Trace" 上传 trace_*.json
# 或点击 "Load Sample Data" 使用示例数据
```

### 📝 详细说明

#### 1️⃣ 生成追踪数据（可选）

**后端**生成追踪数据的步骤：

```bash
cd /Users/dp/Agent_research/design/auto_expansion_agent
python examples/tracing_example.py
```

生成的文件：
```
results/traces/
├── trace_9e098c3e...json           # 完整追踪数据（17KB）
├── trace_9e098c3e...tree.json      # 执行树（2.8KB）
└── trace_9e098c3e...stats.json     # 统计摘要（299B）
```

**提示**：
- ✅ 如果已经有追踪数据，可以跳过此步骤
- ✅ 前端提供 "Load Sample Data" 选项，使用示例数据
- ✅ 数据可以重用，不需要每次重新生成

#### 2️⃣ 启动前端

```bash
cd frontend

# 首次运行：安装依赖
npm install

# 启动开发服务器
npm run dev
```

访问 http://localhost:5173

**为什么使用 `npm run dev`？**
- ✅ **热重载**：修改代码自动刷新浏览器
- ✅ **快速启动**：秒级启动
- ✅ **调试友好**：Source Map 支持
- ✅ **开发体验好**

**什么时候用 `npm run build`？**
- ❌ 开发时不推荐（慢、无热重载）
- ✅ 部署到生产环境时使用
- ✅ 构建成静态文件（dist/ 目录）

#### 3️⃣ 加载和可视化数据

1. 浏览器打开 http://localhost:5173
2. 点击 "Load Agent Trace" 按钮
3. 选择生成的 `trace_*.json` 文件
4. 或点击 "Load Sample Data" 使用示例

### 🏢 生产部署（可选）

如果需要部署到生产环境：

```bash
# 构建静态文件
npm run build

# 预览构建结果
npm run preview

# 部署 dist/ 目录到服务器
```

## 📖 使用指南

### 界面交互

#### 液动拓扑画布
- **点击节点**: 查看详情
- **拖拽画布**: 平移视图
- **滚轮**: 缩放
- **双击**: 聚焦节点

#### 时间轴控制
- **拖动滑块**: 回溯时间
- **空格键**: 播放/暂停
- **←/→**: 前进/后退 1 秒
- **Home/End**: 跳到开始/结束
- **速度控制**: 0.25x ~ 4x

#### Agent 观察器
- **Tab 切换**: Overview / Memory / Cache / LLM / Tools / Benchmark
- **折叠面板**: 点击标题栏
- **缓存详情**: 展开查看 Token 级别

## 🎨 界面布局

```
┌─────────────────────────────────────────────────────────────┐
│                        Header                               │
├──────────────────────────────┬──────────────────────────────┤
│                              │                              │
│      Liquid Graph Canvas      │   Agent Cognitive           │
│      (70% width)             │   Inspector                 │
│                              │   (30% width)                │
│  ┌────────────────────────┐  │  ┌────────────────────────┐ │
│  │  Agent Nodes (动态)    │  │  │  Agent Details         │ │
│  │   ┌───┐               │  │  │  ┌──────────────────┐  │ │
│  │   │ A │────┐          │  │  │  │ Memory Monitor   │  │ │
│  │   └───┘    │          │  │  │  ├──────────────────┤  │ │
│  │      ┌────▼───┐       │  │  │  │ Cache Viewer     │  │ │
│  │      │ Agent B │       │  │  │  ├──────────────────┤  │ │
│  │      └────┬───┘       │  │  │  │ LLM Calls        │  │ │
│  │           ┌▼───┐      │  │  │  └──────────────────┘  │ │
│  │           │ C   │      │  │  │                          │ │
│  │           └────┘      │  │  │                          │ │
│  └────────────────────────┘  │  └────────────────────────┘ │
│                              │                              │
├──────────────────────────────┴──────────────────────────────┤
│                   Timeline Scrubber                         │
│  [◀◀] [▶] [▶▶] [━━━━━◉━━━━━━━] Speed: 1x 0:05 / 0:15     │
└─────────────────────────────────────────────────────────────┘
```

## 📊 数据结构

### Agent 状态
```typescript
interface AgentState {
  node_id: string;
  role: string;
  status: 'idle' | 'thinking' | 'running' | 'completed';
  system_prompt: string;
  dynamic_memory: {
    short_term_memory: string[];
    long_term_memory: object[];
    working_memory: Record<string, any>;
  };
  benchmark_context?: {
    available_commands: string[];
    observation: string;
    background: string;
  };
  // ... more fields
}
```

### Prompt Caching
```typescript
interface PromptCachingInfo {
  status: 'hit' | 'partial' | 'miss';
  cache_hit_position: number;     // Token 位置
  cache_hit_tokens: number;        // 命中数量
  total_tokens: number;
  cache_hit_percentage: number;    // 命中率
}
```

### Handoff
```typescript
interface Handoff {
  handoff_id: string;
  from_agent_id: string;
  to_agent_id: string;
  to_agent_role: string;
  timestamp: string;
  message_content: string;
  context_transferred: string[];
}
```

## 🛠️ 技术栈

- **React 18** - UI 框架
- **TypeScript** - 类型安全
- **Zustand** - 状态管理
- **React Flow** - 流程图/拓扑图
- **Framer Motion** - 动画效果
- **Tailwind CSS** - 样式
- **D3.js** - 数据可视化

## 📁 项目结构

```
frontend/
├── src/
│   ├── components/
│   │   ├── LiquidGraphCanvas.tsx      # 流动拓扑画布
│   │   ├── AgentCognitiveInspector.tsx # 认知观察器
│   │   ├── TimelineScrubber.tsx       # 时间轴回溯器
│   │   ├── LoadTraceData.tsx          # 数据加载
│   │   ├── Header.tsx                 # 顶部栏
│   │   ├── inspector/                 # Inspector 子组件
│   │   │   ├── MemoryMonitor.tsx       # 记忆监控
│   │   │   ├── PromptCacheViewer.tsx  # 缓存查看器
│   │   │   ├── LLMCallHistory.tsx     # LLM 历史
│   │   │   ├── ToolCallList.tsx       # 工具调用列表
│   │   │   └── BenchmarkContextPanel.tsx
│   │   ├── GraphNodes.tsx             # 图节点定义
│   │   └── graphLayout.ts             # 图布局算法
│   ├── store/
│   │   ├── agentStore.ts              # Agent 状态管理
│   │   └── timelineStore.ts           # 时间轴状态管理
│   ├── utils/
│   │   ├── timeFormat.ts              # 时间格式化
│   │   └── graphLayout.ts             # 图布局计算
│   ├── App.tsx                        # 主应用
│   ├── main.tsx                       # 入口
│   └── vite-env.d.ts                  # Vite 类型声明
├── package.json
├── tsconfig.json
├── vite.config.ts
└── tailwind.config.js
```

## 🎯 核心组件说明

### LiquidGraphCanvas
**职责**: 展示 Agent 协作拓扑

**特性**:
- 实时更新节点状态
- 流动动画展示 Handoff
- 迷你地图导航
- 统计信息浮层

### AgentCognitiveInspector
**职责**: 显示 Agent 详细信息

**特性**:
- Tab 切换不同视图
- Memory Monitor 实时记忆
- Prompt Cache 颜色标记
- 可折叠面板

### TimelineScrubber
**职责**: 时间轴回溯

**特性**:
- 拖动定位
- 播放控制
- 键盘快捷键
- 关键帧标记
- 因果分析模式

## 💡 使用场景

### 场景 1: 性能分析
1. 加载追踪数据
2. 打开 Prompt Cache Viewer
3. 分析缓存命中率
4. 找出未缓存的 Prompt
5. 优化 Prompt 结构

### 场景 2: 调试协作流程
1. 观察 Liquid Graph 上的 Handoff
2. 点击问题 Agent 节点
3. 查看 Memory 中的上下文
4. 回溯时间轴查看决策过程

### 场景 3: 成本优化
1. 查看 Token 消耗统计
2. 找出高频 LLM 调用
3. 分析缓存命中情况
4. 优化 Agent 提示词

## 🔧 开发指南

### 添加新的 Inspector Tab

```typescript
// 1. 创建组件
const MyNewTab: React.FC<{ agent: any }> = ({ agent }) => {
  return <div>My Content</div>;
};

// 2. 在 AgentCognitiveInspector 中添加
const tabs = [
  // ... existing tabs
  { id: 'mytab', label: 'My Tab', icon: MyIcon },
];

// 3. 在渲染部分添加
{activeTab === 'mytab' && <MyNewTab agent={selectedAgent} />}
```

### 自定义节点样式

```typescript
// GraphNodes.tsx
export const AgentNode: React.FC<NodeProps> = ({ data }) => {
  return (
    <div className="custom-node">
      {/* Custom node content */}
    </div>
  );
};
```

### 添加新的关键帧类型

```typescript
// timelineStore.ts
addKeyframe({
  id: 'my-keyframe',
  time: Date.now(),
  label: 'Important Event',
  description: 'Event details',
});
```

## 🐛 常见问题

### Q: 加载文件后没有显示？
**A**: 检查 JSON 格式是否正确，文件是否包含 `all_nodes` 和 `events` 字段。

### Q: 时间轴无法播放？
**A**: 确保 `maxTime` 大于 `minTime`，检查事件时间戳是否正确。

### Q: 节点不显示？
**A**: 检查节点数据是否包含必要的字段：`node_id`, `role`, `status`, `created_at`。

### Q: 缓存信息不显示？
**A**: 确保 LLM 调用事件包含 `llm_call_trace.cache_info`。

## 📚 相关文档

- [追踪系统后端](../docs/TRACING_GUIDE.md)
- [前端类型定义](../docs/tracing-frontend-types.ts)
- [使用示例](../examples/tracing_example.py)

## 🎉 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT
