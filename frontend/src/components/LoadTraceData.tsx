/**
 * Load Trace Data Modal
 *
 * 用于加载追踪数据的模态对话框
 */

import React, { useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Upload, FileText, X } from 'lucide-react';

interface LoadTraceDataProps {
  onLoad: (data: any) => void;
}

export const LoadTraceData: React.FC<LoadTraceDataProps> = ({ onLoad }) => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsLoading(true);
    setError(null);

    try {
      const text = await file.text();
      const data = JSON.parse(text);

      // Save to localStorage
      localStorage.setItem('lastTraceData', JSON.stringify(data));

      onLoad(data);
    } catch (err: any) {
      setError(err.message || 'Failed to parse file');
    } finally {
      setIsLoading(false);
    }
  };

  const handleUseSampleData = () => {
    // Load enhanced sample trace data with new fields
    const sampleData = {
      trace_id: 'sample-trace-123',
      task_name: 'Enhanced ALFWorld Task Demo',
      started_at: new Date(Date.now() - 15000).toISOString(),
      completed_at: new Date().toISOString(),
      all_nodes: {
        'node-1': {
          node_id: 'node-1',
          node_type: 'worker',
          role: 'ALFWorldWorker',
          status: 'completed',
          system_prompt: 'You are an ALFWorld agent...',
          user_messages: [{ role: 'user', content: 'Go to countertop and find the apple' }],
          tools: ['navigate', 'search', 'pickup'],
          created_at: new Date(Date.now() - 15000).toISOString(),
          started_at: new Date(Date.now() - 14500).toISOString(),
          completed_at: new Date().toISOString(),
          parent_id: null,
          child_ids: ['node-2', 'node-3'],
          depth: 0,
          total_execution_time_ms: 14500,
          llm_call_count: 8,
          tool_call_count: 5,
          total_tokens_used: 3247,
          total_cost_usd: 0.08,
          // Enhanced fields for new UI
          llm_latency_ms: 1243,
          cache_hit_rate: 73.5,
          handoffs: [],
          events: [
            {
              event_id: 'event-1',
              event_type: 'llm_call_complete',
              timestamp: new Date(Date.now() - 14000).toISOString(),
              llm_call_trace: {
                model: 'gpt-4',
                total_tokens: 1247,
                latency_ms: 1243,
                prompt_caching: {
                  cache_status: 'PARTIAL',
                  cache_hit_position: 856,
                  cache_hit_tokens: 856,
                  total_tokens: 1247,
                  cache_hit_percentage: 68.6
                }
              }
            },
            {
              event_id: 'event-2',
              event_type: 'llm_call_complete',
              timestamp: new Date(Date.now() - 12000).toISOString(),
              llm_call_trace: {
                model: 'gpt-4',
                total_tokens: 892,
                latency_ms: 876,
                prompt_caching: {
                  cache_status: 'HIT',
                  cache_hit_position: 0,
                  cache_hit_tokens: 892,
                  total_tokens: 892,
                  cache_hit_percentage: 100.0
                }
              }
            },
            {
              event_id: 'event-3',
              event_type: 'llm_call_complete',
              timestamp: new Date(Date.now() - 10000).toISOString(),
              llm_call_trace: {
                model: 'gpt-4',
                total_tokens: 1108,
                latency_ms: 1034,
                prompt_caching: {
                  cache_status: 'MISS',
                  cache_hit_position: 0,
                  cache_hit_tokens: 0,
                  total_tokens: 1108,
                  cache_hit_percentage: 0.0
                }
              }
            }
          ],
          metadata: {
            benchmark_context: {
              environment_type: 'ALFWorld',
              task_goal: 'Navigate to countertop and find the apple',
              available_tools: ['navigate', 'search', 'pickup', 'open', 'put'],
              environment_state: {
                location: 'kitchen',
                inventory: [],
                visible_objects: ['apple', 'knife', 'counter']
              }
            }
          }
        },
        'node-2': {
          node_id: 'node-2',
          node_type: 'worker',
          role: 'NavigationWorker',
          status: 'running',
          system_prompt: 'You handle navigation tasks...',
          user_messages: [],
          tools: ['navigate', 'look'],
          created_at: new Date(Date.now() - 10000).toISOString(),
          started_at: new Date(Date.now() - 9500).toISOString(),
          parent_id: 'node-1',
          child_ids: [],
          depth: 1,
          total_execution_time_ms: 9500,
          llm_call_count: 3,
          tool_call_count: 4,
          total_tokens_used: 1567,
          total_cost_usd: 0.04,
          llm_latency_ms: 892,
          cache_hit_rate: 45.2,
          handoffs: [],
          events: [],
          metadata: {}
        },
        'node-3': {
          node_id: 'node-3',
          node_type: 'worker',
          role: 'SearchWorker',
          status: 'thinking',
          system_prompt: 'You handle search operations...',
          user_messages: [],
          tools: ['search', 'examine'],
          created_at: new Date(Date.now() - 8000).toISOString(),
          started_at: new Date(Date.now() - 7500).toISOString(),
          parent_id: 'node-1',
          child_ids: [],
          depth: 1,
          total_execution_time_ms: 7500,
          llm_call_count: 2,
          tool_call_count: 1,
          total_tokens_used: 432,
          total_cost_usd: 0.01,
          llm_latency_ms: 567,
          cache_hit_rate: 91.3,
          handoffs: [],
          events: [],
          metadata: {}
        }
      },
      events: [],
      handoffs: []
    };

    localStorage.setItem('lastTraceData', JSON.stringify(sampleData));
    onLoad(sampleData);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl p-8 max-w-md w-full mx-4"
      >
        {/* Header */}
        <div className="text-center mb-6">
          <div className="w-16 h-16 bg-blue-100 dark:bg-blue-900/30 rounded-full flex items-center justify-center mx-auto mb-4">
            <FileText className="w-8 h-8 text-blue-600 dark:text-blue-400" />
          </div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-2">
            Load Agent Trace
          </h2>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Upload a trace JSON file or use sample data to visualize agent execution
          </p>
        </div>

        {/* Error */}
        <AnimatePresence>
          {error && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-800 dark:text-red-200"
            >
              {error}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Upload Button */}
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={isLoading}
          className="w-full p-4 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg hover:border-blue-400 dark:hover:border-blue-500 transition-colors mb-4 group"
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".json"
            onChange={handleFileUpload}
            className="hidden"
          />
          <div className="flex flex-col items-center">
            <Upload className="w-8 h-8 text-gray-400 group-hover:text-blue-500 transition-colors mb-2" />
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
              {isLoading ? 'Loading...' : 'Click to upload trace file'}
            </span>
            <span className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              trace_*.json files
            </span>
          </div>
        </button>

        {/* Divider */}
        <div className="flex items-center my-4">
          <div className="flex-1 border-t border-gray-300 dark:border-gray-600" />
          <span className="px-4 text-xs text-gray-500 dark:text-gray-400">OR</span>
          <div className="flex-1 border-t border-gray-300 dark:border-gray-600" />
        </div>

        {/* Sample Data Button */}
        <button
          onClick={handleUseSampleData}
          className="w-full p-3 bg-blue-500 hover:bg-blue-600 text-white rounded-lg font-medium transition-colors"
        >
          Load Sample Data
        </button>

        {/* Instructions */}
        <div className="mt-6 p-4 bg-gray-50 dark:bg-gray-900/50 rounded-lg">
          <h3 className="text-xs font-semibold text-gray-700 dark:text-gray-300 mb-2">
            ✨ New Features Demo
          </h3>
          <ul className="text-xs text-gray-600 dark:text-gray-400 space-y-1">
            <li>• High-density Agent cards with metrics</li>
            <li>• Glassmorphism design & animations</li>
            <li>• Token-level cache visualization</li>
            <li>• Flowing handoff animations</li>
          </ul>
        </div>
      </motion.div>
    </div>
  );
};
