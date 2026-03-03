/**
 * Benchmark Context Panel - 基准测试环境上下文
 *
 * 显示 Agent 所处的基准测试环境信息
 * - 环境类型（ALFWorld, StuLife, WebShop）
 * - 任务目标
 * - 可用工具
 * - 环境状态
 */

import React from 'react';
import { Globe, Target, Wrench, Activity } from 'lucide-react';

interface BenchmarkContextPanelProps {
  agent: any;
  currentTime: number;
}

export const BenchmarkContextPanel: React.FC<BenchmarkContextPanelProps> = ({ agent, currentTime }) => {
  // Get benchmark context from agent metadata
  const benchmarkContext = agent?.metadata?.benchmark_context || {};
  const environmentType = benchmarkContext.environment_type || 'Unknown';
  const taskGoal = benchmarkContext.task_goal || 'No task defined';
  const availableTools = benchmarkContext.available_tools || [];
  const environmentState = benchmarkContext.environment_state || {};

  if (Object.keys(benchmarkContext).length === 0) {
    return (
      <div className="text-center py-8 text-gray-500 dark:text-gray-400 text-sm">
        <Globe className="w-8 h-8 mx-auto mb-2 opacity-50" />
        <p>No benchmark context available</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Environment Type */}
      <div className="p-3 bg-gray-50 dark:bg-gray-900/50 rounded-lg border border-gray-200 dark:border-gray-700">
        <div className="flex items-center space-x-2 mb-2">
          <Globe className="w-4 h-4 text-blue-600 dark:text-blue-400" />
          <h4 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
            Environment
          </h4>
        </div>
        <div className="text-xs text-gray-700 dark:text-gray-300 font-mono bg-gray-100 dark:bg-gray-800 px-2 py-1 rounded">
          {environmentType}
        </div>
      </div>

      {/* Task Goal */}
      <div className="p-3 bg-gray-50 dark:bg-gray-900/50 rounded-lg border border-gray-200 dark:border-gray-700">
        <div className="flex items-center space-x-2 mb-2">
          <Target className="w-4 h-4 text-green-600 dark:text-green-400" />
          <h4 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
            Task Goal
          </h4>
        </div>
        <p className="text-xs text-gray-700 dark:text-gray-300 leading-relaxed">
          {taskGoal}
        </p>
      </div>

      {/* Available Tools */}
      {availableTools.length > 0 && (
        <div className="p-3 bg-gray-50 dark:bg-gray-900/50 rounded-lg border border-gray-200 dark:border-gray-700">
          <div className="flex items-center space-x-2 mb-2">
            <Wrench className="w-4 h-4 text-orange-600 dark:text-orange-400" />
            <h4 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
              Available Tools ({availableTools.length})
            </h4>
          </div>
          <div className="flex flex-wrap gap-1">
            {availableTools.map((tool: string, index: number) => (
              <span
                key={index}
                className="text-xs font-mono bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-200 px-2 py-1 rounded"
              >
                {tool}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Environment State */}
      {Object.keys(environmentState).length > 0 && (
        <div className="p-3 bg-gray-50 dark:bg-gray-900/50 rounded-lg border border-gray-200 dark:border-gray-700">
          <div className="flex items-center space-x-2 mb-2">
            <Activity className="w-4 h-4 text-purple-600 dark:text-purple-400" />
            <h4 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
              Environment State
            </h4>
          </div>
          <div className="space-y-1 text-xs">
            {Object.entries(environmentState).map(([key, value]) => (
              <div key={key} className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">{key}:</span>
                <span className="font-mono text-gray-900 dark:text-gray-100">
                  {String(value)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
