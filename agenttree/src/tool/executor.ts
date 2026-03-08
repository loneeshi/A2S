/**
 * Tool executor — bridges ToolDefinition schemas to actual handler functions.
 *
 * The registry stores *definitions* (JSON metadata).
 * The executor stores *handlers* (functions that actually run).
 * Together they give an agent both the schema (for LLM) and the logic (for execution).
 */

import type { ToolDefinition } from "./registry"
import type { ToolSchema } from "../llm/types"

export interface ToolResult {
  ok: boolean
  output: string
  error?: string
  durationMs?: number
}

export type ToolHandler = (args: Record<string, unknown>) => Promise<string>

export class ToolExecutor {
  private handlers = new Map<string, ToolHandler>()

  register(toolId: string, handler: ToolHandler): void {
    this.handlers.set(toolId, handler)
  }

  registerMany(tools: Record<string, ToolHandler>): void {
    for (const [id, handler] of Object.entries(tools)) {
      this.handlers.set(id, handler)
    }
  }

  has(toolId: string): boolean {
    return this.handlers.has(toolId)
  }

  list(): string[] {
    return Array.from(this.handlers.keys())
  }

  async execute(toolId: string, args: Record<string, unknown>): Promise<ToolResult> {
    const handler = this.handlers.get(toolId)
    if (!handler) {
      return { ok: false, output: "", error: `Tool "${toolId}" not registered` }
    }

    const start = Date.now()
    try {
      const output = await handler(args)
      return { ok: true, output, durationMs: Date.now() - start }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      return { ok: false, output: "", error: msg, durationMs: Date.now() - start }
    }
  }

  /**
   * Convert ToolDefinition[] to OpenAI function-calling schemas.
   * Only includes tools that have registered handlers.
   */
  toOpenAISchemas(definitions: ToolDefinition[]): ToolSchema[] {
    return definitions
      .filter((d) => this.handlers.has(d.id))
      .map((d) => ({
        type: "function" as const,
        function: {
          name: d.id,
          description: d.description,
          parameters: {
            type: "object",
            properties: Object.fromEntries(
              Object.entries(d.parameters).map(([name, param]) => [
                name,
                { type: param.type, description: param.description },
              ]),
            ),
            required: Object.entries(d.parameters)
              .filter(([, param]) => param.required)
              .map(([name]) => name),
          },
        },
      }))
  }
}
