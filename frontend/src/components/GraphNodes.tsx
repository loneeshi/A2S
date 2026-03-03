/**
 * Graph Nodes - 增强版图节点定义
 *
 * 复刻 Swarm-IDE 风格的高密度 Agent 卡片
 * - Glassmorphism 毛玻璃效果
 * - 状态呼吸灯
 * - 实时 Metrics 显示
 */

import React from 'react';
import { Handle, Position, NodeProps } from 'reactflow';
import {
  Brain,
  Cpu,
  CheckCircle2,
  AlertCircle,
  XCircle,
  Zap,
  Clock,
  Database
} from 'lucide-react';
import { motion } from 'framer-motion';

/**
 * Agent Node Component - 高密度信息卡片
 */
export const AgentNode: React.FC<NodeProps> = ({ data }) => {
  const {
    role,
    status,
    llm_call_count,
    total_tokens_used,
    isActive,
    isSelected,
    depth,
    llm_latency_ms,
    cache_hit_rate,
  } = data as any;

  // 状态颜色配置 - 更丰富的渐变效果
  const statusConfig = {
    idle: {
      bg: 'bg-gray-50/80 dark:bg-gray-800/60',
      border: 'border-gray-300 dark:border-gray-600',
      glow: 'shadow-gray-200/50 dark:shadow-gray-700/30',
      text: 'text-gray-600 dark:text-gray-400',
      statusColor: 'bg-gray-400',
    },
    thinking: {
      bg: 'bg-yellow-50/80 dark:bg-yellow-900/30',
      border: 'border-yellow-400 dark:border-yellow-600',
      glow: 'shadow-yellow-200/60 dark:shadow-yellow-500/30',
      text: 'text-yellow-700 dark:text-yellow-300',
      statusColor: 'bg-yellow-400 animate-pulse',
    },
    running: {
      bg: 'bg-blue-50/80 dark:bg-blue-900/30',
      border: 'border-blue-400 dark:border-blue-500',
      glow: 'shadow-blue-200/60 dark:shadow-blue-500/40',
      text: 'text-blue-700 dark:text-blue-200',
      statusColor: 'bg-blue-500 animate-pulse',
    },
    completed: {
      bg: 'bg-green-50/80 dark:bg-green-900/30',
      border: 'border-green-400 dark:border-green-600',
      glow: 'shadow-green-200/60 dark:shadow-green-500/30',
      text: 'text-green-700 dark:text-green-300',
      statusColor: 'bg-green-500',
    },
    failed: {
      bg: 'bg-red-50/80 dark:bg-red-900/30',
      border: 'border-red-400 dark:border-red-600',
      glow: 'shadow-red-200/60 dark:shadow-red-500/40',
      text: 'text-red-700 dark:text-red-300',
      statusColor: 'bg-red-500',
    },
  };

  const config = statusConfig[status] || statusConfig.idle;

  // Glassmorphism 效果
  const glassmorphismStyle = {
    backdropFilter: 'blur(12px)',
    WebkitBackdropFilter: 'blur(12px)',
    background: 'linear-gradient(135deg, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0.05) 100%)',
  };

  return (
    <motion.div
      initial={{ scale: 0.9, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ type: "spring", stiffness: 300, damping: 25 }}
      className={`
        relative backdrop-blur-md rounded-xl border-2
        min-w-[280px] cursor-pointer transition-all duration-300
        ${config.bg} ${config.border}
        ${isSelected ? 'ring-4 ring-blue-400/50 scale-105' : 'hover:scale-102'}
        ${isActive ? config.glow : ''}
        ${isActive ? 'animate-glow' : ''}
      `}
      style={glassmorphismStyle as any}
    >
      {/* Header 区：Role 图标和名称 */}
      <div className="px-4 pt-3 pb-2 border-b border-gray-200/50 dark:border-gray-700/50">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2 flex-1">
            <div className={`p-1.5 rounded-lg ${config.bg.replace('/80', '/100')}`}>
              <Brain className={`w-4 h-4 ${config.text}`} />
            </div>
            <div className="flex-1 min-w-0">
              <div className={`text-sm font-bold ${config.text} truncate`}>
                {role}
              </div>
              <div className="text-xs text-gray-500 dark:text-gray-400">
                Depth: {depth}
              </div>
            </div>
          </div>

          {/* 状态指示灯：呼吸灯效果 */}
          <div className={`
            w-3 h-3 rounded-full ${config.statusColor}
            shadow-[0_0_12px_currentColor]
          `} />
        </div>
      </div>

      {/* 实时 Metrics 区 */}
      <div className="px-4 py-3 space-y-2">
        {/* Token 统计和 Latency */}
        <div className="grid grid-cols-2 gap-2">
          <div className="bg-white/40 dark:bg-gray-900/40 rounded-lg p-2 border border-gray-200/50 dark:border-gray-700/50">
            <div className="flex items-center space-x-1 text-xs text-gray-600 dark:text-gray-400 mb-1">
              <Zap className="w-3 h-3" />
              <span>Tokens</span>
            </div>
            <div className={`text-sm font-mono font-bold ${config.text}`}>
              {(total_tokens_used || 0).toLocaleString()}
            </div>
          </div>

          <div className="bg-white/40 dark:bg-gray-900/40 rounded-lg p-2 border border-gray-200/50 dark:border-gray-700/50">
            <div className="flex items-center space-x-1 text-xs text-gray-600 dark:text-gray-400 mb-1">
              <Clock className="w-3 h-3" />
              <span>Latency</span>
            </div>
            <div className={`text-sm font-mono font-bold ${config.text}`}>
              {llm_latency_ms ? `${llm_latency_ms.toFixed(0)}ms` : 'N/A'}
            </div>
          </div>
        </div>

        {/* Cache 命中率 */}
        {cache_hit_rate !== undefined && (
          <div className="bg-white/40 dark:bg-gray-900/40 rounded-lg p-2 border border-gray-200/50 dark:border-gray-700/50">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-1 text-xs text-gray-600 dark:text-gray-400">
                <Database className="w-3 h-3" />
                <span>Cache Hit</span>
              </div>
              <div className={`
                text-xs font-bold px-2 py-0.5 rounded
                ${cache_hit_rate > 50 ? 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300' : 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300'}
              `}>
                {cache_hit_rate.toFixed(1)}%
              </div>
            </div>
          </div>
        )}

        {/* LLM 调用次数 */}
        <div className="flex items-center justify-between text-xs">
          <span className="text-gray-600 dark:text-gray-400">LLM Calls:</span>
          <span className={`font-mono font-semibold ${config.text}`}>
            {llm_call_count || 0}
          </span>
        </div>

        {/* 状态标签 */}
        <div className={`
          text-center py-1 px-2 rounded-lg text-xs font-semibold uppercase tracking-wide
          ${config.bg} ${config.text}
        `}>
          {status}
        </div>
      </div>

      {/* Input/Output Handles */}
      <Handle type="target" position={Position.Left} className="!bg-blue-500 !w-3 !h-3 !border-2 !border-white" />
      <Handle type="source" position={Position.Right} className="!bg-blue-500 !w-3 !h-3 !border-2 !border-white" />
    </motion.div>
  );
};

