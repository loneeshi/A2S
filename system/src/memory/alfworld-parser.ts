/**
 * ALFWorld Environment Parser — extracts structured knowledge from ALFWorld
 * environment observations using regex patterns.
 *
 * ALFWorld observation formats:
 *   "On the countertop 1, you see a bread 1, a knife 1, and a apple 2."
 *   "You open the fridge 1. The fridge 1 is open. In it, you see a apple 1."
 *   "You arrive at loc 5. The cabinet 3 is closed."
 *   "You pick up the apple 1 from the countertop 1."
 *   "Nothing happens."
 */

import type {
  EnvironmentParser,
  SpatialUpdate,
  ObjectUpdate,
  StateUpdate,
} from "./environment-types"

const RECEPTACLES = new Set([
  "countertop", "cabinet", "drawer", "shelf", "fridge", "microwave",
  "sinkbasin", "stoveburner", "coffeemachine", "toaster", "garbagecan",
  "sidetable", "dresser", "desk", "bed", "bathtub", "toilet",
  "safe", "ottoman", "armchair", "sofa", "tvstand", "diningtable",
  "laundryhamper", "handtowelholder", "towelholder",
])

function normalizeObjectType(instance: string): string {
  return instance.replace(/\s*\d+$/, "").trim().toLowerCase()
}

function isReceptacle(name: string): boolean {
  const base = normalizeObjectType(name)
  return RECEPTACLES.has(base)
}

function parseObjectList(text: string): string[] {
  const objects: string[] = []

  const listMatch = text.match(/you see\s+(.+?)\.?\s*$/i)
  if (!listMatch) return objects

  const listText = listMatch[1]
  const items = listText.split(/,\s*(?:and\s+)?|(?:^|\s)and\s+/)
  for (const item of items) {
    const clean = item.replace(/^a\s+|^an\s+/i, "").trim()
    if (clean.length > 0 && clean !== "nothing") {
      objects.push(clean)
    }
  }

  return objects
}

export class ALFWorldParser implements EnvironmentParser {
  parseLocation(action: string, observation: string): SpatialUpdate | null {
    const gotoMatch = action.match(/^(?:go\s*to|goto)\s+(.+)/i)
    if (!gotoMatch) return null

    const location = gotoMatch[1].trim()
    const objects = parseObjectList(observation)
    const contains = objects.filter((o) => !isReceptacle(o))

    return {
      location,
      contains,
    }
  }

  parseObjects(observation: string): ObjectUpdate[] {
    const updates: ObjectUpdate[] = []

    const locationPatterns = [
      /on (?:the )?(.+?),\s+you see\s+(.+?)\.?\s*$/i,
      /in it,\s+you see\s+(.+?)\.?\s*$/i,
      /the (.+?) is open\.\s+in it,\s+you see\s+(.+?)\.?\s*$/i,
    ]

    let location: string | null = null
    let objectListText: string | null = null

    for (const pat of locationPatterns) {
      const m = observation.match(pat)
      if (m) {
        if (m.length === 3) {
          location = m[1].trim()
          objectListText = m[2].trim()
        } else if (m.length === 2) {
          objectListText = m[1].trim()
        }
        break
      }
    }

    if (!location) {
      const locMatch = observation.match(/(?:on|in|at) (?:the )?(.+?),/i)
      if (locMatch) location = locMatch[1].trim()
    }

    if (location && objectListText) {
      const items = objectListText.split(/,\s*(?:and\s+)?|(?:^|\s)and\s+/)
      for (const item of items) {
        const clean = item.replace(/^a\s+|^an\s+/i, "").trim()
        if (clean.length > 0 && clean !== "nothing") {
          updates.push({
            instanceId: clean,
            objectType: normalizeObjectType(clean),
            location,
          })
        }
      }
    }

    const pickMatch = observation.match(/you pick up the (.+?) from the (.+?)\./i)
    if (pickMatch) {
      updates.push({
        instanceId: pickMatch[1].trim(),
        objectType: normalizeObjectType(pickMatch[1]),
        location: pickMatch[2].trim(),
      })
    }

    return updates
  }

  parseState(action: string, observation: string): StateUpdate | null {
    const openMatch = action.match(/^open\s+(.+)/i)
    if (openMatch && !observation.toLowerCase().includes("nothing happens")) {
      return {
        entity: openMatch[1].trim(),
        property: "open_closed",
        value: "open",
      }
    }

    const closeMatch = action.match(/^close\s+(.+)/i)
    if (closeMatch && !observation.toLowerCase().includes("nothing happens")) {
      return {
        entity: closeMatch[1].trim(),
        property: "open_closed",
        value: "closed",
      }
    }

    const closedMatch = observation.match(/the (.+?) is closed/i)
    if (closedMatch) {
      return {
        entity: closedMatch[1].trim(),
        property: "open_closed",
        value: "closed",
      }
    }

    const toggleMatch = action.match(/^(?:toggle|turn on|turn off)\s+(.+)/i)
    if (toggleMatch && !observation.toLowerCase().includes("nothing happens")) {
      const isOn = observation.toLowerCase().includes("turn on") ||
                   observation.toLowerCase().includes("appears to be on")
      return {
        entity: toggleMatch[1].trim(),
        property: "on_off",
        value: isOn ? "on" : "off",
      }
    }

    return null
  }
}
