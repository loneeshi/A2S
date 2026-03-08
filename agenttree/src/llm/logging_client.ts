/**
 * LoggingLLMClient - Wrapper around LLMClient that logs API calls
 *
 * Sends API call data to bench_server for Tier 3 logging without
 * modifying the core LLMClient implementation.
 */

import { LLMClient, type LLMClientOptions } from "./client"
import type { ChatMessage, ChatResponse, ChatOptions } from "./types"

export interface LoggingLLMClientOptions extends LLMClientOptions {
  /** URL of bench_server to send logs to (e.g., http://127.0.0.1:8765) */
  loggingEndpoint?: string
  /** Whether to enable logging (default: true if loggingEndpoint provided) */
  enableLogging?: boolean
}

export class LoggingLLMClient extends LLMClient {
  private loggingEndpoint: string | undefined
  private enableLogging: boolean

  constructor(options: LoggingLLMClientOptions) {
    super(options)
    this.loggingEndpoint = options.loggingEndpoint
    this.enableLogging = options.enableLogging ?? !!options.loggingEndpoint
  }

  async chat(messages: ChatMessage[], options?: ChatOptions): Promise<ChatResponse> {
    if (!this.enableLogging || !this.loggingEndpoint) {
      // No logging, just call parent
      return super.chat(messages, options)
    }

    const startTime = Date.now()
    let response: ChatResponse | undefined
    let error: string | undefined

    try {
      response = await super.chat(messages, options)
      return response
    } catch (err) {
      error = err instanceof Error ? err.message : String(err)
      throw err
    } finally {
      const latencyMs = Date.now() - startTime

      // Send log to bench_server (fire and forget, don't block)
      this.sendLog({
        request: {
          model: options?.model ?? "gpt-4o-mini",
          messages: messages.map(m => ({
            role: m.role,
            content: m.content ?? "",
            tool_calls: (m as any).tool_calls,
          })),
          temperature: options?.temperature ?? 0.7,
          max_tokens: options?.maxTokens,
          tools: options?.tools,
        },
        response: response ? {
          content: response.content,
          tool_calls: response.toolCalls,
          finish_reason: response.finishReason,
        } : undefined,
        usage: response?.usage ? {
          prompt_tokens: response.usage.promptTokens,
          completion_tokens: response.usage.completionTokens,
          total_tokens: response.usage.totalTokens,
        } : undefined,
        latency_ms: latencyMs,
        error,
      }).catch(err => {
        // Silently ignore logging errors to not disrupt main flow
        console.warn(`[LoggingLLMClient] Failed to send log: ${err}`)
      })
    }
  }

  private async sendLog(data: Record<string, unknown>): Promise<void> {
    if (!this.loggingEndpoint) return

    try {
      const res = await fetch(`${this.loggingEndpoint}/log_api_call`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      })

      if (!res.ok) {
        console.warn(`[LoggingLLMClient] Log endpoint returned ${res.status}`)
      }
    } catch (err) {
      // Network errors are expected if bench_server is not running
      // Don't spam console in that case
    }
  }
}
