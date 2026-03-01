#!/usr/bin/env python3
"""
Test ALFWorld with complete configuration
"""

import sys
import os

print("=" * 80)
print("  ALFWorld Complete Configuration Test")
print("=" * 80)
print()

try:
    import alfworld.agents.environment as environment
    from alfworld.agents.environment.alfred_tw_env import TASK_TYPES

    print("Available task types:")
    for tt_id, tt_name in TASK_TYPES.items():
        print(f"  {tt_id}: {tt_name}")
    print()

    # Find default data path
    default_data_path = os.path.expanduser("~/.alfworld/alfred/data/json_2.1.1/train")
    print(f"Looking for data in: {default_data_path}")
    print(f"Exists: {os.path.exists(default_data_path)}")
    print()

    # Create minimal config
    config = {
        'env': {
            'type': 'AlfredTWEnv',
            'goal_desc_human_anns_prob': 0,  # No human annotations
            'task_types': [1],  # Pick and Place task
        },
        'dataset': {
            'data_path': '~/.alfworld/alfred/data/json_2.1.1/train',
            'eval_id_data_path': '~/.alfworld/alfred/data/json_2.1.1/valid_in_distribution',
            'eval_ood_data_path': '~/.alfworld/alfred/data/json_2.1.1/valid_out_of_distribution',
        }
    }

    print("Creating environment with config:")
    print(f"  {config}")
    print()

    env_class = environment.get_environment('AlfredTWEnv')

    print("Initializing environment...")
    env = env_class(config, train_eval='train')
    print(f"✅ Environment created!")
    print()

    print("Initializing with init_env...")
    env = env.init_env(batch_size=1)
    print(f"✅ Environment initialized!")
    print()

    print("Trying reset...")
    obs = env.reset()
    print(f"✅ Reset successful!")
    print(f"  Observation type: {type(obs)}")
    print(f"  Observation: {str(obs)[:200]}...")
    print()

    print("=" * 80)
    print("SUCCESS! ALFWorld environment is working!")
    print("=" * 80)

except FileNotFoundError as e:
    print(f"❌ ALFWorld data not found: {e}")
    print()
    print("You need to download ALFWorld data files.")
    print("Please refer to: https://github.com/alfworld/alfworld#download-alfred-data")
    print()
    sys.exit(1)

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
