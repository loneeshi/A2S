---
id: alfworld/object_handling
description: Best practices for picking up and placing objects in ALFWorld
whenToUse: When handling take/put operations
steps:
  - Navigate to object location
  - Open container if needed
  - Take with exact name
  - Navigate to destination
  - Put with exact name
tags:
  - alfworld
  - manipulation
version: 0.1.0
---

## Take Operation

- Format: `take [exact object name] from [exact location name]`
- Example: `take apple 1 from fridge 1`
- You MUST be at the location (after `goto`)
- Container MUST be open (use `open` first for fridge, cabinet, drawer, etc.)
- You can hold only ONE object

## Put Operation

- Format: `put [exact object name] in/on [exact destination]`
- Use "in" for containers: `put apple 1 in fridge 1`
- Use "on" for surfaces: `put apple 1 on countertop 1`
- You MUST be at the destination (after `goto`)

## Common Errors

- Wrong object number: observation says "apple 1" but you try "apple" → fails
- Not at location: trying to take without first doing `goto` → "Nothing happens"
- Container closed: trying to take from closed fridge → fails. Always `open` first.
- Already holding something: you must put down current object before picking up another
