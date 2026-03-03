/**
 * Agent Store - Agent 状态管理
 *
 * 管理所有 Agent 的状态、选中状态、Handoff 记录等
 */

import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import { immer } from 'zustand/middleware/immer';

interface AgentState {
  node_id: string;
  node_type: string;
  role: string;
  status: 'idle' | 'thinking' | 'running' | 'waiting' | 'completed' | 'failed';
  system_prompt: string;
  user_messages: any[];
  tools: any[];
  created_at: string;
  started_at?: string;
  completed_at?: string;
  parent_id?: string;
  child_ids: string[];
  depth: number;
  dynamic_memory?: any;
  benchmark_context?: any;
  total_execution_time_ms: number;
  llm_call_count: number;
  tool_call_count: number;
  total_tokens_used: number;
  total_cost_usd: number;
  handoffs: any[];
  events: any[];
  error_message?: string;
  metadata: any;
}

interface Handoff {
  handoff_id: string;
  from_agent_id: string;
  to_agent_id: string;
  to_agent_role: string;
  timestamp: string;
  message_content: string;
  context_transferred: string[];
  response_required: boolean;
}

interface AgentStoreState {
  // Data
  agentStates: Record<string, AgentState>;
  handoffs: Handoff[];
  selectedAgentId: string | null;

  // Actions
  setAgentStates: (states: Record<string, AgentState>) => void;
  updateAgentState: (nodeId: string, updates: Partial<AgentState>) => void;
  selectAgent: (nodeId: string | null) => void;
  setHandoffs: (handoffs: Handoff[]) => void;
  addHandoff: (handoff: Handoff) => void;
  reset: () => void;
}

export const useAgentStore = create<AgentStoreState>()(
  devtools(
    immer((set) => ({
      // Initial state
      agentStates: {},
      handoffs: [],
      selectedAgentId: null,

      // Actions
      setAgentStates: (states) =>
        set((draft) => {
          draft.agentStates = states;
        }),

      updateAgentState: (nodeId, updates) =>
        set((draft) => {
          if (draft.agentStates[nodeId]) {
            Object.assign(draft.agentStates[nodeId], updates);
          }
        }),

      selectAgent: (nodeId) =>
        set((draft) => {
          draft.selectedAgentId = nodeId;
        }),

      setHandoffs: (handoffs) =>
        set((draft) => {
          draft.handoffs = handoffs;
        }),

      addHandoff: (handoff) =>
        set((draft) => {
          draft.handoffs.push(handoff);
        }),

      reset: () =>
        set((draft) => {
          draft.agentStates = {};
          draft.handoffs = [];
          draft.selectedAgentId = null;
        }),
    })),
    { name: 'AgentStore' }
  )
);
