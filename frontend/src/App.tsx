/**
 * Agent Visualization App - Main Application
 *
 * 组合所有组件，实现完整的"去黑箱化"可视化体验
 * - Liquid Graph Canvas
 * - Agent Cognitive Inspector
 * - Timeline Scrubber
 */

import React, { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { LiquidGraphCanvas } from './components/LiquidGraphCanvas';
import { AgentCognitiveInspector } from './components/AgentCognitiveInspector';
import { TimelineScrubber } from './components/TimelineScrubber';
import { useAgentStore } from './store/agentStore';
import { useTimelineStore } from './store/timelineStore';
import { LoadTraceData } from './components/LoadTraceData';
import { Header } from './components/Header';

function App() {
  const [traceData, setTraceData] = useState<any>(null);
  const [isInspectorOpen, setIsInspectorOpen] = useState(true);

  // Load trace data (in real app, this would come from API)
  useEffect(() => {
    // Check if we have saved trace data
    const savedTrace = localStorage.getItem('lastTraceData');
    if (savedTrace) {
      try {
        setTraceData(JSON.parse(savedTrace));
      } catch (e) {
        console.error('Failed to load saved trace:', e);
      }
    }
  }, []);

  // Initialize stores with trace data
  useEffect(() => {
    if (!traceData) return;

    console.log('Loading trace data into stores:', traceData);

    const { setAgentStates, setHandoffs } = useAgentStore.getState();
    const { setEvents, addKeyframe } = useTimelineStore.getState();

    // Set agent states
    const allNodes = traceData.all_nodes || {};
    console.log('Setting agent states:', Object.keys(allNodes).length, 'agents');
    setAgentStates(allNodes);

    // Set handoffs
    const allHandoffs: any[] = [];
    Object.values(allNodes).forEach((agent: any) => {
      if (agent.handoffs) {
        allHandoffs.push(...agent.handoffs);
      }
    });
    setHandoffs(allHandoffs);

    // Set events
    setEvents(traceData.events || []);

    // Add keyframes from events
    (traceData.events || []).forEach((event: any) => {
      if (event.event_type === 'node_created' || event.event_type === 'handoff_start') {
        addKeyframe({
          id: event.event_id,
          time: new Date(event.timestamp).getTime(),
          label: event.event_type.replace(/_/g, ' '),
          description: event.content?.role || '',
        });
      }
    });

    // Set time range
    const startTime = traceData.started_at
      ? new Date(traceData.started_at).getTime()
      : 0;
    const endTime = traceData.completed_at
      ? new Date(traceData.completed_at).getTime()
      : startTime + 10000;

    useTimelineStore.setState({
      minTime: startTime,
      maxTime: endTime,
      currentTime: startTime,
    });

    console.log('Stores initialized successfully');
  }, [traceData]);

  const handleTimeChange = (time: number) => {
    // Update agent states based on time
    // This would filter events and show only those before current time
  };

  return (
    <div className="h-screen w-screen flex flex-col bg-gray-50 dark:bg-gray-900 overflow-hidden">
      {/* Header */}
      <Header traceData={traceData} />

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Graph Canvas - Takes 70% width */}
        <div className="flex-[7] flex flex-col overflow-hidden">
          <LiquidGraphCanvas
            className="flex-1"
            onNodeClick={() => setIsInspectorOpen(true)}
          />

          {/* Timeline Scrubber - Fixed at bottom */}
          <div className="h-32 bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 p-4 overflow-y-auto">
            <TimelineScrubber onTimeChange={handleTimeChange} />
          </div>
        </div>

        {/* Agent Cognitive Inspector - Takes 30% width */}
        <AnimatePresence>
          {isInspectorOpen && (
            <motion.div
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: '30%', opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              transition={{ duration: 0.3 }}
              className="relative"
            >
              <AgentCognitiveInspector className="h-full" />

              {/* Collapse Button */}
              <button
                onClick={() => setIsInspectorOpen(false)}
                className="absolute left-0 top-1/2 transform -translate-y-1/2 -translate-x-full bg-white dark:bg-gray-800 border border-r border-gray-200 dark:border-gray-700 rounded-l-lg px-2 py-4 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
              >
                <svg
                  className="w-4 h-4 text-gray-500"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M15 19l-7-7 7-7"
                  />
                </svg>
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Expand Button (when inspector is closed) */}
        {!isInspectorOpen && (
          <button
            onClick={() => setIsInspectorOpen(true)}
            className="absolute right-0 top-1/2 transform -translate-y-1/2 bg-white dark:bg-gray-800 border border-l border-gray-200 dark:border-gray-700 rounded-r-lg px-2 py-4 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors z-10"
          >
            <svg
              className="w-4 h-4 text-gray-500"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 5l7 7-7 7"
              />
            </svg>
          </button>
        )}
      </div>

      {/* Load Trace Data Modal */}
      {!traceData && <LoadTraceData onLoad={setTraceData} />}
    </div>
  );
}

export default App;
