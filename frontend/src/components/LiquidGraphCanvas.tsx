/**
 * Liquid Graph Canvas - 流动拓扑画布
 *
 * 实现实时的、流动的 Agent 协作拓扑图
 * - 动态节点展示 Agent 状态
 * - 流动动画展示任务 Handoff
 * - 实时更新基于 Streaming 数据
 */

import React, { useEffect, useRef, useState, useCallback } from 'react';
import ReactFlow, {
  Node,
  Edge,
  Background,
  Controls,
  MiniMap,
  NodeTypes,
  Position,
  EdgeTypes,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { motion, AnimatePresence } from 'framer-motion';
import { agentNodeTypes, edgeTypes } from './GraphNodes';
import { useAgentStore } from '../store/agentStore';
import { useTimelineStore } from '../store/timelineStore';
import { calculateNodePosition } from '../utils/graphLayout';

interface LiquidGraphCanvasProps {
  className?: string;
  onNodeClick?: (nodeId: string) => void;
}

export const LiquidGraphCanvas: React.FC<LiquidGraphCanvasProps> = ({
  className = '',
  onNodeClick,
}) => {
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);

  // Store state
  const {
    agentStates,
    handoffs,
    selectedAgentId,
    selectAgent,
  } = useAgentStore();

  const {
    currentTime,
    isPlaying,
    playbackSpeed,
  } = useTimelineStore();

  // 转换 Agent 状态为节点
  useEffect(() => {
    const agentNodes: Node[] = Object.values(agentStates || {}).map((agent) => {
      const isActive = agent.status === 'running' || agent.status === 'thinking';
      const isSelected = agent.node_id === selectedAgentId;

      return {
        id: agent.node_id,
        type: 'agentNode',
        position: calculateNodePosition(agent),
        data: {
          ...agent,
          isActive,
          isSelected,
          onClick: () => {
            selectAgent(agent.node_id);
            onNodeClick?.(agent.node_id);
          },
        },
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
      };
    });

    setNodes(agentNodes);
  }, [agentStates, selectedAgentId, selectAgent, onNodeClick]);

  // 转换 Handoff 为边（带流动动画）
  useEffect(() => {
    const handoffEdges: Edge[] = (handoffs || []).map((handoff, index) => {
      const isAnimating = handoff.timestamp <= currentTime;
      const animationDelay = index * 100; // 错开动画

      return {
        id: handoff.handoff_id,
        source: handoff.from_agent_id,
        target: handoff.to_agent_id,
        type: 'handoffEdge',
        animated: isAnimating,
        data: {
          ...handoff,
          isAnimating,
          animationDelay,
        },
        style: {
          stroke: isAnimating ? '#3b82f6' : '#94a3b8',
          strokeWidth: isAnimating ? 3 : 2,
          strokeDasharray: '5 5',
        },
      };
    });

    setEdges(handoffEdges);
  }, [handoffs, currentTime]);

  // Handoff 粒子效果
  useEffect(() => {
    if (!isPlaying) return;

    const interval = setInterval(() => {
      // 更新流动动画
      setEdges((prevEdges) =>
        prevEdges.map((edge) => ({
          ...edge,
          animated: edge.data?.isAnimating,
        }))
      );
    }, 1000 / playbackSpeed);

    return () => clearInterval(interval);
  }, [isPlaying, playbackSpeed, handoffs]);

  return (
    <div className={`liquid-graph-canvas ${className}`} ref={reactFlowWrapper}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={agentNodeTypes as NodeTypes}
        edgeTypes={edgeTypes as EdgeTypes}
        fitView
        attributionPosition="bottom-left"
        minZoom={0.3}
        maxZoom={2}
        defaultEdgeOptions={{
          style: { strokeWidth: 2, stroke: '#94a3b8' },
          type: 'smoothstep',
          animated: false,
        }}
      >
        <Background color="#94a3b8" gap={16} />
        <Controls />

        {/* 迷你地图 */}
        <MiniMap
          nodeColor={(node) => {
            const data = node.data as any;
            if (data?.isActive) return '#3b82f6';
            if (data?.isSelected) return '#f59e0b';
            return '#64748b';
          }}
          maskColor="rgba(0, 0, 0, 0.1)"
        />

        {/* Handoff 流动指示器 */}
        <HandoffFlowIndicator />
      </ReactFlow>

      {/* 图例 */}
      <GraphLegend />

      {/* 实时统计 */}
      <LiveStatistics />
    </div>
  );
};

