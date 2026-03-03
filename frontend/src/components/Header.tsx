/**
 * Header Component - 顶部栏
 */

import React from 'react';
import { Activity, FileText } from 'lucide-react';

interface HeaderProps {
  traceData: any;
}

export const Header: React.FC<HeaderProps> = ({ traceData }) => {
  return (
    <div className="h-14 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-6 flex items-center justify-between">
      <div className="flex items-center space-x-3">
        <Activity className="w-5 h-5 text-blue-600 dark:text-blue-400" />
        <h1 className="text-lg font-bold text-gray-900 dark:text-gray-100">
          Agent Visualization
        </h1>
      </div>

      {traceData && (
        <div className="flex items-center space-x-4 text-sm text-gray-600 dark:text-gray-400">
          <div className="flex items-center space-x-1">
            <FileText className="w-4 h-4" />
            <span>Task:</span>
            <span className="font-medium text-gray-900 dark:text-gray-100">
              {traceData.task_name}
            </span>
          </div>
        </div>
      )}
    </div>
  );
};
