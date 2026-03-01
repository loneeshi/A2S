#!/usr/bin/env python3
"""
Explore get_environment function signature and parameters
"""

import sys
import inspect

print("=" * 80)
print("  Exploring get_environment Function")
print("=" * 80)
print()

try:
    import alfworld.agents.environment as environment

    # Get the function
    func = environment.get_environment

    print("✅ Found get_environment function")
    print()

    # Get signature
    try:
        sig = inspect.signature(func)
        print("Function signature:")
        print(f"  get_environment{sig}")
        print()
    except:
        print("Could not get signature (might be C extension)")
        print()

    # Get docstring
    if func.__doc__:
        print("Documentation:")
        print(func.__doc__)
        print()

    # Try to find what environment types are supported
    print("Trying to find valid environment types...")
    print()

    # Common environment type strings to try
    env_types = [
        'AlfredTWEnv',
        'alfred',
        'tw',
        'text-world',
        'AlfredWorld',
        'horizon',
    ]

    for env_type in env_types:
        try:
            print(f"  Trying '{env_type}'...")
            env = environment.get_environment(env_type)
            print(f"  ✅ '{env_type}' works!")
            print(f"     Environment type: {type(env)}")
            break
        except NotImplementedError as e:
            print(f"  ❌ '{env_type}' not implemented: {e}")
        except Exception as e:
            print(f"  ❌ '{env_type}' failed: {e}")

    print()
    print("=" * 80)
    print("  Summary")
    print("=" * 80)
    print()
    print("The get_environment function expects an environment TYPE string,")
    print("not a config dict or split name.")
    print()
    print("Please check ALFWorld documentation for valid environment types.")

except ImportError as e:
    print(f"❌ Failed to import alfworld: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
