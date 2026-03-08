/**
 * Lightweight OpenAI-compatible LLM client.
 *
 * Uses native fetch with optional proxy support via undici ProxyAgent.
 * Supports tool calling, streaming is intentionally omitted to keep
 * each agent's runtime footprint minimal.
 */

import type { ChatMessage, ChatResponse, ChatOptions } from "./types"

export interface LLMClientOptions {
  apiKey: string
  baseURL?: string
  defaultModel?: string
  timeout?: number
  proxy?: string
}

let _dispatcher: unknown | undefined

async function getProxyDispatcher(proxyUrl: string): Promise<unknown> {
  if (_dispatcher) return _dispatcher
  try {
    const { ProxyAgent } = await import("undici")
    _dispatcher = new ProxyAgent(proxyUrl)
    return _dispatcher
  } catch {
    return undefined
  }
}

function detectProxy(): string | undefined {
  return (
    process.env.https_proxy ||
    process.env.HTTPS_PROXY ||
    process.env.http_proxy ||
    process.env.HTTP_PROXY ||
    undefined
  )
}

export class LLMClient {
  private apiKey: string
  private baseURL: string
  private defaultModel: string
  private timeout: number
  private proxy: string | undefined

  constructor(options: LLMClientOptions) {
    this.apiKey = options.apiKey
    this.baseURL = (options.baseURL ?? "https://api.openai.com/v1").replace(/\/+$/, "")
    this.defaultModel = options.defaultModel ?? "gpt-4o-mini"
    this.timeout = options.timeout ?? 120_000
    this.proxy = options.proxy ?? detectProxy()
  }

  async chat(messages: ChatMessage[], options?: ChatOptions): Promise<ChatResponse> {
    const model = options?.model ?? this.defaultModel

    const body: Record<string, unknown> = {
      model,
      messages,
      temperature: options?.temperature ?? 0.7,
    }

    if (options?.maxTokens) body.max_tokens = options.maxTokens
    if (options?.tools?.length) {
      body.tools = options.tools
      body.tool_choice = "auto"
    }

    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), this.timeout)

    try {
      const fetchOptions: Record<string, unknown> = {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${this.apiKey}`,
        },
        body: JSON.stringify(body),
        signal: options?.signal ?? controller.signal,
      }

      if (this.proxy) {
        const dispatcher = await getProxyDispatcher(this.proxy)
        if (dispatcher) {
          fetchOptions.dispatcher = dispatcher
        }
      }

      const res = await fetch(`${this.baseURL}/chat/completions`, fetchOptions as RequestInit)

      if (!res.ok) {
        const text = await res.text().catch(() => "")
        throw new Error(`LLM API ${res.status}: ${text.slice(0, 500)}`)
      }

      const data = (await res.json()) as any
      const choice = data.choices?.[0]
      const message = choice?.message

      return {
        content: message?.content ?? "",
        toolCalls: message?.tool_calls ?? [],
        finishReason: choice?.finish_reason ?? "stop",
        usage: data.usage
          ? {
              promptTokens: data.usage.prompt_tokens ?? 0,
              completionTokens: data.usage.completion_tokens ?? 0,
              totalTokens: data.usage.total_tokens ?? 0,
            }
          : undefined,
      }
    } finally {
      clearTimeout(timer)
    }
  }
}
