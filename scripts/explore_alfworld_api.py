#!/usr/bin/env python3
"""
Explore ALFWorld API to find correct initialization methods

This script helps identify the correct classes and methods to use
for interacting with ALFWorld environment.
"""

import sys

print("=" * 80)
print("  ALFWorld API Explorer")
print("=" * 80)
print()

# Step 1: Import ALFWorld
try:
    import alfworld
    print(f"✅ ALFWorld imported")
    print(f"   Version: {getattr(alfworld, '__version__', 'Unknown')}")
    print()
except ImportError as e:
    print(f"❌ Failed to import ALFWorld: {e}")
    sys.exit(1)

# Step 2: Explore alfworld.agents.environment
try:
    import alfworld.agents.environment as env_module
    print("✅ alfworld.agents.environment module loaded")
    print()
    print("Available classes and functions:")
    for name in dir(env_module):
        if not name.startswith('_'):
            obj = getattr(env_module, name)
            obj_type = type(obj).__name__
            print(f"   - {name}: {obj_type}")
    print()

except ImportError as e:
    print(f"❌ Failed to import alfworld.agents.environment: {e}")
    print()
    print("Trying alternative import paths...")
    print()

    # Try importing just alfworld.agents
    try:
        import alfworld.agents
        print("✅ alfworld.agents imported")
        print("Available:")
        for name in dir(alfworld.agents):
            if not name.startswith('_'):
                print(f"   - {name}")
        print()
    except:
        pass

# Step 3: Check for common environment classes
print("Checking for common environment classes...")
print()

env_classes = [
    'AlfredTWEnv',
    'AlfredEnv',
    'AlfredWorldEnv',
    'ALFWorldEnv',
    'TWEnv',
]

for cls_name in env_classes:
    try:
        if hasattr(env_module, cls_name):
            cls = getattr(env_module, cls_name)
            print(f"✅ Found: {cls_name}")
            print(f"   Type: {type(cls)}")
            print(f"   Doc: {cls.__doc__[:100] if cls.__doc__ else 'No docstring'}")
            print()
    except:
        pass

# Step 4: Check alfworld.agents.modules
try:
    import alfworld.agents.modules as modules
    print("✅ alfworld.agents.modules available")
    print("Contents:")
    for name in dir(modules):
        if not name.startswith('_'):
            print(f"   - {name}")
    print()
except:
    pass

# Step 5: Look for configuration examples
print("=" * 80)
print("  Suggested Next Steps")
print("=" * 80)
print()
print("1. Check ALFWorld GitHub for examples:")
print("   https://github.com/alfworld/alfworld")
print()
print("2. Check ALFWorld documentation:")
print("   https://alfworld.github.io/")
print()
print("3. Look at example scripts in ALFWorld package:")
print("   import alfworld")
print("   print(alfworld.__file__)")
print()
