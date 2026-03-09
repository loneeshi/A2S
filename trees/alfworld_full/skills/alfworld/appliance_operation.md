---
description: How to operate ALFWorld appliances — microwave, fridge, sinkbasin, desklamp
type: reference
whenToUse: When asked to heat, cool, clean an object or toggle a device
allowedTools:
  - env.goto
  - env.open
  - env.close
  - env.heat
  - env.cool
  - env.clean
  - env.use
steps:
  - Navigate to the appliance
  - Open if needed (microwave, fridge)
  - Perform the operation
  - Report result
tags:
  - alfworld
  - appliance
version: 0.2.0
---

## Appliance Reference

| Operation | Appliance | Need to open? | Command |
|-----------|-----------|--------------|---------|
| Heat | microwave 1 | YES | `heat [object] with microwave 1` |
| Cool | fridge 1 | YES | `cool [object] with fridge 1` |
| Clean | sinkbasin 1 | NO | `clean [object] with sinkbasin 1` |
| Examine/Toggle | desklamp 1 | NO | `use desklamp 1` |

## Prerequisites

- You MUST be holding the object before heat/cool/clean
- You MUST be at the appliance location (`goto` first)
- Microwave and fridge must be `open`ed before use

## Step-by-Step Patterns

### Heat an object
1. `goto microwave 1`
2. `open microwave 1`
3. `heat [object] with microwave 1`
4. Object is now heated — report to manager

### Cool an object
1. `goto fridge 1`
2. `open fridge 1`
3. `cool [object] with fridge 1`
4. Object is now cooled — report to manager

### Clean an object
1. `goto sinkbasin 1`
2. `clean [object] with sinkbasin 1`
3. Object is now clean — report to manager

## Failure Patterns

- "Nothing happens" after heat/cool/clean → you're not holding the object, or not at the appliance
- "Nothing happens" after use → the device doesn't exist at this location, try a different number
- If the microwave already has something in it, you may need to take it out first
