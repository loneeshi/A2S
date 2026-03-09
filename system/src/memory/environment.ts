/**
 * EnvironmentMemory — cross-episode knowledge about the physical environment.
 *
 * Built incrementally from agent observations during task execution.
 * Provides recall() for injecting relevant environment knowledge into prompts.
 *
 * Three storage layers:
 *   - Spatial: what receptacles/objects exist at each location
 *   - Objects: where each object type has been found (with frequency)
 *   - States: default/observed states of entities (open/closed, on/off)
 *
 * Configurable via EnvironmentMemoryConfig:
 *   - enabled: master toggle (off for unseen environment evaluation)
 *   - maxEntries: cap on total stored entries
 *   - consolidateEvery: episodes between compression passes
 *   - decayFactor: weight decay for old observations during consolidation
 *   - backend: "local" (in-memory matching) or "semantic-router" (embedding similarity)
 *
 * The parser is pluggable: ALFWorld uses regex-based extraction,
 * stulife can provide its own parser for campus-specific observations.
 */

import { mkdir, readFile, writeFile } from "node:fs/promises"
import { dirname } from "node:path"
import type {
  EnvironmentMemoryConfig,
  EnvironmentParser,
  SpatialEntry,
  ObjectEntry,
  StateEntry,
  TemporalEntry,
  EnvironmentMemorySnapshot,
} from "./environment-types"
import { DEFAULT_ENV_MEMORY_CONFIG } from "./environment-types"

function normalizeObjectType(name: string): string {
  return name.replace(/\s*\d+$/, "").trim().toLowerCase()
}

export class EnvironmentMemory {
  readonly config: EnvironmentMemoryConfig
  private parser: EnvironmentParser

  private spatial = new Map<string, SpatialEntry>()
  private objects = new Map<string, ObjectEntry>()
  private states = new Map<string, StateEntry>()
  private temporal = new Map<string, TemporalEntry>()

  private totalObservations = 0
  private lastEpisode = 0
  private currentLocation: string | null = null

  constructor(config: Partial<EnvironmentMemoryConfig>, parser: EnvironmentParser) {
    this.config = { ...DEFAULT_ENV_MEMORY_CONFIG, ...config }
    this.parser = parser
  }

  observe(action: string, observation: string, episode: number): void {
    if (!this.config.enabled) return

    this.lastEpisode = Math.max(this.lastEpisode, episode)
    this.totalObservations++

    const spatialUpdate = this.parser.parseLocation(action, observation)
    if (spatialUpdate) {
      this.currentLocation = spatialUpdate.location
      this.updateSpatial(spatialUpdate.location, spatialUpdate.contains, spatialUpdate.connections, episode)
    }

    const objectUpdates = this.parser.parseObjects(observation)
    for (const obj of objectUpdates) {
      this.updateObject(obj.objectType, obj.location, episode)
    }

    const stateUpdate = this.parser.parseState(action, observation)
    if (stateUpdate) {
      this.updateState(stateUpdate.entity, stateUpdate.property, stateUpdate.value, episode)
    }

    if (this.parser.parseTemporal) {
      const temporalUpdate = this.parser.parseTemporal(observation)
      if (temporalUpdate) {
        this.updateTemporal(temporalUpdate.entity, temporalUpdate.pattern, temporalUpdate.confidence ?? 0.5, episode)
      }
    }
  }

  recall(taskDescription: string, currentLoc?: string): string {
    if (!this.config.enabled) return ""

    const sections: string[] = []

    const loc = currentLoc ?? this.currentLocation
    if (loc) {
      const s = this.spatial.get(loc)
      if (s && s.contains.length > 0) {
        sections.push(`Known contents of ${loc}: ${s.contains.join(", ")}`)
      }
    }

    const targetObjects = this.extractTargetObjects(taskDescription)
    for (const objType of targetObjects) {
      const entry = this.objects.get(objType)
      if (entry) {
        const locations = Object.entries(entry.locationCounts)
          .sort(([, a], [, b]) => b - a)
          .slice(0, 5)
          .map(([l, count]) => `${l} (${count}x)`)
        sections.push(`${objType} previously found at: ${locations.join(", ")}`)
      }
    }

    const relevantReceptacles = this.findRelevantReceptacles(taskDescription)
    for (const recep of relevantReceptacles) {
      const s = this.spatial.get(recep)
      if (s && s.contains.length > 0) {
        sections.push(`${recep} contained: ${s.contains.join(", ")}`)
      }

      const stateKey = `${recep}:open_closed`
      const state = this.states.get(stateKey)
      if (state) {
        sections.push(`${recep} is usually ${state.defaultValue}`)
      }
    }

    if (sections.length === 0) return ""

    return `## Environment Knowledge (from previous episodes)\n${sections.join("\n")}`
  }

