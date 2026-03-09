/**
 * Environment Memory types.
 *
 * Structured knowledge about the physical environment, built incrementally
 * from agent observations across episodes. Supports:
 *   - Spatial structure (what locations contain)
 *   - Object distributions (where objects are typically found)
 *   - Entity state (default/observed states of doors, containers, etc.)
 *   - Temporal patterns (schedules, hours — stulife only)
 *
 * The EnvironmentParser interface is pluggable: ALFWorld uses regex-based
 * parsing, stulife may use NER or LLM-assisted extraction.
 */

export interface EnvironmentMemoryConfig {
  enabled: boolean
  maxEntries: number
  consolidateEvery: number
  decayFactor: number
  backend: "local" | "semantic-router"
  srUrl?: string
}

export const DEFAULT_ENV_MEMORY_CONFIG: EnvironmentMemoryConfig = {
  enabled: false,
  maxEntries: 500,
  consolidateEvery: 10,
  decayFactor: 0.95,
  backend: "local",
}

export interface SpatialEntry {
  type: "spatial"
  location: string
  contains: string[]
  connections: string[]
  firstSeen: number
  lastSeen: number
  visitCount: number
}

export interface ObjectEntry {
  type: "object_location"
  objectType: string
  locationCounts: Record<string, number>
  lastSeenAt: string
  lastSeenEpisode: number
}

export interface StateEntry {
  type: "state"
  entity: string
  property: string
  defaultValue: string
  observations: Array<{ value: string; episode: number }>
}

export interface TemporalEntry {
  type: "temporal"
  entity: string
  pattern: string
  confidence: number
  lastUpdated: number
}

export type EnvironmentEntry = SpatialEntry | ObjectEntry | StateEntry | TemporalEntry

export interface SpatialUpdate {
  location: string
  contains: string[]
  connections?: string[]
}

export interface ObjectUpdate {
  objectType: string
  instanceId: string
  location: string
}

export interface StateUpdate {
  entity: string
  property: string
  value: string
}

export interface TemporalUpdate {
  entity: string
  pattern: string
  confidence?: number
}

export interface EnvironmentParser {
  parseLocation(action: string, observation: string): SpatialUpdate | null
  parseObjects(observation: string): ObjectUpdate[]
  parseState(action: string, observation: string): StateUpdate | null
  parseTemporal?(observation: string): TemporalUpdate | null
}

export interface EnvironmentMemorySnapshot {
  version: 1
  spatial: Record<string, SpatialEntry>
  objects: Record<string, ObjectEntry>
  states: Record<string, StateEntry>
  temporal: Record<string, TemporalEntry>
  totalObservations: number
  lastEpisode: number
}
