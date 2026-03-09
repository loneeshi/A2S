import type { MemoryConfig } from "../spec/agent"
import { MemoryStore, NoopMemoryStore } from "./store"
import type { Mem0Bridge, SemanticMemory } from "./mem0-bridge"

export interface WorkingContext {
  recentActions: string[]
  lessons: string[]
  knownErrors: string[]
  semanticMemories: SemanticMemory[]
}

export class MemoryManager {
  private baseDir: string
  private stores = new Map<string, MemoryStore>()
  private mem0?: Mem0Bridge

  constructor(baseDir: string, mem0?: Mem0Bridge) {
    this.baseDir = baseDir
    this.mem0 = mem0
  }

  setMem0(mem0: Mem0Bridge): void {
    this.mem0 = mem0
  }

  getMem0(): Mem0Bridge | undefined {
    return this.mem0
  }

  hasMem0(): boolean {
    return this.mem0 !== undefined && this.mem0.isReady()
  }

  getStore(agentId: string, config: MemoryConfig): MemoryStore {
    if (config.mode === "off") {
      return new NoopMemoryStore({
        agentId,
        storeDir: this.baseDir,
        capacity: config.capacity,
      })
    }

    const existing = this.stores.get(agentId)
    if (existing) return existing

    const store = new MemoryStore({
      agentId,
      storeDir: this.baseDir,
      capacity: config.capacity,
      ttlHours: config.ttlHours,
    })

    this.stores.set(agentId, store)
    return store
  }

  async pruneAll(): Promise<number> {
    let total = 0
    for (const store of this.stores.values()) {
      total += await store.prune()
    }
    return total
  }

  async getWorkingContext(
    agentId: string,
    config: MemoryConfig,
    taskHint?: string,
  ): Promise<WorkingContext> {
    const store = this.getStore(agentId, config)

    const [actions, lessons, errors] = await Promise.all([
      store.query({ type: "action", limit: 5 }),
      store.query({ type: "lesson", limit: 5 }),
      store.query({ type: "error", limit: 3 }),
    ])

    let semanticMemories: SemanticMemory[] = []
    if (this.mem0 && taskHint) {
      semanticMemories = await this.mem0.searchRelevant(taskHint, {
        agentId,
        limit: 5,
      })
    }

    return {
      recentActions: actions.map((e) => e.content),
      lessons: lessons.map((e) => e.content),
      knownErrors: errors.map((e) => e.content),
      semanticMemories,
    }
  }

  async addSemanticMemory(
    agentId: string,
    content: string,
    metadata?: Record<string, unknown>,
  ): Promise<string | null> {
    if (!this.mem0) return null
    return this.mem0.addExperience(agentId, content, metadata)
  }

  async addLesson(
    agentId: string,
    lesson: string,
    metadata?: Record<string, unknown>,
  ): Promise<string | null> {
    if (!this.mem0) return null
    return this.mem0.addLesson(agentId, lesson, metadata)
  }

  async addOrgKnowledge(
    content: string,
    metadata?: Record<string, unknown>,
  ): Promise<string | null> {
    if (!this.mem0) return null
    return this.mem0.addOrgKnowledge(content, metadata)
  }

  async searchSemanticMemory(
    query: string,
    opts?: { agentId?: string; limit?: number },
  ): Promise<SemanticMemory[]> {
    if (!this.mem0) return []
    return this.mem0.searchRelevant(query, opts)
  }

  async searchForManager(
    taskDescription: string,
    limit = 5,
  ): Promise<SemanticMemory[]> {
    if (!this.mem0) return []
    return this.mem0.searchForManager(taskDescription, limit)
  }
}
