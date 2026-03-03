/**
 * Timeline Store - 时间轴状态管理
 *
 * 管理时间轴的播放状态、当前时间、关键帧等
 */

import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';

interface TimelineState {
  // Time
  currentTime: number;
  minTime: number;
  maxTime: number;

  // Playback
  isPlaying: boolean;
  playbackSpeed: number;

  // Keyframes
  keyframes: Array<{
    id: string;
    time: number;
    label: string;
    description?: string;
  }>;

  // Events (for causal analysis)
  events: Array<{
    event_id: string;
    event_type: string;
    timestamp: string;
    node_id: string;
  }>;

  // Actions
  setCurrentTime: (time: number) => void;
  togglePlay: () => void;
  setPlaybackSpeed: (speed: number) => void;
  jumpToStart: () => void;
  jumpToEnd: () => void;
  jumpBackward: (amount?: number) => void;
  jumpForward: (amount?: number) => void;
  addKeyframe: (keyframe: {
    id: string;
    time: number;
    label: string;
    description?: string;
  }) => void;
  setEvents: (events: any[]) => void;
  reset: () => void;
}

const initialState = {
  currentTime: 0,
  minTime: 0,
  maxTime: 10000,
  isPlaying: false,
  playbackSpeed: 1,
  keyframes: [],
  events: [],
};

export const useTimelineStore = create<TimelineState>()(
  devtools(
    persist(
      (set, get) => ({
        ...initialState,

        setCurrentTime: (time) =>
          set({ currentTime: time }),
        togglePlay: () =>
          set((state) => ({ isPlaying: !state.isPlaying })),
        setPlaybackSpeed: (speed) =>
          set({ playbackSpeed: speed }),

        jumpToStart: () =>
          set({ currentTime: 0, isPlaying: false }),

        jumpToEnd: () =>
          set((state) => ({ currentTime: state.maxTime, isPlaying: false })),

        jumpBackward: (amount = 1000) =>
          set((state) => ({
            currentTime: Math.max(state.minTime, state.currentTime - amount),
          })),

        jumpForward: (amount = 1000) =>
          set((state) => ({
            currentTime: Math.min(state.maxTime, state.currentTime + amount),
          })),

        addKeyframe: (keyframe) =>
          set((state) => ({
            keyframes: [...state.keyframes, keyframe].sort(
              (a, b) => a.time - b.time
            ),
          })),

        setEvents: (events) => set({ events }),

        reset: () => set(initialState),
      }),
      {
        name: 'timeline-storage',
        partialize: (state) => ({
          playbackSpeed: state.playbackSpeed,
          keyframes: state.keyframes,
        }),
      }
    ),
    { name: 'TimelineStore' }
  )
);
