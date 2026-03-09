/**
 * BenchmarkBridge — connects to the Python bench_server.py via HTTP
 * and translates agenttree tool calls into real benchmark actions.
 *
 * Architecture:
 *   TS (AgentRuntime) → ToolExecutor → BenchmarkBridge → HTTP → bench_server.py → ALFWorld / StuLife
 *
 * The bridge:
 *   1. Spawns the Python server as a child process (optional)
 *   2. Provides `reset()` / `step()` / `status()` methods
 *   3. Registers tool handlers that map `env.*` calls to `step()` with the
 *      correct action string format for each benchmark
 *   4. Manages the server lifecycle
 */

import { spawn, type ChildProcess } from "node:child_process"
import { join } from "node:path"
import type { ToolHandler } from "../tool/executor"

export interface BridgeOptions {
  benchmark: "alfworld" | "stulife"
  host?: string
  port?: number
  pythonPath?: string
  autoStart?: boolean
  split?: string
  skip?: number
  configPath?: string
  projectRoot?: string
}

export interface ResetResult {
  task: string
  episode: number
  admissible_commands: string[]
}

export interface StepResult {
  observation: string
  done: boolean
  won: boolean
  reward: number
  admissible_commands: string[]
}

export interface StatusResult {
  benchmark: string
  episode: number
  done?: boolean
  last_reward?: number
}

export class BenchmarkBridge {
  private baseURL: string
  private benchmark: "alfworld" | "stulife"
  private serverProcess: ChildProcess | null = null
  private options: BridgeOptions

  private lastObs = ""
  private lastAdmissible: string[] = []
  private isDone = false
  private currentTask = ""

  constructor(options: BridgeOptions) {
    this.options = options
    this.benchmark = options.benchmark
    const host = options.host ?? "127.0.0.1"
    const port = options.port ?? 8765
    this.baseURL = `http://${host}:${port}`
  }

  async start(): Promise<void> {
    if (this.options.autoStart !== false) {
      await this.startServer()
    }
    await this.waitForServer(120_000)
  }

  async stop(): Promise<void> {
    try {
      await this.post("/shutdown", {})
    } catch {
      // server may already be down
    }
    if (this.serverProcess) {
      this.serverProcess.kill()
      this.serverProcess = null
    }
  }

