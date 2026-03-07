import { mkdir, readFile, writeFile, appendFile, rm } from "fs/promises"
import { dirname } from "path"
import { MemoryEntrySchema, type MemoryEntry } from "../spec/memory"

export interface MemoryStoreConfig {
  agentId: string
  storeDir: string
  capacity: number
  ttlHours?: number
}

export class MemoryStore {
  protected agentId: string
  protected filePath: string
  protected capacity: number
  protected ttlHours?: number

  constructor(config: MemoryStoreConfig) {
    this.agentId = config.agentId
    this.filePath = `${config.storeDir}/${config.agentId}.jsonl`
    this.capacity = config.capacity
    this.ttlHours = config.ttlHours
  }

  async append(entry: Omit<MemoryEntry, "timestamp" | "agent">): Promise<void> {
    const full = MemoryEntrySchema.parse({
      ...entry,
      timestamp: new Date().toISOString(),
      agent: this.agentId,
    })

    await mkdir(dirname(this.filePath), { recursive: true })
    await appendFile(this.filePath, JSON.stringify(full) + "\n")

    const entries = await this.readAll()
    if (entries.length > this.capacity) {
      const trimmed = entries.slice(entries.length - this.capacity)
      await this.writeAll(trimmed)
    }
  }

  async query(filter: { type?: string; tags?: string[]; limit?: number }): Promise<MemoryEntry[]> {
    let entries = await this.readAll()

    if (filter.type) {
      entries = entries.filter((e) => e.type === filter.type)
    }
    if (filter.tags && filter.tags.length > 0) {
      const tagSet = new Set(filter.tags)
      entries = entries.filter((e) => e.tags.some((t) => tagSet.has(t)))
    }

    entries.reverse()

    if (filter.limit !== undefined) {
      entries = entries.slice(0, filter.limit)
    }

    return entries
  }

  async getRecent(n: number): Promise<MemoryEntry[]> {
    const entries = await this.readAll()
    return entries.slice(-n).reverse()
  }

  async prune(): Promise<number> {
    const entries = await this.readAll()
    const now = Date.now()

    const kept = entries.filter((e) => {
      const ttl = e.ttlHours ?? this.ttlHours
      if (ttl === undefined) return true
      const age = (now - new Date(e.timestamp).getTime()) / (1000 * 60 * 60)
      return age < ttl
    })

    const removed = entries.length - kept.length
    if (removed > 0) {
      await this.writeAll(kept)
    }
    return removed
  }

  async clear(): Promise<void> {
    try {
      await rm(this.filePath)
    } catch {
      // file may not exist
    }
  }

  async stats(): Promise<{ total: number; byType: Record<string, number> }> {
    const entries = await this.readAll()
    const byType: Record<string, number> = {}
    for (const e of entries) {
      byType[e.type] = (byType[e.type] ?? 0) + 1
    }
    return { total: entries.length, byType }
  }

  protected async readAll(): Promise<MemoryEntry[]> {
    let raw: string
    try {
      raw = await readFile(this.filePath, "utf-8")
    } catch {
      return []
    }

    return raw
      .split("\n")
      .filter((line) => line.trim().length > 0)
      .map((line) => MemoryEntrySchema.parse(JSON.parse(line)))
  }

  protected async writeAll(entries: MemoryEntry[]): Promise<void> {
    await mkdir(dirname(this.filePath), { recursive: true })
    const data = entries.map((e) => JSON.stringify(e)).join("\n") + "\n"
    await writeFile(this.filePath, data)
  }
}

export class NoopMemoryStore extends MemoryStore {
  async append(): Promise<void> {}
  async query(): Promise<MemoryEntry[]> { return [] }
  async getRecent(): Promise<MemoryEntry[]> { return [] }
  async prune(): Promise<number> { return 0 }
  async clear(): Promise<void> {}
  async stats(): Promise<{ total: number; byType: Record<string, number> }> {
    return { total: 0, byType: {} }
  }
}
