/**
 * Tool Call List - 工具调用列表
 */

import React from 'react';
import { Wrench } from 'lucide-react';

interface ToolCallListProps {
  agent: any;
  currentTime: number;
}

export const ToolCallList: React.FC<ToolCallListProps> = ({ agent, currentTime }) => {
  const toolCalls = (agent.events || []).filter(
    (e: any) =>
      e.event_type === 'tool_call_complete' &&
      new Date(e.timestamp).getTime() <= currentTime
  );

  if (toolCalls.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500 dark:text-gray-400 text-sm">
        <Wrench className="w-8 h-8 mx-auto mb-2 opacity-50" />
        <p>No tool calls recorded</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {toolCalls.map((event: any, index: number) => (
        <div
          key={event.event_id}
          className="p-3 bg-gray-50 dark:bg-gray-900/50 rounded-lg border border-gray-200 dark:border-gray-700"
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-gray-900 dark:text-gray-100">
              #{index + 1}
            </span>
            <span className="text-xs text-gray-500">
              {new Date(event.timestamp).toLocaleTimeString()}
            </span>
          </div>

          {event.tool_call_record && (
            <div className="space-y-1 text-xs">
              <div>
                <span className="text-gray-600 dark:text-gray-400">Tool:</span>
                <span className="font-mono text-gray-900 dark:text-gray-100 ml-2">
                  {event.tool_call_record.tool_name}
                </span>
              </div>
              <div>
                <span className="text-gray-600 dark:text-gray-400">Arguments:</span>
                <pre className="mt-1 p-2 bg-gray-100 dark:bg-gray-800 rounded text-gray-800 dark:text-gray-200 overflow-x-auto">
                  {JSON.stringify(event.tool_call_record.arguments, null, 2)}
                </pre>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">Status:</span>
                <span className={
                  event.tool_call_record.status === 'success'
                    ? 'text-green-600'
                    : 'text-red-600'
                }>
                  {event.tool_call_record.status}
                </span>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
};
