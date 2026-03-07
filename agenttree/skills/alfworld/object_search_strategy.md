---
description: Efficient search strategies for finding objects in ALFWorld rooms
type: reference
whenToUse: When assigned to find an object in the environment
allowedTools:
  - env.goto
  - env.look
  - env.open
  - env.close
  - env.examine
steps:
  - Identify object category
  - Search high-probability locations first
  - Open closed containers
  - Track visited locations
tags:
  - alfworld
  - search
  - strategy
version: 0.2.0
---

## Search Priority by Object Category

**Food/kitchen items** → countertop, fridge, diningtable, cabinet, shelf, microwave, stoveburner
**Bathroom items** → countertop, sinkbasin, bathtubbasin, cabinet, shelf, toilet
**Small personal items** → desk, sidetable, drawer, shelf, dresser, coffeetable
**Lighting items** → sidetable, desk, shelf, dresser

## Search Efficiency Rules

1. ALWAYS read the observation after `goto` — objects are listed in the text
2. Containers like drawer, cabinet, fridge, safe are CLOSED by default — you MUST `open` them to see contents
3. If `goto` returns "Nothing happens" → that location doesn't exist, move on immediately
4. Number your attempts mentally — after checking 8+ locations with no result, reconsider whether you're looking for the right object name
5. Some objects appear with different IDs: "apple 1", "apple 2" — any matching object is fine unless the task specifies a number

## Container Search Pattern

For closed containers, always:
1. `goto` the container → read what's visible on/near it
2. `open` the container → read what's inside
3. If empty, `close` the container and move on

## Failure Recovery

- "Nothing happens" → location doesn't exist, skip
- Object not found after 10 locations → re-read task, check object name spelling
- All high-priority locations checked → try shelf, garbagecan, toilet, bathtubbasin