  async reset(): Promise<ResetResult> {
    const result = await this.post<ResetResult>("/reset", {})
    let task = result.task
    // ALFWorld may return task as a Python tuple/repr string: "('...text...',)"
    // or "(\"...\",)" — strip the wrapping
    if (typeof task === "string") {
      const tupleMatch = task.match(/^\(\s*['"](.*)['"],?\s*\)$/s)
      if (tupleMatch) {
        task = tupleMatch[1]
      }
      // Unescape literal \n from Python repr
      task = task.replace(/\\n/g, "\n")
    }
    this.currentTask = task
    this.lastObs = task
    this.lastAdmissible = result.admissible_commands ?? []
    this.isDone = false
    return { ...result, task }
  }

  async step(action: string): Promise<StepResult> {
    const result = await this.post<StepResult>("/step", { action })
    this.lastObs = result.observation
    this.lastAdmissible = result.admissible_commands ?? []
    this.isDone = result.done
    return result
  }

  async status(): Promise<StatusResult> {
    return this.get<StatusResult>("/status")
  }

  getLastObservation(): string {
    return this.lastObs
  }

  getAdmissibleCommands(): string[] {
    return this.lastAdmissible
  }

  getCurrentTask(): string {
    return this.currentTask
  }

  getIsDone(): boolean {
    return this.isDone
  }

  /**
   * Finalize the current episode (notify server that episode is done)
   * This is important for StuLife to save session data
   */
  async finalizeEpisode(): Promise<void> {
    if (this.benchmark === "stulife") {
      try {
        await this.post("/finalize", {})
      } catch (error) {
        console.warn("Failed to finalize episode:", error)
      }
    }
  }

  /**
   * Build tool handlers that map env.* tool calls → benchmark step() calls.
   *
   * ALFWorld actions are plain text commands like "go to fridge 1", "take apple 1 from countertop 2".
   * StuLife actions use dot-notation method calls like "geography.walk_to(library)".
   */
  createToolHandlers(): Record<string, ToolHandler> {
    if (this.benchmark === "alfworld") {
      return this.createALFWorldHandlers()
    } else {
      return this.createStuLifeHandlers()
    }
  }

  private createALFWorldHandlers(): Record<string, ToolHandler> {
    const bridge = this

    const withHints = (result: StepResult): string => {
      let obs = result.observation
      if (result.admissible_commands?.length > 0) {
        const cmds = result.admissible_commands.slice(0, 20)
        const more = result.admissible_commands.length > 20
          ? ` ... +${result.admissible_commands.length - 20} more`
          : ""
        obs += `\n[Available actions]: ${cmds.join("; ")}${more}`
      }
      return obs
    }

    return {
      "env.look": async (args) => {
        const target = args.target as string | undefined
        const action = target ? `examine ${target}` : "look"
        return withHints(await bridge.step(action))
      },
      "env.goto": async (args) => {
        const target = args.target as string
        return withHints(await bridge.step(`go to ${target}`))
      },
      "env.take": async (args) => {
        const obj = args.object as string
        const rec = args.receptacle as string
        return withHints(await bridge.step(`take ${obj} from ${rec}`))
      },
      "env.put": async (args) => {
        const obj = args.object as string
        const rec = args.receptacle as string
        return withHints(await bridge.step(`put ${obj} in/on ${rec}`))
      },
      "env.open": async (args) => {
        const rec = args.receptacle as string
        return withHints(await bridge.step(`open ${rec}`))
      },
      "env.close": async (args) => {
        const rec = args.receptacle as string
        return withHints(await bridge.step(`close ${rec}`))
      },
      "env.clean": async (args) => {
        const obj = args.object as string
        const rec = args.receptacle as string
        return withHints(await bridge.step(`clean ${obj} with ${rec}`))
      },
      "env.heat": async (args) => {
        const obj = args.object as string
        const rec = args.receptacle as string
        return withHints(await bridge.step(`heat ${obj} with ${rec}`))
      },
      "env.cool": async (args) => {
        const obj = args.object as string
        const rec = args.receptacle as string
        return withHints(await bridge.step(`cool ${obj} with ${rec}`))
      },
      "env.toggle": async (args) => {
        const obj = args.object as string
        return withHints(await bridge.step(`use ${obj}`))
      },
      "env.examine": async (args) => {
        const target = args.target as string
        return withHints(await bridge.step(`examine ${target}`))
      },
    }
  }

  private createStuLifeHandlers(): Record<string, ToolHandler> {
    const bridge = this

    // Helper function to build StuLife action format: <action>Action: method(k="v", k="v")</action>
    const buildAction = (method: string, args: Record<string, unknown>): string => {
      const argsStr = Object.entries(args)
        .filter(([, v]) => v !== undefined && v !== "")
        .map(([k, v]) => `${k}=${JSON.stringify(v)}`)
        .join(", ")
      return `<action>Action: ${method}(${argsStr})</action>`
    }

    const stuLifeCall = async (method: string, args: Record<string, unknown>): Promise<string> => {
      const action = buildAction(method, args)
      const result = await bridge.step(action)
      return result.observation
    }

    return {
      // Map System
      "map.find_building_id": async (args) =>
        stuLifeCall("map.find_building_id", args),
      "map.get_building_details": async (args) =>
        stuLifeCall("map.get_building_details", args),
      "map.find_room_location": async (args) =>
        stuLifeCall("map.find_room_location", args),
      "map.find_optimal_path": async (args) =>
        stuLifeCall("map.find_optimal_path", args),
      "map.query_buildings_by_property": async (args) =>
        stuLifeCall("map.query_buildings_by_property", args),

      // Geography System
      "geography.walk_to": async (args) =>
        stuLifeCall("geography.walk_to", args),
      "geography.get_current_location": async () =>
        stuLifeCall("geography.get_current_location", {}),
      "geography.set_location": async (args) =>
        stuLifeCall("geography.set_location", args),

      // Email System - map to StuLife method names
      "email.send": async (args) =>
        stuLifeCall("email.send_email", args),
      "email.search": async (args) =>
        stuLifeCall("email.view_inbox", args),
      "email.read": async (args) =>
        stuLifeCall("email.view_inbox", args),
      "email.reply": async (args) =>
        stuLifeCall("email.reply_email", args),
      "email.forward": async (args) =>
        stuLifeCall("email.send_email", args),
      "email.delete": async (args) =>
        stuLifeCall("email.delete_email", args),

      // Calendar System
      "calendar.add_event": async (args) =>
        stuLifeCall("calendar.add_event", args),
      "calendar.remove_event": async (args) =>
        stuLifeCall("calendar.remove_event", args),
      "calendar.update_event": async (args) =>
        stuLifeCall("calendar.update_event", args),
      "calendar.view_schedule": async (args) =>
        stuLifeCall("calendar.view_schedule", args),
      "calendar.search_events": async (args) =>
        stuLifeCall("calendar.view_schedule", args),
      "calendar.get_schedule": async (args) =>
        stuLifeCall("calendar.view_schedule", args),
      "calendar.query_advisor_availability": async (args) =>
        stuLifeCall("calendar.query_advisor_availability", args),

      // Course Selection System
      "course.search": async (args) => {
        // Convert query parameter to filters format
        const filters: Record<string, unknown> = {}
        if (args.query) {
          const query = String(args.query)
          // If query looks like a course code (contains numbers or hyphens), use course_code filter
          // Otherwise use course_name filter
          if (/[0-9-]/.test(query)) {
            filters.course_code = query
          } else {
            filters.course_name = query
          }
        }
        if (args.department) {
          filters.course_code = args.department
        }
        return stuLifeCall("course_selection.browse_courses", Object.keys(filters).length > 0 ? { filters } : {})
      },
      "course.get_details": async (args) => {
        const filters: Record<string, unknown> = {}
        if (args.course_id) {
          filters.course_code = args.course_id
        }
        return stuLifeCall("course_selection.browse_courses", Object.keys(filters).length > 0 ? { filters } : {})
      },
      "course.check_prerequisites": async (args) =>
        stuLifeCall("course_selection.browse_courses", {}),
      "course.check_conflicts": async (args) =>
        stuLifeCall("draft.view", {}),
      "course.register": async (args) =>
        stuLifeCall("draft.add_course", args),
      "course.drop": async (args) =>
        stuLifeCall("draft.remove_course", args),

      // Draft System
      "draft.add_course": async (args) =>
        stuLifeCall("draft.add_course", args),
      "draft.remove_course": async (args) =>
        stuLifeCall("draft.remove_course", args),
      "draft.assign_pass": async (args) =>
        stuLifeCall("draft.assign_pass", args),
      "draft.view": async () =>
        stuLifeCall("draft.view", {}),

      // Registration System
      "registration.submit_draft": async () =>
        stuLifeCall("registration.submit_draft", {}),

      // Reservation System
      "reservation.make": async (args) =>
        stuLifeCall("reservation.make_booking", args),
      "reservation.check_availability": async (args) =>
        stuLifeCall("reservation.query_availability", args),
      "reservation.cancel": async (args) =>
        stuLifeCall("reservation.make_booking", args),
      "reservation.query_availability": async (args) =>
        stuLifeCall("reservation.query_availability", args),
      "reservation.make_booking": async (args) =>
        stuLifeCall("reservation.make_booking", args),

      // Bibliography System
      "bibliography.list_chapters": async (args) =>
        stuLifeCall("bibliography.list_chapters", args),
      "bibliography.list_sections": async (args) =>
        stuLifeCall("bibliography.list_sections", args),
      "bibliography.list_articles": async (args) =>
        stuLifeCall("bibliography.list_articles", args),
      "bibliography.view_article": async (args) =>
        stuLifeCall("bibliography.view_article", args),

      // Data System
      "data_system.list_by_category": async (args) =>
        stuLifeCall("data_system.list_by_category", args),
      "data_system.query_by_identifier": async (args) =>
        stuLifeCall("data_system.query_by_identifier", args),
      "data_system.list_books_by_category": async (args) =>
        stuLifeCall("data_system.list_books_by_category", args),
      "data_system.search_books": async (args) =>
        stuLifeCall("data_system.search_books", args),

      // Special: finish action
      "finish": async () => {
        const action = "<action>Action: finish()</action>"
        const result = await bridge.step(action)
        return result.observation
      },
    }
  }

  // ---------- HTTP helpers ----------

  private async post<T>(path: string, body: Record<string, unknown>): Promise<T> {
    const res = await fetch(`${this.baseURL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
    if (!res.ok) {
      const text = await res.text().catch(() => "")
      throw new Error(`Bridge ${path} failed (${res.status}): ${text.slice(0, 300)}`)
    }
    return res.json() as Promise<T>
  }

  private async get<T>(path: string): Promise<T> {
    const res = await fetch(`${this.baseURL}${path}`)
    if (!res.ok) {
      const text = await res.text().catch(() => "")
      throw new Error(`Bridge ${path} failed (${res.status}): ${text.slice(0, 300)}`)
    }
    return res.json() as Promise<T>
  }

  // ---------- Server lifecycle ----------

  private async startServer(): Promise<void> {
    const python = this.options.pythonPath ?? "python3"
    const projectRoot =
      this.options.projectRoot ??
      join(import.meta.dirname ?? __dirname, "..", "..")

    const serverScript = join(projectRoot, "agenttree", "bridge", "bench_server.py")

    const args = [
      serverScript,
      "--benchmark", this.benchmark,
      "--port", String(this.options.port ?? 8765),
      "--host", this.options.host ?? "127.0.0.1",
    ]

    if (this.options.split) args.push("--split", this.options.split)
    if (this.options.configPath) args.push("--config", this.options.configPath)
    if (this.options.skip && this.options.skip > 0) args.push("--skip", String(this.options.skip))

    this.serverProcess = spawn(python, args, {
      cwd: projectRoot,
      stdio: ["ignore", "pipe", "pipe"],
      env: {
        ...process.env,
        PYTHONPATH: projectRoot,
      },
    })

    this.serverProcess.stdout?.on("data", (data: Buffer) => {
      const line = data.toString().trim()
      if (line) console.log(`[bench_server] ${line}`)
    })

    this.serverProcess.stderr?.on("data", (data: Buffer) => {
      const line = data.toString().trim()
      if (line) console.error(`[bench_server] ${line}`)
    })

    this.serverProcess.on("exit", (code) => {
      if (code !== 0 && code !== null) {
        console.error(`[bench_server] exited with code ${code}`)
      }
      this.serverProcess = null
    })
  }

  private async waitForServer(timeoutMs: number): Promise<void> {
    const start = Date.now()
    while (Date.now() - start < timeoutMs) {
      try {
        await this.get("/health")
        return
      } catch {
        await new Promise((r) => setTimeout(r, 500))
      }
    }
    throw new Error(
      `Bridge server did not start within ${timeoutMs}ms at ${this.baseURL}`,
    )
  }
}
