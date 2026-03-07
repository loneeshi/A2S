---
id: alfworld/task_decomposition
description: How to decompose ALFWorld tasks into worker subtasks
whenToUse: When receiving any ALFWorld task as manager
steps:
  - Identify task type from the task description
  - Map to decomposition pattern
  - Assign each subtask to the right worker
tags:
  - alfworld
  - manager
  - decomposition
version: 0.1.0
---

## Task Type Identification

Read the task description and classify:

| Pattern in task description | Task type |
|---------------------------|-----------|
| "put ... in/on ..." (no clean/heat/cool) | pick_and_place |
| "clean" or "put a clean" | pick_clean_then_place |
| "hot" or "heat" or "put a hot" | pick_heat_then_place |
| "cool" or "cold" or "put a cool" | pick_cool_then_place |
| "examine" or "look at ... under" | examine |

## Context Passing Between Workers

After each worker completes, include critical state in the next delegation:
- **Current location**: "You are at microwave 1"
- **Holding status**: "You are holding apple 1" or "Your hands are empty"
- **Object state**: "apple 1 has been heated" or "mug 1 is clean"
- **Container states**: "fridge 1 is open"

## Failure Recovery

- If search_worker can't find the object: suggest alternative locations, or ask it to search more broadly
- If manipulation_worker fails to take: check if the container is open, check the exact object name
- If appliance_worker fails: check if the agent is holding the object and at the right location
