/**
 * LLM types — OpenAI-compatible chat completion format.
 *
 * Kept as plain interfaces (no runtime deps) so any module can import
 * without pulling in the HTTP client.
 */

export interface ChatMessage {
  role: "system" | "user" | "assistant" | "tool"
  content: string
  tool_calls?: ToolCallRequest[]
  tool_call_id?: string
  name?: string
}

export interface ToolCallRequest {
  id: string
  type: "function"
  function: {
    name: string
    arguments: string
  }
}

export interface ChatResponse {
  content: string
  toolCalls: ToolCallRequest[]
  finishReason: string
  usage?: {
    promptTokens: number
    completionTokens: number
    totalTokens: number
  }
}

export interface ToolSchema {
  type: "function"
  function: {
    name: string
    description: string
    parameters: Record<string, unknown>
  }
}

export interface ChatOptions {
  model?: string
  temperature?: number
  maxTokens?: number
  tools?: ToolSchema[]
  signal?: AbortSignal
}
