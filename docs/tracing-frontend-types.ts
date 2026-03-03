/**
 * Agent Execution Tracing - Frontend Type Definitions
 *
 * 前端可视化界面的 TypeScript 类型定义
 * 用于实现"去黑箱化"展示
 */

// ===== Enums =====

enum NodeType {
  ROOT = "root",
  MANAGER = "manager",
  WORKER = "worker",
  HUMAN = "human",
  REFLECTION = "reflection",
  TOOL_EXECUTOR = "tool_executor"
}

enum NodeStatus {
  IDLE = "idle",
  THINKING = "thinking",
  RUNNING = "running",
  WAITING = "waiting",
  COMPLETED = "completed",
  FAILED = "failed",
  INTERRUPTED = "interrupted"
}

enum EventType {
  NODE_CREATED = "node_created",
  NODE_STARTED = "node_started",
  NODE_COMPLETED = "node_completed",
  NODE_FAILED = "node_failed",
  LLM_CALL_START = "llm_call_start",
  LLM_CALL_COMPLETE = "llm_call_complete",
  TOOL_CALL_START = "tool_call_start",
  TOOL_CALL_COMPLETE = "tool_call_complete",
  HANDOFF_START = "handoff_start",
  HANDOFF_COMPLETE = "handoff_complete",
  CACHE_HIT = "cache_hit",
  CACHE_MISS = "cache_miss",
  REFLECTION_START = "reflection_start",
  REFLECTION_COMPLETE = "reflection_complete",
  HEARTBEAT = "heartbeat"
}

enum CacheStatus {
  HIT = "hit",
  PARTIAL = "partial",
  MISS = "miss",
  DISABLED = "disabled"
}

// ===== Interfaces =====

/**
 * 提示词缓存信息
 */
interface PromptCachingInfo {
  status: CacheStatus;
  cache_hit_position?: number;
  cache_hit_tokens: number;
  total_tokens: number;
  cache_key?: string;
  cache_hit_percentage: number;
}

/**
 * 工具调用记录
 */
interface ToolCallRecord {
  call_id: string;
  tool_name: string;
  arguments: Record<string, any>;
  start_time: string;
  end_time?: string;
  status: "pending" | "success" | "error";
  result?: Record<string, any>;
  error_message?: string;
  execution_time_ms: number;
  metadata: Record<string, any>;
}

/**
 * 移交向量
 */
interface HandoffVector {
  handoff_id: string;
  from_agent_id: string;
  to_agent_id: string;
  to_agent_role: string;
  timestamp: string;
  message_content: string;
  context_transferred: string[];
  response_required: boolean;
}

/**
 * LLM API 调用追踪
 */
interface LLMApiCallTrace {
  call_id: string;
  timestamp: string;
  model: string;
  messages: Array<{role: string; content: string}>;
  tools?: Array<{name: string; description: string}>;
  temperature: number;
  max_tokens?: number;

  // 思考过程
  thinking_time_ms: number;
  reasoning_steps: string[];

  // API 响应
  response_content: string;
  tool_calls?: Array<{
    id: string;
    type: string;
    function: {name: string; arguments: string};
  }>;
  finish_reason?: string;

  // Token 使用
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;

  // 缓存信息
  cache_info?: PromptCachingInfo;

  // 性能指标
  latency_ms: number;
  ttft_ms?: number;

  // 错误信息
  error?: string;
  retry_count: number;
}

/**
 * Benchmark 上下文（ALFWorld 等）
 */
interface BenchmarkContext {
  benchmark_name: string;
  task_type?: string;

  // ALFWorld 特定字段
  available_commands?: string[];
  observation?: string;
  background?: string;

  // 通用字段
  step_number: number;
  max_steps: number;
  reward: number;
  done: boolean;
  won: boolean;

  metadata: Record<string, any>;
}

/**
 * 反思追踪
 */
interface ReflectionTrace {
  reflection_id: string;
  timestamp: string;
  trigger_reason: string;

  // 反思的输入
  original_action?: string;
  action_result?: Record<string, any>;
  agent_state?: Record<string, any>;

  // 反思过程
  reflection_prompt: string;
  thinking_process: string[];

  // 反思结果
  reflection_content: string;
  suggested_improvements: string[];
  confidence_score: number;
  should_retry: boolean;

  // 性能指标
  reflection_time_ms: number;
  llm_calls: number;
  tokens_used: number;
}

/**
 * 动态记忆快照
 */
interface DynamicMemory {
  snapshot_id: string;
  timestamp: string;

  short_term_memory: string[];
  long_term_memory: Array<{key: string; value: any}>;
  working_memory: Record<string, any>;

  total_memories: number;
  memory_size_bytes: number;

  importance_scores: Record<string, number>;
}

/**
 * 追踪事件
 */
interface TraceEvent {
  event_id: string;
  event_type: EventType;
  timestamp: string;
  node_id: string;

  content: Record<string, any>;

  related_event_ids: string[];
  parent_event_id?: string;

  // 数据负载
  llm_call_trace?: LLMApiCallTrace;
  tool_call_record?: ToolCallRecord;
  handoff_vector?: HandoffVector;
  reflection_trace?: ReflectionTrace;
  benchmark_context?: BenchmarkContext;

  metadata: Record<string, any>;
}

/**
 * Agent 节点状态
 */
interface AgentNodeState {
  node_id: string;
  node_type: NodeType;
  role: string;

  // System Prompts 和 Messages
  system_prompt: string;
  user_messages: Array<{role: string; content: string}>;
  tools: Array<{name: string; description: string}>;

