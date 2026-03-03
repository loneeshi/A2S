/**
 * Graph Nodes - 增强版图节点定义
 *
 * 复刻 Swarm-IDE 风格的高密度 Agent 卡片
 * - SPEC_v1.0 Obsidian/Deep-Space Aesthetic
 * - 实时 Metrics 显示 (去黑箱化)
 * - Liquid Flow 动态连线
 */

import React from 'react';
import { Handle, Position, NodeProps, EdgeProps, getBezierPath } from 'reactflow';
import { motion } from 'framer-motion';

// 基于 SPEC_v1.0 的状态芯片样式
const StatusChip = ({ state }: { state: string }) => {
  const configs: Record<string, string> = {
    thinking: "border-brand-primary/40 text-brand-primary animate-pulse",
    running: "border-brand-accent/40 text-brand-accent animate-bounce",
    idle: "border-zinc-700 text-zinc-500",
    completed: "border-green-500/40 text-green-500",
    failed: "border-red-500/40 text-red-500"
  };
  return (
    <div className={`flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-mono border uppercase tracking-wider ${configs[state] || configs.idle}`}>
      <span className={`w-1.5 h-1.5 rounded-full bg-current`} />
      {state}
    </div>
  );
};

/**
 * Agent Node Component - 高密度信息卡片 (SPEC_v1.0)
 */
export const AgentNode: React.FC<NodeProps> = ({ data }) => {
  const {
    role,
    status,
    total_tokens_used,
    llm_latency_ms,
    id,
  } = data as any;

  return (
    <div className="bg-brand-card p-4 rounded-xl border border-white/5 shadow-2xl min-w-[220px] font-sans transition-all duration-300 hover:border-brand-primary/30">
      <Handle type="target" position={Position.Left} className="!w-2 !h-2 !bg-brand-primary !border-0 opacity-0 group-hover:opacity-100" />

      {/* Header: Role & Status */}
      <div className="flex justify-between items-start mb-4">
        <div className="w-8 h-8 bg-brand-primary/10 rounded flex items-center justify-center border border-brand-primary/20">
           <svg className="w-4 h-4 text-brand-primary" fill="currentColor" viewBox="0 0 24 24">
             <path d="M12 2L2 19h20L12 2zm0 3.3l7.2 12.4H4.8L12 5.3z" />
           </svg>
        </div>
        <StatusChip state={status || 'idle'} />
      </div>

      {/* Body: Agent Identity */}
      <div className="mb-4">
        <h3 className="text-sm font-bold text-white tracking-tight">{role}</h3>
        <p className="text-[10px] text-brand-text font-mono mt-1 uppercase">ID: {id || 'N/A'}</p>
      </div>

      {/* Metrics: 去黑箱化关键数据 */}
      <div className="grid grid-cols-2 gap-2 pt-3 border-t border-brand-border">
        <div>
          <p className="text-[9px] text-zinc-500 uppercase font-bold">Tokens</p>
          <p className="text-xs font-mono text-brand-primary">{(total_tokens_used || 0).toLocaleString()}</p>
        </div>
        <div>
          <p className="text-[9px] text-zinc-500 uppercase font-bold">Latency</p>
          <p className="text-xs font-mono text-brand-accent">{llm_latency_ms ? `${llm_latency_ms.toFixed(0)}ms` : '0ms'}</p>
        </div>
      </div>

      <Handle type="source" position={Position.Right} className="!w-2 !h-2 !bg-brand-primary !border-0 opacity-0 group-hover:opacity-100" />
    </div>
  );
};

/**
 * Handoff Edge Component - Liquid Flow 增强版流动动画
 */
export const HandoffEdge: React.FC<EdgeProps> = ({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
}) => {
  const [edgePath] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  const isAnimating = data?.isAnimating;

  return (
    <g>
      <defs>
        <linearGradient id={`liquid-gradient-${id}`} x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#3c83f6" stopOpacity="0.2" />
          <stop offset="50%" stopColor="#a855f7" stopOpacity="0.6" />
          <stop offset="100%" stopColor="#3c83f6" stopOpacity="0.2" />
        </linearGradient>
      </defs>

      {/* Background Shadow Line */}
      <path
        d={edgePath}
        fill="none"
        stroke="#27272a"
        strokeWidth={3}
        className="opacity-50"
      />

      {/* Animated Flow Line */}
      <motion.path
        d={edgePath}
        fill="none"
        stroke={`url(#liquid-gradient-${id})`}
        strokeWidth={2}
        initial={{ strokeDasharray: "10 5", strokeDashoffset: 0 }}
        animate={isAnimating ? {
          strokeDashoffset: [-20, 0],
        } : {}}
        transition={{
          duration: 1.5,
          repeat: Infinity,
          ease: "linear",
        }}
        className="a2s-liquid-flow"
      />

      {/* Glow Particle */}
      {isAnimating && (
        <motion.circle
          r="3"
          fill="#a855f7"
          initial={{ offsetDistance: "0%" }}
          animate={{ offsetDistance: "100%" }}
          transition={{
            duration: 2,
            repeat: Infinity,
            ease: "easeInOut",
          }}
          style={{ offsetPath: `path("${edgePath}")` }}
          className="shadow-[0_0_8px_#a855f7]"
        />
      )}
    </g>
  );
};

// Export node types and edge types
export const agentNodeTypes = {
  agentNode: AgentNode,
};

export const edgeTypes = {
  handoffEdge: HandoffEdge,
};
