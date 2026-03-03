/**
 * Agent Cognitive Inspector - 智能体认知观察器
 *
 * 点击拓扑图中的 Agent 节点后，显示该 Agent 的全透明报告
 * - Memory Monitor: 实时查看局部记忆
 * - Prompt Cache Viewer: 可视化缓存命中
 * - LLM Call History: 调用历史
 * - Tool Calls: 工具调用记录
 * - Benchmark Context: 环境上下文
 */

import React, { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAgentStore } from '../store/agentStore';
import { useTimelineStore } from '../store/timelineStore';
import { MemoryMonitor } from './inspector/MemoryMonitor';
import { PromptCacheViewer } from './inspector/PromptCacheViewer';
import { LLMCallHistory } from './inspector/LLMCallHistory';
import { ToolCallList } from './inspector/ToolCallList';
import { BenchmarkContextPanel } from './inspector/BenchmarkContextPanel';
import { ChevronDown, ChevronRight, Brain, Database, Zap, Code, Globe } from 'lucide-react';

interface AgentCognitiveInspectorProps {
  className?: string;
}

type InspectorTab =
  | 'overview'
  | 'memory'
  | 'cache'
  | 'llm'
  | 'tools'
  | 'benchmark';

export const AgentCognitiveInspector: React.FC<AgentCognitiveInspectorProps> = ({
  className = '',
}) => {
  const { selectedAgentId, agentStates } = useAgentStore();
  const { currentTime } = useTimelineStore();
  const [activeTab, setActiveTab] = useState<InspectorTab>('overview');
  const [expandedSections, setExpandedSections] = useState<Set<string>>(
    new Set(['overview', 'memory'])
  );

  const selectedAgent = useMemo(
    () => (selectedAgentId ? agentStates[selectedAgentId] : null),
    [selectedAgentId, agentStates, currentTime]
  );

  const toggleSection = (section: string) => {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      if (next.has(section)) {
        next.delete(section);
      } else {
        next.add(section);
      }
      return next;
    });
  };

  if (!selectedAgent) {
    return (
      <div
        className={`agent-cognitive-inspector ${className} bg-white dark:bg-gray-800 border-l border-gray-200 dark:border-gray-700`}
      >
        <div className="p-6 h-full flex items-center justify-center text-gray-500 dark:text-gray-400">
          <div className="text-center">
            <Brain className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p className="text-sm">Select an agent to inspect</p>
            <p className="text-xs mt-1">Click on any node in the graph</p>
          </div>
        </div>
      </div>
    );
  }

  const tabs = [
    { id: 'overview' as InspectorTab, label: 'Overview', icon: Brain },
    { id: 'memory' as InspectorTab, label: 'Memory', icon: Database },
    { id: 'cache' as InspectorTab, label: 'Cache', icon: Zap },
    { id: 'llm' as InspectorTab, label: 'LLM Calls', icon: Code },
    { id: 'tools' as InspectorTab, label: 'Tools', icon: Code },
    {
      id: 'benchmark' as InspectorTab,
      label: 'Benchmark',
      icon: Globe,
    },
  ];

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      className={`agent-cognitive-inspector ${className} bg-white dark:bg-gray-800 border-l border-gray-200 dark:border-gray-700 overflow-hidden flex flex-col h-full`}
    >
      {/* Header */}
      <div className="p-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              {selectedAgent.role}
            </h2>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
              ID: {selectedAgent.node_id.slice(0, 8)}...
            </p>
          </div>
          <div
            className={`px-3 py-1 rounded-full text-xs font-medium ${
              selectedAgent.status === 'running'
                ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
                : selectedAgent.status === 'completed'
                ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                : selectedAgent.status === 'thinking'
                ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'
                : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
            }`}
          >
            {selectedAgent.status}
          </div>
        </div>

        {/* Tabs */}
        <div className="flex space-x-1 overflow-x-auto">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-200'
                    : 'text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-700'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        <AnimatePresence mode="wait">
          {activeTab === 'overview' && (
            <OverviewPanel
              key="overview"
              agent={selectedAgent}
              expandedSections={expandedSections}
              toggleSection={toggleSection}
            />
          )}
          {activeTab === 'memory' && (
            <MemoryMonitor
              key="memory"
              agent={selectedAgent}
              currentTime={currentTime}
            />
          )}
          {activeTab === 'cache' && (
            <PromptCacheViewer
              key="cache"
              agent={selectedAgent}
              currentTime={currentTime}
            />
          )}
          {activeTab === 'llm' && (
            <LLMCallHistory
              key="llm"
              agent={selectedAgent}
              currentTime={currentTime}
            />
          )}
          {activeTab === 'tools' && (
            <ToolCallList
              key="tools"
              agent={selectedAgent}
              currentTime={currentTime}
            />
          )}
          {activeTab === 'benchmark' && (
            <BenchmarkContextPanel
              key="benchmark"
              agent={selectedAgent}
            />
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
};

/**
 * Overview Panel - 概览面板
 */
const OverviewPanel: React.FC<{
  agent: any;
  expandedSections: Set<string>;
  toggleSection: (section: string) => void;
}> = ({ agent, expandedSections, toggleSection }) => {
  const sections = [
    {
      id: 'basic',
      title: 'Basic Information',
      icon: Brain,
      content: <BasicInfoSection agent={agent} />,
    },
    {
      id: 'performance',
      title: 'Performance Metrics',
      icon: Zap,
      content: <PerformanceSection agent={agent} />,
    },
    {
      id: 'hierarchy',
      title: 'Hierarchy & Handoffs',
      icon: Database,
      content: <HierarchySection agent={agent} />,
    },
  ];

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="space-y-3"
    >
      {sections.map((section) => {
        const Icon = section.icon;
        const isExpanded = expandedSections.has(section.id);

        return (
          <div
            key={section.id}
            className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden"
          >
            <button
              onClick={() => toggleSection(section.id)}
              className="w-full px-3 py-2 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
            >
              <div className="flex items-center space-x-2">
                <Icon className="w-4 h-4 text-gray-600 dark:text-gray-400" />
                <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                  {section.title}
                </span>
              </div>
              {isExpanded ? (
                <ChevronDown className="w-4 h-4 text-gray-500" />
              ) : (
                <ChevronRight className="w-4 h-4 text-gray-500" />
              )}
            </button>

            <AnimatePresence>
              {isExpanded && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.2 }}
                  className="overflow-hidden"
                >
                  <div className="p-3 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/50">
                    {section.content}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        );
      })}
    </motion.div>
  );
};

