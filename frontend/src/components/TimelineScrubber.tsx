/**
 * Timeline Scrubber - 时间轴回溯器
 *
 * 允许拖动时间轴，回溯整个 Swarm 在过去任何一个时刻的完整状态快照
 * - 实现严格的因果分析
 * - 显示当时的 Memory 和 Cache 命中情况
 * - 播放/暂停/速度控制
 * - 关键事件标记
 */

import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Play,
  Pause,
  SkipBack,
  SkipForward,
  Clock,
  FastForward,
  Rewind,
  Bookmark,
} from 'lucide-react';
import { useTimelineStore } from '../store/timelineStore';
import { formatDuration } from '../utils/timeFormat';

interface TimelineScrubberProps {
  className?: string;
  onTimeChange?: (time: number) => void;
}

export const TimelineScrubber: React.FC<TimelineScrubberProps> = ({
  className = '',
  onTimeChange,
}) => {
  const scrubberRef = useRef<HTMLDivElement>(null);
  const [isDragging, setIsDragging] = useState(false);

  const {
    currentTime,
    minTime,
    maxTime,
    isPlaying,
    playbackSpeed,
    setCurrentTime,
    togglePlay,
    setPlaybackSpeed,
    jumpToStart,
    jumpToEnd,
    jumpBackward,
    jumpForward,
    keyframes,
  } = useTimelineStore();

  // Calculate progress percentage
  const progress = useMemo(() => {
    if (maxTime === minTime) return 0;
    return ((currentTime - minTime) / (maxTime - minTime)) * 100;
  }, [currentTime, minTime, maxTime]);

  // Handle time scrubbing
  const handleScrub = useCallback(
    (clientX: number) => {
      if (!scrubberRef.current) return;

      const rect = scrubberRef.current.getBoundingClientRect();
      const x = clientX - rect.left;
      const percentage = Math.max(0, Math.min(1, x / rect.width));
      const newTime = minTime + percentage * (maxTime - minTime);

      setCurrentTime(newTime);
      onTimeChange?.(newTime);
    },
    [minTime, maxTime, setCurrentTime, onTimeChange]
  );

  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    handleScrub(e.clientX);
  };

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (isDragging) {
        handleScrub(e.clientX);
      }
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    }

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, handleScrub]);

  // Auto-play
  useEffect(() => {
    if (!isPlaying) return;

    const interval = setInterval(() => {
      setCurrentTime((prev) => {
        const next = prev + 100 * playbackSpeed;
        if (next >= maxTime) {
          togglePlay();
          return maxTime;
        }
        return next;
      });
    }, 100);

    return () => clearInterval(interval);
  }, [isPlaying, playbackSpeed, maxTime, setCurrentTime, togglePlay]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement) return;

      switch (e.key) {
        case ' ':
          e.preventDefault();
          togglePlay();
          break;
        case 'ArrowLeft':
          e.preventDefault();
          jumpBackward();
          break;
        case 'ArrowRight':
          e.preventDefault();
          jumpForward();
          break;
        case 'Home':
          e.preventDefault();
          jumpToStart();
          break;
        case 'End':
          e.preventDefault();
          jumpToEnd();
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [togglePlay, jumpBackward, jumpForward, jumpToStart, jumpToEnd]);

  const speedOptions = [0.25, 0.5, 1, 2, 4];

  return (
    <div className={`timeline-scrubber ${className}`}>
      {/* Main Controls */}
      <div className="flex items-center space-x-3 mb-3">
        {/* Play/Pause */}
        <div className="flex items-center space-x-1">
          <ControlButton
            icon={SkipBack}
            onClick={jumpToStart}
            tooltip="Jump to start (Home)"
          />
          <ControlButton
            icon={Rewind}
            onClick={jumpBackward}
            tooltip="Step backward (←)"
          />
          <ControlButton
            icon={isPlaying ? Pause : Play}
            onClick={togglePlay}
            primary
            tooltip={isPlaying ? 'Pause (Space)' : 'Play (Space)'}
          />
          <ControlButton
            icon={FastForward}
            onClick={jumpForward}
            tooltip="Step forward (→)"
          />
          <ControlButton
            icon={SkipForward}
            onClick={jumpToEnd}
            tooltip="Jump to end (End)"
          />
        </div>

        {/* Speed Control */}
        <div className="flex items-center space-x-2">
          <span className="text-xs text-gray-500 dark:text-gray-400">
            Speed:
          </span>
          <div className="flex space-x-1">
            {speedOptions.map((speed) => (
              <button
                key={speed}
                onClick={() => setPlaybackSpeed(speed)}
                className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
                  playbackSpeed === speed
                    ? 'bg-blue-500 text-white'
                    : 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
                }`}
              >
                {speed}x
              </button>
            ))}
          </div>
        </div>

        {/* Time Display */}
        <div className="flex items-center space-x-3 ml-auto">
          <div className="text-sm font-mono text-gray-700 dark:text-gray-300">
            <Clock className="w-3 h-3 inline mr-1" />
            {formatDuration(currentTime)}
          </div>
          <div className="text-xs text-gray-500 dark:text-gray-400">
            / {formatDuration(maxTime)}
          </div>
        </div>
      </div>

      {/* Scrubber Bar */}
      <div
        ref={scrubberRef}
        className="relative h-8 bg-gray-100 dark:bg-gray-800 rounded-lg cursor-crosshair border border-gray-200 dark:border-gray-700 select-none"
        onMouseDown={handleMouseDown}
      >
        {/* Background Track */}
        <div className="absolute inset-0 bg-gray-100 dark:bg-gray-800 rounded-lg overflow-hidden">
          {/* Keyframe Markers */}
          <div className="absolute inset-0 flex">
            {keyframes.map((keyframe) => {
              const position =
                ((keyframe.time - minTime) / (maxTime - minTime)) * 100;
              return (
                <div
                  key={keyframe.id}
                  className="absolute top-0 bottom-0 w-0.5 bg-gray-300 dark:bg-gray-600 hover:bg-blue-400 transition-colors cursor-pointer"
                  style={{ left: `${position}%` }}
                  title={keyframe.label}
                  onClick={(e) => {
                    e.stopPropagation();
                    setCurrentTime(keyframe.time);
                    onTimeChange?.(keyframe.time);
                  }}
                >
                  {/* Keyframe Label */}
                  <div className="absolute -top-6 left-1/2 transform -translate-x-1/2 whitespace-nowrap">
                    <span className="text-[10px] text-gray-600 dark:text-gray-400 bg-white dark:bg-gray-800 px-1 rounded shadow">
                      {keyframe.label}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Progress Fill */}
          <motion.div
            className="absolute top-0 bottom-0 bg-gradient-to-r from-blue-400 to-blue-600 dark:from-blue-600 dark:to-blue-400 opacity-50"
            style={{ width: `${progress}%` }}
            animate={isPlaying ? { opacity: [0.5, 0.7, 0.5] } : {}}
            transition={{ duration: 1, repeat: Infinity }}
          />
        </div>

        {/* Scrubber Handle */}
        <motion.div
          className="absolute top-0 bottom-0 w-1 bg-blue-500 shadow-lg cursor-ew-resize z-10"
          style={{ left: `${progress}%` }}
          drag="x"
          dragConstraints={scrubberRef}
          dragElastic={0}
          onDrag={(_, info) => {
            const rect = scrubberRef.current?.getBoundingClientRect();
            if (rect) {
              const percentage = (info.offset.x + info.point.x - rect.left) / rect.width;
              const newTime = minTime + percentage * (maxTime - minTime);
              setCurrentTime(Math.max(minTime, Math.min(maxTime, newTime)));
              onTimeChange?.(newTime);
            }
          }}
          whileHover={{ scale: 2 }}
          whileDrag={{ scale: 2 }}
        >
          {/* Handle Tooltip */}
          <AnimatePresence>
            {isDragging && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 10 }}
                className="absolute -top-8 left-1/2 transform -translate-x-1/2 bg-gray-900 text-white text-xs px-2 py-1 rounded whitespace-nowrap"
              >
                {formatDuration(currentTime)}
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      </div>

      {/* Keyframe Legend */}
      {keyframes.length > 0 && (
        <div className="mt-3 flex items-center flex-wrap gap-2">
          <Bookmark className="w-3 h-3 text-gray-500" />
          <span className="text-xs text-gray-600 dark:text-gray-400">
            Keyframes:
          </span>
          {keyframes.slice(0, 5).map((keyframe) => (
            <button
              key={keyframe.id}
              onClick={() => {
                setCurrentTime(keyframe.time);
                onTimeChange?.(keyframe.time);
              }}
              className="px-2 py-1 bg-gray-100 dark:bg-gray-800 rounded text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
            >
              {keyframe.label}
            </button>
          ))}
          {keyframes.length > 5 && (
            <span className="text-xs text-gray-500">
              +{keyframes.length - 5} more
            </span>
          )}
        </div>
      )}

      {/* Causal Analysis Mode Indicator */}
      <CausalAnalysisIndicator currentTime={currentTime} />
    </div>
  );
};

/**
 * Control Button Component
 */
interface ControlButtonProps {
  icon: any;
  onClick: () => void;
  primary?: boolean;
  tooltip?: string;
}

const ControlButton: React.FC<ControlButtonProps> = ({
  icon: Icon,
  onClick,
  primary = false,
  tooltip,
}) => {
  return (
    <button
      onClick={onClick}
      className={`p-2 rounded-lg transition-all ${
        primary
          ? 'bg-blue-500 text-white hover:bg-blue-600 shadow-md hover:shadow-lg'
          : 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
      }`}
      title={tooltip}
    >
      <Icon className="w-4 h-4" />
    </button>
  );
};

/**
 * Causal Analysis Mode Indicator
 * Shows what events are active at the current time
 */
const CausalAnalysisIndicator: React.FC<{ currentTime: number }> = ({
  currentTime,
}) => {
  const { events } = useTimelineStore();

  // Find events happening at current time (within 1 second window)
  const activeEvents = events.filter(
    (e) => Math.abs(new Date(e.timestamp).getTime() - currentTime) < 1000
  );

  if (activeEvents.length === 0) return null;

  return (
    <div className="mt-3 p-2 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
      <div className="flex items-center space-x-2 mb-1">
        <Clock className="w-3 h-3 text-blue-600 dark:text-blue-400" />
        <span className="text-xs font-semibold text-blue-900 dark:text-blue-100">
          Active at this moment:
        </span>
      </div>
      <div className="flex flex-wrap gap-1">
        {activeEvents.slice(0, 3).map((event) => (
          <span
            key={event.event_id}
            className="text-[10px] px-2 py-0.5 bg-white dark:bg-gray-800 rounded-full text-blue-800 dark:text-blue-200 border border-blue-200 dark:border-blue-700"
          >
            {event.event_type.replace(/_/g, ' ')}
          </span>
        ))}
        {activeEvents.length > 3 && (
          <span className="text-[10px] text-blue-600 dark:text-blue-400">
            +{activeEvents.length - 3} more
          </span>
        )}
      </div>
    </div>
  );
};

export default TimelineScrubber;
