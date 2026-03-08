---
id: campus-navigation-basic
description: Navigating between campus buildings and facilities
whenToUse: When an agent needs to find or travel to campus buildings and locations
tags:
  - navigation
  - campus
  - geography
  - map
---

## Campus Navigation

### Finding Buildings
1. Use `map.find_building_id` with the building name (e.g., "library", "science hall")
2. The returned ID is used by other navigation tools
3. If unsure of the exact name, try common variations

### Planning a Route
1. Use `geography.get_current_location` to confirm where you are
2. Use `map.find_optimal_path` with `from_location` and `to_location` to get directions
3. The optimal path accounts for campus layout and walking distances

### Walking to a Destination
1. Use `geography.walk_to` with the destination name or ID
2. After arriving, confirm location with `geography.get_current_location`
3. You must physically walk to a building before interacting with facilities inside it

### Tips
- Always look up the building ID before walking — ensures the destination exists
- Check your current location if you are unsure where you are
- Use optimal path for multi-stop trips — walking order matters for efficiency
- Some tasks require being at a specific building (e.g., reserving a room at the library)