/**
 * Handoff Edge Component - 增强版流动动画
 */
const HandoffEdge: React.FC<any> = ({
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
}) => {
  const isAnimating = data?.isAnimating || false;
  const messageSize = data?.context_size || 1; // 用于控制连线粗细

  // 计算路径（支持曲线）
  const path = `M ${sourceX},${sourceY} L ${targetX},${targetY}`;

  return (
    <g>
      {/* 主连线 - 流光效果 */}
      <defs>
        <linearGradient id={`gradient-${data?.handoff_id}`} x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor={isAnimating ? '#3b82f6' : '#94a3b8'} stopOpacity={1} />
          <stop offset="100%" stopColor={isAnimating ? '#8b5cf6' : '#94a3b8'} stopOpacity={1} />
        </linearGradient>
      </defs>

      {/* 背景线 */}
      <path
        d={path}
        fill="none"
        stroke="#e2e8f0"
        strokeWidth={Math.max(2, messageSize * 2)}
        strokeDasharray="8 4"
        className="dark:stroke-gray-700"
      />

      {/* 流光主线 */}
      <path
        d={path}
        fill="none"
        stroke={`url(#gradient-${data?.handoff_id})`}
        strokeWidth={Math.max(2, messageSize * 1.5)}
        strokeDasharray="12 6"
        className={isAnimating ? 'animate-pulse' : ''}
        style={{
          animation: isAnimating ? 'dash 1s linear infinite' : 'none',
        }}
      >
        {isAnimating && (
          <animate
            attributeName="stroke-dashoffset"
            from="18"
            to="0"
            dur="1s"
            repeatCount="indefinite"
          />
        )}
      </path>

      {/* 流动的粒子效果 */}
      {isAnimating && (
        <circle r={4} fill="#3b82f6" className="opacity-80">
          <animateMotion
            dur="1.5s"
            repeatCount="indefinite"
            path={path}
            keyPoints="0;1"
            keyTimes="0;1"
          />
        </circle>
      )}
    </g>
  );
};

// Export node types and edge types AFTER component definitions
export const agentNodeTypes = {
  agentNode: AgentNode,
};

export const edgeTypes = {
  handoffEdge: HandoffEdge,
};
