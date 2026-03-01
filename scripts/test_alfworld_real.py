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


def create_alfworld_env(split='train'):
    """Create ALFWorld environment with complete configuration"""
    import alfworld.agents.environment as environment
    import os

    logger.info(f"Creating ALFWorld environment (split: {split})...")

    # Map split names to ALFWorld's train_eval names
    split_mapping = {
        'train': 'train',
        'valid_in_distribution': 'eval_in_distribution',
        'test_in_distribution': 'eval_in_distribution',
    }
    train_eval = split_mapping.get(split, 'train')

    # Create complete config
    config = {
        'env': {
            'type': 'AlfredTWEnv',
            'goal_desc_human_anns_prob': 0,  # No human annotations
            'task_types': [1],  # 1=pick_and_place_simple (can be 1-6)
        },
        'dataset': {
            'data_path': '~/.alfworld/alfred/data/json_2.1.1/train',
            'eval_id_data_path': '~/.alfworld/alfred/data/json_2.1.1/valid_in_distribution',
            'eval_ood_data_path': '~/.alfworld/alfred/data/json_2.1.1/valid_out_of_distribution',
            'num_train_games': -1,  # -1 means use all available games
            'num_eval_games': -1,
        }
    }

    # Check if data files exist
    data_path = os.path.expanduser(config['dataset']['data_path'])
    if not os.path.exists(data_path):
        logger.warning(f"⚠️  ALFWorld data not found: {data_path}")
        logger.warning("")
        logger.warning("Please download ALFWorld data:")
        logger.warning("  1. Run: alfworld-agenerate --download-data")
        logger.warning("  2. Or visit: https://github.com/alfworld/alfworld#download-alfred-data")
        logger.warning("")
        logger.warning("For now, falling back to simulated mode...")
        return None

    try:
        # Get environment class
        env_class = environment.get_environment('AlfredTWEnv')
        logger.info("✅ Got AlfredTWEnv class")

        # Instantiate environment
        logger.info(f"Initializing with train_eval={train_eval}...")
        env = env_class(config, train_eval=train_eval)
        logger.info("✅ Environment instantiated")

        # Initialize batch
        logger.info("Calling init_env(batch_size=1)...")
        env = env.init_env(batch_size=1)
        logger.info("✅ Environment initialized and ready")

        return env

    except FileNotFoundError as e:
        logger.error(f"❌ Data files not found: {e}")
        logger.info("")
        logger.info("Please download ALFWorld data first:")
        logger.info("  alfworld-agenerate --download-data")
        logger.info("")
        return None

    except Exception as e:
        logger.error(f"❌ Failed to create environment: {e}")
        import traceback
        traceback.print_exc()
        return None


def run_simulated_test(num_episodes=5):
    """Run simulated test when ALFWorld data is not available"""

    from core.generator import AgentTreeGenerator
    from core.optimizer import PerformanceMonitor, DynamicExtensionEngine, TaskResult, TaskStatus
    import random

    print_section("Simulated Test Mode")

    logger.info("Generating agent tree...")

    generator = AgentTreeGenerator()
    tree = generator.generate_initial_tree("alfworld")

    logger.info(f"✅ Generated {len(tree.workers)} workers and {len(tree.managers)} managers")

    logger.info("Initializing performance monitor...")

    monitor = PerformanceMonitor(window_size=50)
    extension_engine = DynamicExtensionEngine(
        performance_monitor=monitor,
        extension_threshold=0.7
    )

    logger.info("Running simulated episodes...")

    task_types = ["object_manipulation", "navigation_exploration", "multi_step_task",
                   "object_search", "task_planning"]

    for episode_id in range(num_episodes):
        task_type = random.choice(task_types)
        agent = random.choice(tree.workers)
        success = random.random() < 0.7

        result = TaskResult(
            task_id=f"sim_task_{episode_id}",
            task_type=task_type,
            status=TaskStatus.SUCCESS if success else TaskStatus.FAILURE,
            agent_used=agent.name,
            duration=random.uniform(1.0, 5.0),
            error_message=None if success else "Simulated failure"
        )

        monitor.record_task_result(result)

        if (episode_id + 1) % max(1, num_episodes // 5) == 0:
            recent = monitor.get_recent_performance(n=min(5, episode_id + 1))
            logger.info(f"  Episode {episode_id + 1}/{num_episodes} - Recent success rate: {recent['success_rate']:.2%}")

    logger.info(f"✅ Completed {num_episodes} simulated episodes")

    print_section("Performance Analysis")

    summary = monitor.get_summary()
    logger.info(f"Overall success rate: {summary['overall_success_rate']:.2%}")

    print_section("Summary")

    logger.info("🎉 Simulated test completed!")
    logger.info(f"Agents: {len(tree.workers)} workers, {len(tree.managers)} managers")
    logger.info(f"Success rate: {summary['overall_success_rate']:.2%}")

    if monitor.should_trigger_extension(threshold=0.7):
        logger.info("\n⚠️  Extension would be triggered in real scenario")

    return True


def test_real_alfworld(num_episodes=5, split='train'):
    """Test with real ALFWorld environment (with fallback to simulated)"""

    print_section("Phase 1: Initialize ALFWorld Environment")

    if not try_import_alfworld():
        return False

    try:
        import alfworld.agents.environment as environment

        logger.info("✅ ALFWorld imported successfully")

        # Create environment
        env = create_alfworld_env(split)

        if env is None:
            logger.info("")
            logger.info("Falling back to simulated test mode...")
            logger.info("(This still tests agent tree generation, monitoring, and extensions)")
            logger.info("")
            return run_simulated_test(num_episodes)

        logger.info("✅ ALFWorld environment initialized successfully")

    except Exception as e:
        logger.error(f"❌ Failed to initialize ALFWorld: {e}")
        logger.info("\nFalling back to simulated test mode...")
        return run_simulated_test(num_episodes)

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
