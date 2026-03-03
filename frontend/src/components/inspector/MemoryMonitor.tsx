/**
 * Memory Monitor - 实时局部记忆查看器
 *
 * 显示 Agent 在当前时刻的动态记忆快照
 * - Short-term Memory: 短期记忆（最近思考）
 * - Long-term Memory: 长期记忆（持久知识）
 * - Working Memory: 工作记忆（当前任务上下文）
 */

import React, { useState, useMemo } from 'react';
import { motion } from 'framer-motion';
import { Brain, Database, HardDrive, TrendingUp, Clock } from 'lucide-react';
import { useTimelineStore } from '../../store/timelineStore';

interface MemoryMonitorProps {
  agent: any;
  currentTime: number;
}

export const MemoryMonitor: React.FC<MemoryMonitorProps> = ({
  agent,
  currentTime,
}) => {
  const [selectedMemory, setSelectedMemory] = useState<string | null>(null);

  // 获取当前时刻的记忆快照
  const memorySnapshot = useMemo(() => {
    if (!agent.dynamic_memory) return null;

    const snapshotTime = new Date(agent.dynamic_memory.timestamp).getTime();
    const isCurrent = Math.abs(snapshotTime - currentTime) < 5000; // 5秒内

    return {
      ...agent.dynamic_memory,
      isCurrent,
    };
  }, [agent.dynamic_memory, currentTime]);

  if (!memorySnapshot) {
    return (
      <div className="text-center py-12 text-gray-500 dark:text-gray-400">
        <Database className="w-12 h-12 mx-auto mb-3 opacity-50" />
        <p className="text-sm">No memory snapshot available</p>
      </div>
    );
  }

  const { short_term_memory, long_term_memory, working_memory, isCurrent } =
    memorySnapshot;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="space-y-4"
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Brain className="w-5 h-5 text-purple-600 dark:text-purple-400" />
          <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
            Memory Snapshot
          </h3>
        </div>
        {isCurrent && (
          <div className="flex items-center space-x-1 text-xs text-green-600 dark:text-green-400">
            <Clock className="w-3 h-3" />
            <span>Current</span>
          </div>
        )}
      </div>

      {/* Memory Statistics */}
      <MemoryStats memorySnapshot={memorySnapshot} />

      {/* Short-term Memory */}
      <MemorySection
        title="Short-term Memory"
        icon={TrendingUp}
        color="blue"
        items={short_term_memory}
        itemCount={short_term_memory.length}
        description="Recent thoughts and observations"
      />

      {/* Working Memory */}
      <WorkingMemorySection
        workingMemory={working_memory}
        description="Current task context and variables"
      />

      {/* Long-term Memory */}
      <MemorySection
        title="Long-term Memory"
        icon={HardDrive}
        color="purple"
        items={long_term_memory}
        itemCount={long_term_memory.length}
        description="Persistent knowledge and facts"
        isList
      />
    </motion.div>
  );
};

/**
 * Memory Statistics
 */
