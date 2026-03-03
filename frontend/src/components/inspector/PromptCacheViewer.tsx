/**
 * Prompt Cache Viewer - 增强版缓存可视化
 *
 * 复刻 Swarm-IDE 的差异对比风格
 * - VS Code 风格的差异对比颜色块
 * - Token 级别的精确命中显示
 * - 缓存性能统计
 */

import React, { useMemo } from 'react';
import { Database, Zap, TrendingUp, PieChart } from 'lucide-react';

interface PromptCacheViewerProps {
  agent: any;
  currentTime: number;
}

interface CacheSegment {
  type: 'hit' | 'miss' | 'partial';
  start: number;
  end: number;
  percentage: number;
  tokens: number;
}

export const PromptCacheViewer: React.FC<PromptCacheViewerProps> = ({ agent, currentTime }) => {
  // 获取 LLM 调用记录
  const llmCalls = (agent.events || []).filter(
    (e: any) =>
      e.event_type === 'llm_call_complete' &&
      new Date(e.timestamp).getTime() <= currentTime
  );

  // 计算缓存统计
  const cacheStats = useMemo(() => {
    const totalCalls = llmCalls.length;
    if (totalCalls === 0) {
      return { hitRate: 0, totalTokens: 0, cachedTokens: 0, savings: 0 };
    }

    let totalTokens = 0;
    let cachedTokens = 0;

    llmCalls.forEach((call: any) => {
      const trace = call.llm_call_trace;
      if (trace) {
        totalTokens += trace.total_tokens || 0;
        if (trace.prompt_caching) {
          cachedTokens += trace.prompt_caching.cache_hit_tokens || 0;
        }
      }
    });

    const hitRate = totalTokens > 0 ? (cachedTokens / totalTokens) * 100 : 0;
    // 假设缓存命中节省 90% 成本
    const savings = (cachedTokens * 0.00003).toFixed(4); // USD

    return {
      hitRate,
      totalTokens,
      cachedTokens,
      savings: parseFloat(savings),
    };
  }, [llmCalls]);

  // 生成缓存段可视化
  const generateCacheSegments = (call: any): CacheSegment[] => {
    const trace = call.llm_call_trace;
    if (!trace || !trace.prompt_caching) {
      return [];
    }

    const { cache_status, cache_hit_position, cache_hit_tokens, total_tokens } = trace.prompt_caching;

    if (cache_status === 'HIT') {
      return [{ type: 'hit', start: 0, end: total_tokens, percentage: 100, tokens: total_tokens }];
    }

    if (cache_status === 'MISS') {
      return [{ type: 'miss', start: 0, end: total_tokens, percentage: 100, tokens: total_tokens }];
    }

    if (cache_status === 'PARTIAL') {
      const hitPercentage = (cache_hit_tokens / total_tokens) * 100;
      return [
        { type: 'hit', start: 0, end: cache_hit_position, percentage: hitPercentage, tokens: cache_hit_tokens },
        { type: 'miss', start: cache_hit_position, end: total_tokens, percentage: 100 - hitPercentage, tokens: total_tokens - cache_hit_tokens },
      ];
    }

    return [];
  };

  if (llmCalls.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500 dark:text-gray-400 text-sm">
        <Database className="w-8 h-8 mx-auto mb-2 opacity-50" />
        <p>No LLM calls recorded</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* 总览统计卡片 */}
      <div className="grid grid-cols-2 gap-2">
        <div className="bg-gradient-to-br from-blue-50 to-blue-100 dark:from-blue-900/40 dark:to-blue-800/40 rounded-lg p-3 border border-blue-200 dark:border-blue-700">
          <div className="flex items-center space-x-2 mb-1">
            <PieChart className="w-4 h-4 text-blue-600 dark:text-blue-400" />
            <span className="text-xs font-semibold text-blue-900 dark:text-blue-100">
              Cache Hit Rate
            </span>
          </div>
          <div className={`text-2xl font-bold ${
            cacheStats.hitRate > 50 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
          }`}>
            {cacheStats.hitRate.toFixed(1)}%
          </div>
        </div>

        <div className="bg-gradient-to-br from-green-50 to-green-100 dark:from-green-900/40 dark:to-green-800/40 rounded-lg p-3 border border-green-200 dark:border-green-700">
          <div className="flex items-center space-x-2 mb-1">
            <Zap className="w-4 h-4 text-green-600 dark:text-green-400" />
            <span className="text-xs font-semibold text-green-900 dark:text-green-100">
              Cost Savings
            </span>
          </div>
          <div className="text-2xl font-bold text-green-600 dark:text-green-400">
            ${cacheStats.savings.toFixed(2)}
          </div>
        </div>
      </div>

      {/* 详细调用记录 */}
      <div className="space-y-3">
        <div className="text-xs font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide">
          LLM Call Breakdown
        </div>

        {llmCalls.slice(-5).map((event: any, index: number) => {
          const trace = event.llm_call_trace;
          if (!trace) return null;

          const segments = generateCacheSegments(event);
          const { cache_status } = trace.prompt_caching || { cache_status: 'MISS' };

          return (
            <div
              key={event.event_id}
              className="bg-white dark:bg-gray-900/50 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden"
            >
              {/* 调用头部 */}
              <div className="px-3 py-2 bg-gray-50 dark:bg-gray-800/50 border-b border-gray-200 dark:border-gray-700">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-gray-900 dark:text-gray-100">
                    Call #{llmCalls.length - llmCalls.slice(-5).length + index + 1}
                  </span>
                  <span className={`text-xs px-2 py-0.5 rounded font-semibold ${
                    cache_status === 'HIT'
                      ? 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300'
                      : cache_status === 'PARTIAL'
                      ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300'
                      : 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300'
                  }`}>
                    {cache_status}
                  </span>
                </div>
              </div>

              {/* Token 级别缓存可视化 */}
              <div className="p-3">
                <div className="text-xs text-gray-600 dark:text-gray-400 mb-2">
                  Token-level Cache Visualization
                </div>

                {/* 进度条 */}
                <div className="relative h-6 rounded overflow-hidden bg-gray-200 dark:bg-gray-700 mb-2">
                  <div className="flex h-full">
                    {segments.map((seg, i) => (
                      <div
                        key={i}
                        className={`
                          transition-all duration-300
                          ${seg.type === 'hit' ? 'bg-green-500' : 'bg-red-400'}
                        `}
                        style={{ width: `${seg.percentage}%` }}
                        title={`${seg.tokens} tokens (${seg.percentage.toFixed(1)}%)`}
                      />
                    ))}
                  </div>

                  {/* 刻度标记 */}
                  <div className="absolute inset-0 flex items-center justify-center">
                    <span className="text-xs font-bold text-white drop-shadow-md">
                      {trace.total_tokens?.toLocaleString()} tokens
                    </span>
                  </div>
                </div>

                {/* 详细统计 */}
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="flex justify-between">
                    <span className="text-gray-600 dark:text-gray-400">Cached:</span>
                    <span className="font-mono font-semibold text-green-600 dark:text-green-400">
                      {segments.filter(s => s.type === 'hit').reduce((sum, s) => sum + s.tokens, 0).toLocaleString()}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600 dark:text-gray-400">New:</span>
                    <span className="font-mono font-semibold text-red-600 dark:text-red-400">
                      {segments.filter(s => s.type === 'miss').reduce((sum, s) => sum + s.tokens, 0).toLocaleString()}
                    </span>
                  </div>
                </div>

                {/* VS Code 风格的差异预览 */}
                {segments.length > 0 && (
                  <div className="mt-3 p-2 bg-gray-50 dark:bg-gray-900 rounded border border-gray-200 dark:border-gray-700">
                    <div className="text-xs text-gray-600 dark:text-gray-400 mb-1">
                      Token Breakdown
                    </div>
                    <div className="space-y-1">
                      {segments.map((seg, i) => (
                        <div
                          key={i}
                          className={`p-2 rounded text-xs font-mono ${
                            seg.type === 'hit'
                              ? 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-200'
                              : 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-200'
                          }`}
                        >
                          <div className="flex justify-between">
                            <span>{seg.type === 'hit' ? '✓' : '✗'} {seg.type.toUpperCase()}</span>
                            <span>{seg.tokens} tokens ({seg.percentage.toFixed(1)}%)</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Latency */}
              {trace.latency_ms && (
                <div className="px-3 py-2 border-t border-gray-200 dark:border-gray-700">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-gray-600 dark:text-gray-400">Latency:</span>
                    <span className="font-mono font-semibold text-gray-900 dark:text-gray-100">
                      {trace.latency_ms.toFixed(0)} ms
                    </span>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* 性能提示 */}
      {cacheStats.hitRate < 50 && (
        <div className="mt-4 p-3 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg border border-yellow-200 dark:border-yellow-800">
          <div className="flex items-start space-x-2">
            <TrendingUp className="w-4 h-4 text-yellow-600 dark:text-yellow-400 mt-0.5" />
            <div className="text-xs text-yellow-800 dark:text-yellow-200">
              <strong>Optimization Tip:</strong> Cache hit rate is below 50%. Consider consolidating similar prompts to improve cache utilization.
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
