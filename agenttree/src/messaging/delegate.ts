/**
 * Delegation — a manager dispatches a sub-task to a worker and
 * awaits the result.
 *
 * The worker runs its own agentic loop (through AgentRuntime.run())
 * and the result is sent back as a DelegateResult message.
 *
 * Usage (from TreeRuntime):
 *   const result = await delegator.delegate({
 *     from: "task_coordinator",
 *     to: "navigation_worker",
 *     input: "Navigate to Building A",
 *   })
 */

import type { AgentRuntime } from "../runtime/agent"
import type { RunOptions } from "../runtime/types"
import type { DelegateRequest, DelegateResult } from "./types"
import { MessageBus } from "./bus"

let _taskId = 0

export class Delegator {
  constructor(
    private bus: MessageBus,
    private agents: Map<string, AgentRuntime>,
  ) {}

  async delegate(
    params: {
      from: string
      to: string
      input: string
      metadata?: Record<string, unknown>
      runOptions?: RunOptions
    },
  ): Promise<DelegateResult> {
    const taskId = `task_${Date.now()}_${++_taskId}`

    const request: DelegateRequest = {
      taskId,
      from: params.from,
      to: params.to,
      input: params.input,
      metadata: params.metadata,
    }

    await this.bus.send({
      from: params.from,
      to: params.to,
      type: "delegate",
      content: params.input,
      metadata: { taskId, ...params.metadata },
    })

    const agent = this.agents.get(params.to)
    if (!agent) {
      const result: DelegateResult = {
        taskId,
        from: params.to,
        to: params.from,
        success: false,
        output: "",
        error: `Agent "${params.to}" not found`,
      }
      await this.bus.send({
        from: params.to,
        to: params.from,
        type: "delegate_result",
        content: JSON.stringify(result),
        metadata: { taskId },
      })
      return result
    }

    try {
      const runResult = await agent.run(params.input, params.runOptions)

      const result: DelegateResult = {
        taskId,
        from: params.to,
        to: params.from,
        success: true,
        output: runResult.response,
        toolCalls: runResult.toolCalls.map((tc) => ({
          tool: tc.tool,
          args: tc.args,
          result: tc.result,
        })),
      }

      await this.bus.send({
        from: params.to,
        to: params.from,
        type: "delegate_result",
        content: runResult.response,
        metadata: { taskId, iterations: runResult.iterations, usage: runResult.usage },
      })

      return result
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      const result: DelegateResult = {
        taskId,
        from: params.to,
        to: params.from,
        success: false,
        output: "",
        error: msg,
      }

      await this.bus.send({
        from: params.to,
        to: params.from,
        type: "delegate_result",
        content: `Error: ${msg}`,
        metadata: { taskId },
      })

      return result
    }
  }

  async delegateMany(
    params: {
      from: string
      tasks: Array<{ to: string; input: string; metadata?: Record<string, unknown> }>
      runOptions?: RunOptions
    },
  ): Promise<DelegateResult[]> {
    return Promise.all(
      params.tasks.map((t) =>
        this.delegate({
          from: params.from,
          to: t.to,
          input: t.input,
          metadata: t.metadata,
          runOptions: params.runOptions,
        }),
      ),
    )
  }
}