const MemoryStats: React.FC<{ memorySnapshot: any }> = ({ memorySnapshot }) => {
  const stats = [
    {
      label: 'Total Memories',
      value: memorySnapshot.total_memories,
      icon: Database,
      color: 'text-blue-600 dark:text-blue-400',
    },
    {
      label: 'Memory Size',
      value: `${(memorySnapshot.memory_size_bytes / 1024).toFixed(1)} KB`,
      icon: HardDrive,
      color: 'text-purple-600 dark:text-purple-400',
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-2">
      {stats.map((stat) => {
        const Icon = stat.icon;
        return (
          <div
            key={stat.label}
            className="p-3 bg-gray-50 dark:bg-gray-900/50 rounded-lg border border-gray-200 dark:border-gray-700"
          >
            <div className="flex items-center space-x-2 mb-1">
              <Icon className={`w-4 h-4 ${stat.color}`} />
              <span className="text-xs text-gray-600 dark:text-gray-400">
                {stat.label}
              </span>
            </div>
            <div className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              {stat.value}
            </div>
          </div>
        );
      })}
    </div>
  );
};

/**
 * Memory Section Component
 */
interface MemorySectionProps {
  title: string;
  icon: any;
  color: string;
  items: any[];
  itemCount: number;
  description: string;
  isList?: boolean;
}

const MemorySection: React.FC<MemorySectionProps> = ({
  title,
  icon: Icon,
  color,
  items,
  itemCount,
  description,
  isList = false,
}) => {
  const [isExpanded, setIsExpanded] = useState(true);

  const colorClasses = {
    blue: {
      bg: 'bg-blue-50 dark:bg-blue-900/20',
      border: 'border-blue-200 dark:border-blue-800',
      icon: 'text-blue-600 dark:text-blue-400',
    },
    purple: {
      bg: 'bg-purple-50 dark:bg-purple-900/20',
      border: 'border-purple-200 dark:border-purple-800',
      icon: 'text-purple-600 dark:text-purple-400',
    },
  }[color];

  return (
    <div
      className={`border ${colorClasses.border} rounded-lg overflow-hidden`}
    >
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className={`w-full px-3 py-2 ${colorClasses.bg} flex items-center justify-between hover:opacity-80 transition-opacity`}
      >
        <div className="flex items-center space-x-2">
          <Icon className={`w-4 h-4 ${colorClasses.icon}`} />
          <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">
            {title}
          </span>
          <span className="text-xs text-gray-500 dark:text-gray-400">
            ({itemCount})
          </span>
        </div>
        <div className="text-xs text-gray-500 dark:text-gray-400">
          {isExpanded ? '▼' : '▶'}
        </div>
      </button>

      {/* Description */}
      <div className="px-3 py-1 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
        <p className="text-xs text-gray-500 dark:text-gray-400 italic">
          {description}
        </p>
      </div>

      {/* Content */}
      {isExpanded && (
        <div className="p-3 bg-white dark:bg-gray-800 max-h-64 overflow-y-auto">
          {items.length > 0 ? (
            <div className="space-y-2">
              {items.map((item, index) => (
                <MemoryItem
                  key={index}
                  item={item}
                  index={index}
                  isList={isList}
                />
              ))}
            </div>
          ) : (
            <div className="text-center py-4 text-xs text-gray-400 dark:text-gray-500 italic">
              No items in memory
            </div>
          )}
        </div>
      )}
    </div>
  );
};

/**
 * Memory Item Component
 */
interface MemoryItemProps {
  item: any;
  index: number;
  isList?: boolean;
}

const MemoryItem: React.FC<MemoryItemProps> = ({ item, index, isList }) => {
  // Handle both string items and object items
  const content = typeof item === 'string' ? item : JSON.stringify(item, null, 2);
  const hasImportance = typeof item === 'object' && item.importance !== undefined;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
      className="group relative"
    >
      <div className="text-xs p-2 bg-gray-50 dark:bg-gray-900/50 rounded border border-gray-200 dark:border-gray-700">
        {/* Index */}
        <div className="absolute -left-1 -top-1 w-5 h-5 bg-blue-500 text-white rounded-full flex items-center justify-center text-[10px] font-bold opacity-0 group-hover:opacity-100 transition-opacity">
          {index + 1}
        </div>

        {/* Content */}
        <div className="text-gray-800 dark:text-gray-200 whitespace-pre-wrap break-words font-mono">
          {content}
        </div>

        {/* Importance Score (if available) */}
        {hasImportance && (
          <div className="mt-2 flex items-center space-x-2">
            <span className="text-xs text-gray-500">Importance:</span>
            <div className="flex-1 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-500 rounded-full"
                style={{ width: `${item.importance * 100}%` }}
              />
            </div>
            <span className="text-xs font-mono text-gray-600 dark:text-gray-400">
              {item.importance.toFixed(2)}
            </span>
          </div>
        )}
      </div>
    </motion.div>
  );
};

/**
 * Working Memory Section (specialized for key-value pairs)
 */
interface WorkingMemorySectionProps {
  workingMemory: Record<string, any>;
  description: string;
}

const WorkingMemorySection: React.FC<WorkingMemorySectionProps> = ({
  workingMemory,
  description,
}) => {
  const [isExpanded, setIsExpanded] = useState(true);
  const entries = Object.entries(workingMemory || {});

  return (
    <div className="border border-green-200 dark:border-green-800 rounded-lg overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-3 py-2 bg-green-50 dark:bg-green-900/20 flex items-center justify-between hover:opacity-80 transition-opacity"
      >
        <div className="flex items-center space-x-2">
          <HardDrive className="w-4 h-4 text-green-600 dark:text-green-400" />
          <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">
            Working Memory
          </span>
          <span className="text-xs text-gray-500 dark:text-gray-400">
            ({entries.length})
          </span>
        </div>
        <div className="text-xs text-gray-500 dark:text-gray-400">
          {isExpanded ? '▼' : '▶'}
        </div>
      </button>

      {/* Description */}
      <div className="px-3 py-1 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
        <p className="text-xs text-gray-500 dark:text-gray-400 italic">
          {description}
        </p>
      </div>

      {/* Content */}
      {isExpanded && (
        <div className="p-3 bg-white dark:bg-gray-800 max-h-64 overflow-y-auto">
          {entries.length > 0 ? (
            <div className="space-y-2">
              {entries.map(([key, value], index) => (
                <motion.div
                  key={key}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: index * 0.05 }}
                  className="flex items-start space-x-2 p-2 bg-gray-50 dark:bg-gray-900/50 rounded border border-gray-200 dark:border-gray-700"
                >
                  <div className="flex-shrink-0 w-24 text-xs font-semibold text-green-600 dark:text-green-400 break-words">
                    {key}:
                  </div>
                  <div className="flex-1 text-xs text-gray-800 dark:text-gray-200 font-mono break-words">
                    {typeof value === 'object'
                      ? JSON.stringify(value, null, 2)
                      : String(value)}
                  </div>
                </motion.div>
              ))}
            </div>
          ) : (
            <div className="text-center py-4 text-xs text-gray-400 dark:text-gray-500 italic">
              Working memory is empty
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default MemoryMonitor;
