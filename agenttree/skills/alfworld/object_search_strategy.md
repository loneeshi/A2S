---
id: alfworld/object_search_strategy
description: Efficient search strategies for finding objects in ALFWorld rooms
whenToUse: When assigned to find an object in the environment
steps:
  - Identify object category
  - Search high-probability locations first
  - Open closed containers
  - Track visited locations
tags:
  - alfworld
  - search
  - strategy
version: 0.1.0
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