const BasicInfoSection: React.FC<{ agent: any }> = ({ agent }) => {
  return (
    <div className="space-y-2 text-xs">
      <InfoRow label="Node ID" value={agent.node_id} />
      <InfoRow label="Node Type" value={agent.node_type} />
      <InfoRow label="Role" value={agent.role} />
      <InfoRow label="Depth" value={agent.depth.toString()} />
      <InfoRow
        label="Created At"
        value={new Date(agent.created_at).toLocaleString()}
      />
      {agent.started_at && (
        <InfoRow
          label="Started At"
          value={new Date(agent.started_at).toLocaleString()}
        />
      )}
      {agent.completed_at && (
        <InfoRow
          label="Completed At"
          value={new Date(agent.completed_at).toLocaleString()}
        />
      )}
    </div>
  );
};

const PerformanceSection: React.FC<{ agent: any }> = ({ agent }) => {
  return (
    <div className="space-y-3">
      <MetricCard
        label="Execution Time"
        value={`${(agent.total_execution_time_ms / 1000).toFixed(2)}s`}
        color="#3b82f6"
      />
      <MetricCard
        label="LLM Calls"
        value={agent.llm_call_count.toString()}
        color="#8b5cf6"
      />
      <MetricCard
        label="Tool Calls"
        value={agent.tool_call_count.toString()}
        color="#10b981"
      />
      <MetricCard
        label="Tokens Used"
        value={agent.total_tokens_used.toLocaleString()}
        color="#f59e0b"
      />
      <MetricCard
        label="Cost"
        value={`$${agent.total_cost_usd.toFixed(4)}`}
        color="#ef4444"
      />
    </div>
  );
};

const HierarchySection: React.FC<{ agent: any }> = ({ agent }) => {
  return (
    <div className="space-y-2 text-xs">
      {agent.parent_id && (
        <InfoRow label="Parent ID" value={agent.parent_id} />
      )}
      <div>
        <div className="font-medium text-gray-700 dark:text-gray-300 mb-1">
          Child Agents ({agent.child_ids.length})
        </div>
        {agent.child_ids.length > 0 ? (
          <div className="space-y-1">
            {agent.child_ids.map((childId: string) => (
              <div
                key={childId}
                className="pl-2 text-gray-600 dark:text-gray-400 text-xs"
              >
                • {childId.slice(0, 8)}...
              </div>
            ))}
          </div>
        ) : (
          <div className="text-gray-400 dark:text-gray-500 italic">
            No child agents
          </div>
        )}
      </div>
      {agent.handoffs && agent.handoffs.length > 0 && (
        <div>
          <div className="font-medium text-gray-700 dark:text-gray-300 mb-1">
            Handoffs ({agent.handoffs.length})
          </div>
          <div className="space-y-1">
            {agent.handoffs.map((handoff: any) => (
              <div
                key={handoff.handoff_id}
                className="pl-2 text-xs text-gray-600 dark:text-gray-400"
              >
                → {handoff.to_agent_role} ({handoff.to_agent_id.slice(0, 8)}
                ...)
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

const InfoRow: React.FC<{ label: string; value: string }> = ({
  label,
  value,
}) => {
  return (
    <div className="flex justify-between">
      <span className="text-gray-600 dark:text-gray-400">{label}:</span>
      <span className="text-gray-900 dark:text-gray-100 font-medium">
        {value}
      </span>
    </div>
  );
};

const MetricCard: React.FC<{
  label: string;
  value: string;
  color: string;
}> = ({ label, value, color }) => {
  return (
    <div
      className="p-3 rounded-lg bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700"
    >
      <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">
        {label}
      </div>
      <div
        className="text-xl font-bold"
        style={{ color }}
      >
        {value}
      </div>
    </div>
  );
};

export default AgentCognitiveInspector;