  resetEpisodeState(): void {
    this.currentLocation = null
  }

  consolidate(): void {
    for (const [, entry] of this.objects) {
      for (const loc of Object.keys(entry.locationCounts)) {
        entry.locationCounts[loc] = Math.max(1, Math.floor(entry.locationCounts[loc] * this.config.decayFactor))
      }
    }

    for (const [, entry] of this.states) {
      if (entry.observations.length > 20) {
        entry.observations = entry.observations.slice(-20)
      }
      entry.defaultValue = this.computeMode(entry.observations.map((o) => o.value))
    }

    this.enforceMaxEntries()
  }

  clear(): void {
    this.spatial.clear()
    this.objects.clear()
    this.states.clear()
    this.temporal.clear()
    this.totalObservations = 0
    this.lastEpisode = 0
    this.currentLocation = null
  }

  isEmpty(): boolean {
    return this.spatial.size === 0 && this.objects.size === 0 && this.states.size === 0
  }

  stats(): { spatial: number; objects: number; states: number; temporal: number; total: number } {
    return {
      spatial: this.spatial.size,
      objects: this.objects.size,
      states: this.states.size,
      temporal: this.temporal.size,
      total: this.spatial.size + this.objects.size + this.states.size + this.temporal.size,
    }
  }

  async save(filePath: string): Promise<void> {
    const snapshot: EnvironmentMemorySnapshot = {
      version: 1,
      spatial: Object.fromEntries(this.spatial),
      objects: Object.fromEntries(this.objects),
      states: Object.fromEntries(this.states),
      temporal: Object.fromEntries(this.temporal),
      totalObservations: this.totalObservations,
      lastEpisode: this.lastEpisode,
    }
    await mkdir(dirname(filePath), { recursive: true })
    await writeFile(filePath, JSON.stringify(snapshot, null, 2), "utf-8")
  }

  async load(filePath: string): Promise<boolean> {
    try {
      const raw = await readFile(filePath, "utf-8")
      const snapshot = JSON.parse(raw) as EnvironmentMemorySnapshot
      if (snapshot.version !== 1) return false

      this.spatial = new Map(Object.entries(snapshot.spatial))
      this.objects = new Map(Object.entries(snapshot.objects))
      this.states = new Map(Object.entries(snapshot.states))
      this.temporal = new Map(Object.entries(snapshot.temporal))
      this.totalObservations = snapshot.totalObservations ?? 0
      this.lastEpisode = snapshot.lastEpisode ?? 0
      return true
    } catch {
      return false
    }
  }

  private updateSpatial(location: string, contains: string[], connections: string[] | undefined, episode: number): void {
    const existing = this.spatial.get(location)
    if (existing) {
      const mergedContains = new Set([...existing.contains, ...contains])
      existing.contains = Array.from(mergedContains)
      if (connections) {
        const mergedConn = new Set([...existing.connections, ...connections])
        existing.connections = Array.from(mergedConn)
      }
      existing.lastSeen = episode
      existing.visitCount++
    } else {
      this.spatial.set(location, {
        type: "spatial",
        location,
        contains,
        connections: connections ?? [],
        firstSeen: episode,
        lastSeen: episode,
        visitCount: 1,
      })
    }
  }

