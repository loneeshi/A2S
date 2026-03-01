#!/usr/bin/env python3
"""
Test script for ALFWorld with Real Environment Integration

This script uses the actual ALFWorld environment to test the auto-expansion agents.

Requirements:
    conda activate skilltree_py311
    pip install alfworld

Usage:
    python scripts/test_alfworld_real.py --num_episodes 10 --split train
"""

import sys
import logging
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def try_import_alfworld():
    """Try to import ALFWorld and provide helpful error if not installed"""
    try:
        import alfworld
        import alfworld.agents.environment
        return True
    except ImportError as e:
        logger.error("❌ ALFWorld not installed!")
        logger.error("\nTo install ALFWorld:")
        logger.error("  conda activate skilltree_py311")
        logger.error("  pip install alfworld")
        logger.error("\nOr run the setup script:")
        logger.error("  bash scripts/setup_alfworld.sh")
        return False


def create_alfworld_config(split='train'):
    """Create ALFWorld configuration"""
    import alfworld.agents.environment

    config = {
        'env': {
            'type': 'AlfredTWEnv',
            'num_clients': 1,
        },
        'dataset': {
            'name': 'alfworld',
            'split': split,
        },
        'scene': {
            'type': 'train',
        },
        'task': {
            'name': 'train',
        },
    }

    return config


def test_real_alfworld(num_episodes=5, split='train'):
    """Test with real ALFWorld environment"""

    print_section("Phase 1: Initialize ALFWorld Environment")

    if not try_import_alfworld():
        return False

    try:
        import alfworld.agents.environment as environment

        logger.info("✅ ALFWorld imported successfully")

        # Create environment
        logger.info(f"Creating ALFWorld environment (split: {split})...")

        config = create_alfworld_config(split)

        env = environment.AlfredTWEnv(config, train_eval='train')
        env = env.init_env(batch_size=1)

        logger.info("✅ ALFWorld environment initialized")

    except Exception as e:
        logger.error(f"❌ Failed to initialize ALFWorld: {e}")
        logger.info("\nNote: ALFWorld may require data files to be downloaded separately.")
        logger.info("Please refer to ALFWorld documentation for setup instructions.")
        return False

    print_section("Phase 2: Generate Agent Tree")

    from core.generator import AgentTreeGenerator

    generator = AgentTreeGenerator()
    tree = generator.generate_initial_tree("alfworld")

    logger.info(f"✅ Generated {len(tree.workers)} workers and {len(tree.managers)} managers")

    print_section("Phase 3: Initialize Performance Monitor")

    from core.optimizer import PerformanceMonitor, DynamicExtensionEngine, TaskResult, TaskStatus

    monitor = PerformanceMonitor(window_size=50)
    extension_engine = DynamicExtensionEngine(
        performance_monitor=monitor,
        extension_threshold=0.7
    )

    logger.info("✅ Performance monitor initialized")

    print_section("Phase 4: Run Real ALFWorld Episodes")

    import numpy as np

    success_count = 0
    for episode_idx in range(num_episodes):
        try:
            logger.info(f"\n--- Episode {episode_idx + 1}/{num_episodes} ---")

            # Reset environment
            obs, info = env.reset()
            logger.info(f"Task: {info.get('extra.task_desc', 'Unknown')}")
            logger.info(f"Observation: {obs[0][:100]}...")

            # Select a worker agent (random for now)
            import random
            agent = random.choice(tree.workers)

            # Run episode
            done = False
            step = 0
            episode_success = False
            total_reward = 0

            while not done and step < 100:  # Max 100 steps
                # Get admissible actions
                if hasattr(env, 'get_admissible_actions'):
                    admissible_actions = env.get_admissible_actions()
                    # Pick random action (in real scenario, agent would decide)
                    action = random.choice(admissible_actions[0])
                else:
                    # Fallback: use a simple random action
                    action = "look around"

                # Step environment
                obs, reward, done, info = env.step([action])
                total_reward += reward[0]
                step += 1

                if done:
                    episode_success = reward[0] > 0
                    break

            logger.info(f"Steps: {step}, Reward: {total_reward:.2f}, Success: {episode_success}")

            # Record result
            result = TaskResult(
                task_id=f"alfworld_real_{episode_idx}",
                task_type="alfworld_task",
                status=TaskStatus.SUCCESS if episode_success else TaskStatus.FAILURE,
                agent_used=agent.name,
                duration=step * 0.1,  # Approximate
            )
            monitor.record_task_result(result)

            if episode_success:
                success_count += 1

        except Exception as e:
            logger.error(f"Episode {episode_idx + 1} failed: {e}")
            import traceback
            traceback.print_exc()

            # Record failure
            result = TaskResult(
                task_id=f"alfworld_real_{episode_idx}",
                task_type="alfworld_task",
                status=TaskStatus.FAILURE,
                agent_used=agent.name if agent else "Unknown",
                duration=0,
                error_message=str(e)
            )
            monitor.record_task_result(result)

    logger.info(f"\n✅ Completed {num_episodes} real episodes")
    logger.info(f"Success rate: {success_count}/{num_episodes} ({success_count/num_episodes:.1%})")

    print_section("Phase 5: Performance Analysis")

    summary = monitor.get_summary()
    logger.info(f"Overall Performance:")
    logger.info(f"   Total tasks: {summary['total_tasks']}")
    logger.info(f"   Overall success rate: {summary['overall_success_rate']:.2%}")

    print_section("Phase 6: Dynamic Extension (if needed)")

    if monitor.should_trigger_extension(threshold=0.7):
        logger.info("⚠️  Performance threshold breached - applying extensions...")
        extended_tree = extension_engine.monitor_and_extend(tree)
        logger.info(f"✅ Tree extended: {len(tree.workers)} → {len(extended_tree.workers)} workers")
    else:
        logger.info("✅ Performance satisfactory - no extension needed")

    print_section("Summary")

    logger.info("🎉 Real ALFWorld test completed!")
    logger.info(f"\nResults:")
    logger.info(f"   Episodes run: {num_episodes}")
    logger.info(f"   Success rate: {success_count/num_episodes:.1%}")
    logger.info(f"   Final workers: {len(tree.workers)}")
    logger.info(f"   Final managers: {len(tree.managers)}")

    return True


def print_section(title: str):
    """Print a formatted section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test auto-expansion agents with real ALFWorld")
    parser.add_argument(
        "--num_episodes",
        type=int,
        default=5,
        help="Number of episodes to run (default: 5)"
    )
    parser.add_argument(
        "--split",
        type=str,
        default="train",
        choices=["train", "valid_in_distribution", "test_in_distribution"],
        help="Data split to use (default: train)"
    )

    args = parser.parse_args()

    try:
        success = test_real_alfworld(
            num_episodes=args.num_episodes,
            split=args.split
        )
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
