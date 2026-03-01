#!/usr/bin/env python3
"""
Test ALFWorld environment initialization step by step
"""

import sys

print("=" * 80)
print("  ALFWorld Environment Initialization Test")
print("=" * 80)
print()

try:
    import alfworld.agents.environment as environment

    print("Step 1: Get environment class")
    print("-" * 80)
    env_class = environment.get_environment('AlfredTWEnv')
    print(f"✅ Got environment class: {env_class}")
    print(f"   Type: {type(env_class)}")
    print()

    print("Step 2: Explore environment class")
    print("-" * 80)
    print(f"Class name: {env_class.__name__}")
    print(f"Module: {env_class.__module__}")
    print()

    # Check if it has __init__ signature
    import inspect
    try:
        sig = inspect.signature(env_class.__init__)
        print(f"__init__ signature: {sig}")
        print()
    except:
        print("Could not get __init__ signature")
        print()

    print("Step 3: Try to instantiate")
    print("-" * 80)

    # Try different initialization approaches
    approaches = [
        ("No arguments", lambda: env_class()),
        ("With config dict", lambda: env_class({'split': 'train'})),
        ("With split='train'", lambda: env_class(split='train')),
        ("With train_eval='train'", lambda: env_class(train_eval='train')),
    ]

    for desc, approach in approaches:
        try:
            print(f"  Trying: {desc}...")
            env = approach()
            print(f"  ✅ Success! Type: {type(env)}")

            # Try to initialize
            if hasattr(env, 'init_env'):
                print(f"  Has init_env method, trying to initialize...")
                try:
                    env = env.init_env(batch_size=1)
                    print(f"  ✅ Environment initialized!")
                    print(f"     Type after init: {type(env)}")
                    print()
                    break
                except Exception as e:
                    print(f"  init_env failed: {e}")
            else:
                print(f"  No init_env method")
                print()

            break
        except Exception as e:
            print(f"  ❌ Failed: {e}")
            print()

    print("=" * 80)

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