  private updateObject(objectType: string, location: string, episode: number): void {
    const existing = this.objects.get(objectType)
    if (existing) {
      existing.locationCounts[location] = (existing.locationCounts[location] ?? 0) + 1
      existing.lastSeenAt = location
      existing.lastSeenEpisode = episode
    } else {
      this.objects.set(objectType, {
        type: "object_location",
        objectType,
        locationCounts: { [location]: 1 },
        lastSeenAt: location,
        lastSeenEpisode: episode,
      })
    }
  }

  private updateState(entity: string, property: string, value: string, episode: number): void {
    const key = `${entity}:${property}`
    const existing = this.states.get(key)
    if (existing) {
      existing.observations.push({ value, episode })
      existing.defaultValue = this.computeMode(existing.observations.map((o) => o.value))
    } else {
      this.states.set(key, {
        type: "state",
        entity,
        property,
        defaultValue: value,
        observations: [{ value, episode }],
      })
    }
  }

  private updateTemporal(entity: string, pattern: string, confidence: number, episode: number): void {
    this.temporal.set(entity, {
      type: "temporal",
      entity,
      pattern,
      confidence,
      lastUpdated: episode,
    })
  }

  private extractTargetObjects(taskDescription: string): string[] {
    const targets: string[] = []
    const commonObjects = [
      "apple", "bread", "butter knife", "candle", "cd", "cellphone",
      "cloth", "credit card", "cup", "dishsponge", "egg", "fork",
      "glassbottle", "houseplant", "kettle", "keychain", "knife",
      "ladle", "lettuce", "mug", "newspaper", "pan", "peppershaker",
      "pencil", "pen", "pillow", "plate", "plunger", "pot",
      "potato", "remote control", "saltshaker", "soapbar", "soapbottle",
      "spatula", "spoon", "spray bottle", "statue", "teddy bear",
      "tissue box", "toilet paper", "tomato", "towel", "vase",
      "watch", "watering can", "wine bottle", "book", "bowl",
      "box", "laptop", "alarmclock", "baseballbat", "basketball",
      "boots", "desklamp", "floorlamp",
    ]

    const lower = taskDescription.toLowerCase()
    for (const obj of commonObjects) {
      if (lower.includes(obj)) {
        targets.push(obj)
      }
    }

    return targets
  }

  private findRelevantReceptacles(taskDescription: string): string[] {
    const relevant: string[] = []
    const lower = taskDescription.toLowerCase()

    if (lower.includes("heat") || lower.includes("microwave")) relevant.push("microwave 1")
    if (lower.includes("cool") || lower.includes("fridge")) relevant.push("fridge 1")
    if (lower.includes("clean") || lower.includes("sink")) relevant.push("sinkbasin 1")
    if (lower.includes("examine") || lower.includes("lamp") || lower.includes("light")) {
      relevant.push("desklamp 1", "floorlamp 1")
    }

    return relevant
  }

  private computeMode(values: string[]): string {
    const counts = new Map<string, number>()
    for (const v of values) {
      counts.set(v, (counts.get(v) ?? 0) + 1)
    }
    let maxCount = 0
    let mode = values[0] ?? ""
    for (const [val, count] of counts) {
      if (count > maxCount) {
        maxCount = count
        mode = val
      }
    }
    return mode
  }

  private enforceMaxEntries(): void {
    const totalEntries = this.spatial.size + this.objects.size + this.states.size + this.temporal.size
    if (totalEntries <= this.config.maxEntries) return

    const toRemove = totalEntries - this.config.maxEntries
    let removed = 0

    const objectsByAge = Array.from(this.objects.entries())
      .sort(([, a], [, b]) => a.lastSeenEpisode - b.lastSeenEpisode)
    for (const [key] of objectsByAge) {
      if (removed >= toRemove) break
      this.objects.delete(key)
      removed++
    }

    if (removed < toRemove) {
      const statesByAge = Array.from(this.states.entries())
        .sort(([, a], [, b]) => {
          const aLast = a.observations[a.observations.length - 1]?.episode ?? 0
          const bLast = b.observations[b.observations.length - 1]?.episode ?? 0
          return aLast - bLast
        })
      for (const [key] of statesByAge) {
        if (removed >= toRemove) break
        this.states.delete(key)
        removed++
      }
    }
  }
}
