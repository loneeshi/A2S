/**
 * Mem0Bridge — typed wrapper around mem0ai/oss Memory class.
 *
 * Design principles:
 *   1. SELECTIVE WRITES — mem0 calls LLM on every add() for fact extraction,
 *      so we only write high-value semantic memories (lessons, strategies, user prefs),
 *      never raw tool call logs (those stay in JSONL).
 *   2. SCOPED ACCESS — uses mem0's userId/agentId/runId to enforce:
 *      - org level: shared environment knowledge (all agents read)
 *      - agent level: per-agent experience (private + manager reads)
 *      - session level: current episode context (ephemeral)
 *   3. GRACEFUL DEGRADATION — if mem0 init fails or search errors,
 *      methods return empty results rather than crashing the pipeline.
 */

import { Memory } from "mem0ai/oss"
import type { SearchResult, MemoryItem } from "mem0ai/oss"

export interface Mem0BridgeConfig {
  apiKey: string
  baseUrl: string
  extractionModel?: string
  embeddingModel?: string
  historyDbPath?: string
  collectionName?: string
}

export type MemoryScope = "org" | "agent" | "session"

export interface ScopedAddOptions {
  scope: MemoryScope
  agentId?: string
  sessionId?: string
  metadata?: Record<string, unknown>
}

export interface ScopedSearchOptions {
  scope: MemoryScope
  agentId?: string
  sessionId?: string
  limit?: number
}

export interface SemanticMemory {
  id: string
  content: string
  score?: number
  metadata?: Record<string, unknown>
  createdAt?: string
}

const ORG_USER_ID = "a2s_shared"

export class Mem0Bridge {
  private memory: Memory
  private ready = false
  private initError?: string

  constructor(config: Mem0BridgeConfig) {
    this.memory = new Memory({
      embedder: {
        provider: "openai",
        config: {
          model: config.embeddingModel ?? "text-embedding-ada-002",
          apiKey: config.apiKey,
          url: config.baseUrl,
        },
      },
      vectorStore: {
        provider: "memory",
        config: {
          collectionName: config.collectionName ?? "a2s_memories",
        },
      },
      llm: {
        provider: "openai",
        config: {
          model: config.extractionModel ?? "gpt-4o-mini",
          apiKey: config.apiKey,
          baseURL: config.baseUrl,
        },
      },
      disableHistory: false,
      historyDbPath: config.historyDbPath ?? "memory/mem0_history.db",
    })
    this.ready = true
  }

  isReady(): boolean {
    return this.ready
  }

  getInitError(): string | undefined {
    return this.initError
  }

  private buildEntity(opts: ScopedAddOptions | ScopedSearchOptions): {
    userId?: string
    agentId?: string
    runId?: string
  } {
    switch (opts.scope) {
      case "org":
        return { userId: ORG_USER_ID }
      case "agent":
        return {
          userId: ORG_USER_ID,
          agentId: opts.agentId ?? "unknown",
        }
      case "session":
        return {
          userId: ORG_USER_ID,
          agentId: opts.agentId ?? "unknown",
          runId: opts.sessionId ?? "default",
        }
    }
  }

  async add(content: string, opts: ScopedAddOptions): Promise<string | null> {
    if (!this.ready) return null

    try {
      const entity = this.buildEntity(opts)
      const result = await this.memory.add(content, {
        ...entity,
        metadata: opts.metadata as Record<string, any>,
      })
      const items = (result as SearchResult)?.results
      return items?.[0]?.id ?? null
    } catch (err) {
      console.warn("[mem0] add failed:", (err as Error).message)
      return null
    }
  }

  async search(query: string, opts: ScopedSearchOptions): Promise<SemanticMemory[]> {
    if (!this.ready) return []

    try {
      const entity = this.buildEntity(opts)
      const result = await this.memory.search(query, {
        ...entity,
        limit: opts.limit ?? 5,
      })
      return (result.results ?? []).map(this.toSemanticMemory)
    } catch (err) {
      console.warn("[mem0] search failed:", (err as Error).message)
      return []
    }
  }

  async addExperience(
    agentId: string,
    content: string,
    metadata?: Record<string, unknown>,
  ): Promise<string | null> {
    return this.add(content, {
      scope: "agent",
      agentId,
      metadata: { type: "experience", ...metadata },
    })
  }

  async addLesson(
    agentId: string,
    lesson: string,
    metadata?: Record<string, unknown>,
  ): Promise<string | null> {
    return this.add(lesson, {
      scope: "agent",
      agentId,
      metadata: { type: "lesson", ...metadata },
    })
  }

  async addOrgKnowledge(
    content: string,
    metadata?: Record<string, unknown>,
  ): Promise<string | null> {
    return this.add(content, {
      scope: "org",
      metadata: { type: "org_knowledge", ...metadata },
    })
  }

  async searchRelevant(
    query: string,
    opts?: { agentId?: string; limit?: number },
  ): Promise<SemanticMemory[]> {
    const results: SemanticMemory[] = []

    const orgResults = await this.search(query, {
      scope: "org",
      limit: opts?.limit ?? 3,
    })
    results.push(...orgResults)

    if (opts?.agentId) {
      const agentResults = await this.search(query, {
        scope: "agent",
        agentId: opts.agentId,
        limit: opts?.limit ?? 3,
      })
      results.push(...agentResults)
    }

    results.sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
    return results.slice(0, opts?.limit ?? 5)
  }

  async searchForManager(
    taskDescription: string,
    limit = 5,
  ): Promise<SemanticMemory[]> {
    return this.searchRelevant(taskDescription, {
      agentId: "alfworld_manager",
      limit,
    })
  }

  async getAll(opts: ScopedSearchOptions): Promise<SemanticMemory[]> {
    if (!this.ready) return []

    try {
      const entity = this.buildEntity(opts)
      const result = await this.memory.getAll({
        ...entity,
        limit: opts.limit ?? 100,
      })
      return (result.results ?? []).map(this.toSemanticMemory)
    } catch (err) {
      console.warn("[mem0] getAll failed:", (err as Error).message)
      return []
    }
  }

  async deleteSession(agentId: string, sessionId: string): Promise<void> {
    if (!this.ready) return

    try {
      await this.memory.deleteAll({
        userId: ORG_USER_ID,
        agentId,
        runId: sessionId,
      })
    } catch (err) {
      console.warn("[mem0] deleteSession failed:", (err as Error).message)
    }
  }

  async reset(): Promise<void> {
    if (!this.ready) return
    try {
      await this.memory.reset()
    } catch (err) {
      console.warn("[mem0] reset failed:", (err as Error).message)
    }
  }

  async stats(): Promise<{ org: number; agents: Record<string, number> }> {
    const orgItems = await this.getAll({ scope: "org", limit: 1000 })
    return {
      org: orgItems.length,
      agents: {},
    }
  }

  private toSemanticMemory(item: MemoryItem): SemanticMemory {
    return {
      id: item.id,
      content: item.memory,
      score: item.score,
      metadata: item.metadata,
      createdAt: item.createdAt,
    }
  }
}
