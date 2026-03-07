---
description: Best practices for picking up and placing objects in ALFWorld
type: workflow
whenToUse: When handling take/put operations
allowedTools:
  - env.goto
  - env.take
  - env.put
  - env.open
  - env.close
steps:
  - Navigate to object location
  - Open container if needed
  - Take with exact name
  - Navigate to destination
  - Put with exact name
tags:
  - alfworld
  - manipulation
version: 0.2.0
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

## Recovery Strategies

If take fails:
1. Verify you did `goto [location]` first
2. Check if container needs `open`
3. Verify exact object name matches observation text (including number suffix)
4. If holding another object, `put` it down first

If put fails:
1. Verify you did `goto [destination]` first
2. Verify you are still holding the object
3. Check "in" vs "on" — containers use "in", surfaces use "on"
