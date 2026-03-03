/**
 * LLM Call History - LLM 调用历史
 */

import React from 'react';
import { Cpu, Clock, Hash } from 'lucide-react';

interface LLMCallHistoryProps {
  agent: any;
  currentTime: number;
}

export const LLMCallHistory: React.FC<LLMCallHistoryProps> = ({ agent, currentTime }) => {
  const llmCalls = (agent.events || []).filter(
    (e: any) =>
      e.event_type === 'llm_call_complete' &&
      new Date(e.timestamp).getTime() <= currentTime
  );

  if (llmCalls.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500 dark:text-gray-400 text-sm">
        <Cpu className="w-8 h-8 mx-auto mb-2 opacity-50" />
        <p>No LLM calls recorded</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {llmCalls.map((event: any, index: number) => (
        <div
          key={event.event_id}
          className="p-3 bg-gray-50 dark:bg-gray-900/50 rounded-lg border border-gray-200 dark:border-gray-700"
        >
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center space-x-2 text-xs">
              <Hash className="w-3 h-3 text-gray-500" />
              <span className="font-semibold text-gray-900 dark:text-gray-100">
                Call #{index + 1}
              </span>
            </div>
            <span className="text-xs text-gray-500">
              {new Date(event.timestamp).toLocaleTimeString()}
            </span>
          </div>

          {event.llm_call_trace && (
            <div className="space-y-2 text-xs">
              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">Model:</span>
                <span className="font-mono text-gray-900 dark:text-gray-100">
                  {event.llm_call_trace.model}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">Tokens:</span>
                <span className="font-mono text-gray-900 dark:text-gray-100">
                  {event.llm_call_trace.total_tokens}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">Latency:</span>
                <span className="font-mono text-gray-900 dark:text-gray-100">
                  {event.llm_call_trace.latency_ms.toFixed(2)} ms
                </span>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
};
