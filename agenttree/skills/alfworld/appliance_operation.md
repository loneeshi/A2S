---
id: alfworld/appliance_operation
description: How to operate ALFWorld appliances — microwave, fridge, sinkbasin, desklamp
whenToUse: When asked to heat, cool, clean an object or toggle a device
steps:
  - Navigate to the appliance
  - Open if needed (microwave, fridge)
  - Perform the operation
  - Report result
tags:
  - alfworld
  - appliance
version: 0.1.0
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

## Failure Patterns

- "Nothing happens" after heat/cool/clean → you're not holding the object, or not at the appliance
- "Nothing happens" after use → the device doesn't exist at this location, try a different number
- If the microwave already has something in it, you may need to take it out first