/**
 * Handoff 流动指示器
 * 显示当前正在进行的任务移交
 */
const HandoffFlowIndicator: React.FC = () => {
  const { handoffs } = useAgentStore();
  const { currentTime } = useTimelineStore();
  const activeHandoffs = (handoffs || []).filter(
    (h) => Math.abs(h.timestamp - currentTime) < 2000 // 2秒内的活跃移交
  );

  return (
    <div className="absolute top-4 left-4 z-10">
      <AnimatePresence>
        {activeHandoffs.map((handoff) => (
          <motion.div
            key={handoff.handoff_id}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
            className="mb-2 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-3 shadow-lg"
          >
            <div className="flex items-center space-x-2">
              <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
              <div className="text-sm font-medium text-blue-900 dark:text-blue-100">
                {handoff.from_agent_id.slice(0, 8)} → {handoff.to_agent_role}
              </div>
            </div>
            <div className="text-xs text-blue-700 dark:text-blue-300 mt-1 truncate">
              {handoff.message_content}
            </div>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
};

/**
 * 图例组件
 */
const GraphLegend: React.FC = () => {
  return (
    <div className="absolute bottom-4 left-4 z-10 bg-white dark:bg-gray-800 rounded-lg shadow-lg p-3 border border-gray-200 dark:border-gray-700">
      <div className="text-xs font-semibold text-gray-700 dark:text-gray-300 mb-2">
        Agent Status
      </div>
      <div className="space-y-1.5">
        <LegendItem
          color="#3b82f6"
          label="Running"
          description="Agent is currently executing"
        />
        <LegendItem
          color="#10b981"
          label="Completed"
          description="Task completed successfully"
        />
        <LegendItem
          color="#f59e0b"
          label="Thinking"
          description="LLM is processing"
        />
        <LegendItem
          color="#ef4444"
          label="Failed"
          description="Execution failed"
        />
      </div>
    </div>
  );
};

const LegendItem: React.FC<{
  color: string;
  label: string;
  description: string;
}> = ({ color, label, description }) => {
  return (
    <div className="flex items-center space-x-2">
      <div
        className="w-3 h-3 rounded-full"
        style={{ backgroundColor: color }}
      />
      <div>
        <div className="text-xs font-medium text-gray-900 dark:text-gray-100">
          {label}
        </div>
        <div className="text-xs text-gray-500 dark:text-gray-400">
          {description}
        </div>
      </div>
    </div>
  );
};

/**
 * 实时统计组件
 */
const LiveStatistics: React.FC = () => {
  const { agentStates } = useAgentStore();
  const { currentTime } = useTimelineStore();

  const totalAgents = Object.keys(agentStates || {}).length;
  const activeAgents = Object.values(agentStates || {}).filter(
    (a) => a.status === 'running' || a.status === 'thinking'
  ).length;
  const completedAgents = Object.values(agentStates || {}).filter(
    (a) => a.status === 'completed'
  ).length;

  return (
    <div className="absolute top-4 right-4 z-10 bg-white dark:bg-gray-800 rounded-lg shadow-lg p-3 border border-gray-200 dark:border-gray-700 min-w-[200px]">
      <div className="text-xs font-semibold text-gray-700 dark:text-gray-300 mb-2">
        Live Statistics
      </div>
      <div className="space-y-2">
        <StatRow label="Total Agents" value={totalAgents} />
        <StatRow label="Active" value={activeAgents} color="#3b82f6" />
        <StatRow label="Completed" value={completedAgents} color="#10b981" />
        <div className="pt-2 border-t border-gray-200 dark:border-gray-700">
          <div className="text-xs text-gray-500 dark:text-gray-400">
            Timeline: {typeof currentTime === 'number' ? currentTime.toFixed(0) : currentTime}ms
          </div>
        </div>
      </div>
    </div>
  );
};

const StatRow: React.FC<{
  label: string;
  value: number;
  color?: string;
}> = ({ label, value, color }) => {
  return (
    <div className="flex items-center justify-between">
      <span className="text-xs text-gray-600 dark:text-gray-400">{label}</span>
      <span
        className="text-sm font-semibold"
        style={{ color: color || '#64748b' }}
      >
        {value}
      </span>
    </div>
  );
};

export default LiquidGraphCanvas;