  // 状态信息
  status: NodeStatus;
  created_at: string;
  started_at?: string;
  completed_at?: string;

  // 层级关系
  parent_id?: string;
  child_ids: string[];
  depth: number;

  // 执行上下文
  dynamic_memory?: DynamicMemory;
  benchmark_context?: BenchmarkContext;

  // 性能指标
  total_execution_time_ms: number;
  llm_call_count: number;
  tool_call_count: number;
  total_tokens_used: number;
  total_cost_usd: number;

  // 子 Agent 和移交
  handoffs: HandoffVector[];

  // 错误信息
  error_message?: string;
  error_stack?: string;

  metadata: Record<string, any>;
}

/**
 * 执行树节点（用于前端可视化）
 */
interface ExecutionTreeNode {
  node: AgentNodeState;
  children: ExecutionTreeNode[];
  events: TraceEvent[];
}

/**
 * 任务执行追踪
 */
interface TaskTrace {
  trace_id: string;
  task_name: string;
  task_description: string;

  started_at: string;
  completed_at?: string;
  duration_ms: number;

  root_node?: AgentNodeState;
  all_nodes: Record<string, AgentNodeState>;
  events: TraceEvent[];

  // 统计信息
  total_nodes: number;
  total_events: number;
  total_llm_calls: number;
  total_tool_calls: number;
  total_tokens_used: number;
  total_cost_usd: number;

  // 最终结果
  success: boolean;
  final_result?: Record<string, any>;
  error_message?: string;

  metadata: Record<string, any>;
}

// ===== Frontend Visualization Components =====

/**
 * 追踪可视化组件 Props
 */
interface TraceVisualizationProps {
  trace: TaskTrace;
  onNodeClick?: (nodeId: string) => void;
  onEventClick?: (eventId: string) => void;
  selectedNodeId?: string;
  selectedEventId?: string;
}

/**
 * 节点状态卡片 Props
 */
interface NodeStateCardProps {
  node: AgentNodeState;
  events: TraceEvent[];
  showBenchmarkContext?: boolean;
  showDynamicMemory?: boolean;
  showTools?: boolean;
}

/**
 * LLM 调用详情 Props
 */
interface LLMDetailsProps {
  llmCall: LLMApiCallTrace;
  showCacheInfo?: boolean;
  showReasoning?: boolean;
}

/**
 * 时间线事件 Props
 */
interface TimelineEventProps {
  event: TraceEvent;
  position: "left" | "right";
  onClick?: () => void;
}

// ===== Visualization Helper Functions =====

/**
 * 获取节点的所有事件（按时间排序）
 */
function getEventsForNode(
  trace: TaskTrace,
  nodeId: string
): TraceEvent[] {
  return trace.events
    .filter(e => e.node_id === nodeId)
    .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
}

/**
 * 获取节点的执行路径（从根到该节点）
 */
function getExecutionPath(
  trace: TaskTrace,
  nodeId: string
): AgentNodeState[] {
  const path: AgentNodeState[] = [];
  let currentNode = trace.all_nodes[nodeId];

  while (currentNode) {
    path.unshift(currentNode);
    if (currentNode.parent_id) {
      currentNode = trace.all_nodes[currentNode.parent_id];
    } else {
      break;
    }
  }

  return path;
}

/**
 * 计算节点的总成本（包括所有子节点）
 */
function calculateTotalCost(
  trace: TaskTrace,
  nodeId: string
): number {
  const node = trace.all_nodes[nodeId];
  if (!node) return 0;

  let total = node.total_cost_usd;

  for (const childId of node.child_ids) {
    total += calculateTotalCost(trace, childId);
  }

  return total;
}

/**
 * 获取缓存命中率统计
 */
function getCacheStatistics(
  trace: TaskTrace,
  nodeId?: string
): {
  totalCalls: number;
  cacheHits: number;
  cacheMisses: number;
  partialHits: number;
  hitRate: number;
} {
  const events = nodeId
    ? getEventsForNode(trace, nodeId)
    : trace.events;

  const llmCalls = events.filter(e =>
    e.event_type === EventType.LLM_CALL_COMPLETE &&
    e.llm_call_trace
  );

  const cacheHits = llmCalls.filter(e =>
    e.llm_call_trace!.cache_info?.status === CacheStatus.HIT
  ).length;

  const partialHits = llmCalls.filter(e =>
    e.llm_call_trace!.cache_info?.status === CacheStatus.PARTIAL
  ).length;

  const cacheMisses = llmCalls.filter(e =>
    e.llm_call_trace!.cache_info?.status === CacheStatus.MISS
  ).length;

  return {
    totalCalls: llmCalls.length,
    cacheHits,
    cacheMisses,
    partialHits,
    hitRate: llmCalls.length > 0
      ? ((cacheHits + partialHits) / llmCalls.length) * 100
      : 0
  };
}

/**
 * 导出类型定义
 */
export type {
  NodeType,
  NodeStatus,
  EventType,
  CacheStatus,
  PromptCachingInfo,
  ToolCallRecord,
  HandoffVector,
  LLMApiCallTrace,
  BenchmarkContext,
  ReflectionTrace,
  DynamicMemory,
  TraceEvent,
  AgentNodeState,
  ExecutionTreeNode,
  TaskTrace,
  TraceVisualizationProps,
  NodeStateCardProps,
  LLMDetailsProps,
  TimelineEventProps
};

export {
  getEventsForNode,
  getExecutionPath,
  calculateTotalCost,
  getCacheStatistics
};
