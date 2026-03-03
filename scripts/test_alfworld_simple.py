#!/usr/bin/env python3
"""
Simple ALFWorld Test Script (Borrowed from Agent_to_Skills)

This script uses the proven AlfworldAdapter implementation from Agent_to_Skills
to test ALFWorld environment without initialization delays.
"""

import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Add Agent_to_Skills to path for importing AlfworldAdapter
agent_to_skills_path = Path("/Users/dp/Agent_research/design/Agent_to_Skills")
sys.path.insert(0, str(agent_to_skills_path))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_alfworld_simple(num_episodes=3):
    """Test ALFWorld with simple, proven implementation"""

    print("\n" + "=" * 80)
    print("  ALFWorld Simple Test (Using Agent_to_Skills Adapter)")
    print("=" * 80 + "\n")

    try:
        # Import the proven adapter
        from src.adapters.alfworld_adapter import AlfworldAdapter
        logger.info("✅ Imported AlfworldAdapter from Agent_to_Skills")

        # Initialize adapter (using default config)
        logger.info("Initializing ALFWorld adapter...")
        adapter = AlfworldAdapter(
            config_path=None,  # Use default config
            train_eval='train'  # Use training split
        )
        logger.info("✅ Adapter initialized")

        # Run episodes
        success_count = 0
        import time

        for episode_idx in range(num_episodes):
            print("\n" + "#" * 60)
            print(f"# Episode {episode_idx + 1}/{num_episodes}")
            print("#" * 60 + "\n")

            # Reset environment
            logger.info("→ Resetting environment...")
            reset_start = time.time()
            task_desc = adapter.reset()
            reset_time = time.time() - reset_start
            logger.info(f"✅ Reset completed in {reset_time:.2f}s")

            if reset_time < 5:
                logger.info(f"   🚀 Excellent speed! ({reset_time:.2f}s)")
            elif reset_time < 10:
                logger.info(f"   ✓ Good performance ({reset_time:.2f}s)")
            else:
                logger.warning(f"   ⚠️  Slow reset ({reset_time:.2f}s > 10s)")

            logger.info(f"Task: {task_desc[:200]}...")

            # Simulate a few random actions (just to test stepping)
            step = 0
            max_steps = 5  # Just test a few steps

            logger.info(f"Running {max_steps} test steps...")

            while step < max_steps:
                # Get admissible commands from last info
                if hasattr(adapter, 'infos') and adapter.infos:
                    commands = adapter._extract_admissible_commands(adapter.infos)
                    if commands:
                        action = commands[0]  # Take first available action
                    else:
                        action = "look around"
                else:
                    action = "look around"

                logger.info(f"  Step {step + 1}: {action[:50]}...")

                # Execute action
                response = adapter.step(action)

                logger.info(f"    Done: {response.metadata.get('done', False)}, "
                          f"Reward: {response.metadata.get('reward', 0.0):.2f}")

                step += 1

                if response.metadata.get('done', False):
                    if response.metadata.get('won', False):
                        success_count += 1
                        logger.info("  ✅ Episode completed successfully!")
                    else:
                        logger.info("  ❌ Episode failed")
                    break

            if step >= max_steps:
                logger.info(f"  ⏹️  Reached test step limit ({max_steps})")

        # Summary
        print("\n" + "=" * 80)
        print("  Test Summary")
        print("=" * 80 + "\n")
        logger.info(f"Episodes completed: {num_episodes}")
        logger.info(f"Success rate: {success_count}/{num_episodes} ({success_count/num_episodes:.1%})")

        return True

    except ImportError as e:
        logger.error(f"❌ Failed to import: {e}")
        logger.info("\nMake sure Agent_to_Skills is available at:")
        logger.info("  /Users/dp/Agent_research/design/Agent_to_Skills")
        return False

    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Simple ALFWorld test")
    parser.add_argument(
        "--num_episodes",
        type=int,
        default=3,
        help="Number of episodes to test (default: 3)"
    )

    args = parser.parse_args()

    try:
        success = test_alfworld_simple(num_episodes=args.num_episodes)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n\nTest interrupted by user")
        sys.exit(1)
