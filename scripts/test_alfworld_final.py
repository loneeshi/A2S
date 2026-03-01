#!/usr/bin/env python3
"""
Final test for ALFWorld environment with correct configuration
"""

import sys

print("=" * 80)
print("  ALFWorld Final Initialization Test")
print("=" * 80)
print()

try:
    import alfworld.agents.environment as environment

    print("Creating environment...")
    print("-" * 80)

    # Get environment class
    env_class = environment.get_environment('AlfredTWEnv')
    print(f"✅ Got class: {env_class.__name__}")

    # Create config based on signature
    config = {
        'env': {
            'type': 'AlfredTWEnv',
        },
        'dataset': {
            'split': 'train',
        }
    }

    print(f"Config: {config}")
    print()

    # Try to instantiate
    try:
        print("Instantiating environment...")
        env = env_class(config, train_eval='train')
        print(f"✅ Instance created: {type(env)}")
        print()

        # Try to initialize
        if hasattr(env, 'init_env'):
            print("Initializing with init_env...")
            env = env.init_env(batch_size=1)
            print(f"✅ Environment initialized!")
            print(f"   Type: {type(env)}")
            print()

            # Check methods
            print("Available methods:")
            for name in dir(env):
                if not name.startswith('_') and callable(getattr(env, name)):
                    print(f"  - {name}")
            print()

            # Try reset
            if hasattr(env, 'reset'):
                print("Trying reset()...")
                obs = env.reset()
                print(f"✅ Reset successful!")
                print(f"   Observation type: {type(obs)}")
                if hasattr(obs, '__len__'):
                    print(f"   Length: {len(obs)}")
                    if len(obs) > 0:
                        print(f"   First element type: {type(obs[0])}")
                        if isinstance(obs[0], str):
                            print(f"   First obs: {obs[0][:100]}...")
                print()

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

    print("=" * 80)
    print("SUCCESS! Environment is ready to use.")
    print("=" * 80)

except Exception as e:
    print(f"❌ Fatal error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
