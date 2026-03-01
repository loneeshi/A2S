#!/usr/bin/env python3
"""
Test script for ALFWorld with Real Environment (Updated API)

This script uses gym-style interface which is more standard and likely
to work with newer versions of ALFWorld.

Requirements:
    conda activate skilltree_py311
    pip install alfworld

Usage:
    python scripts/test_alfworld_real_v2.py --num_episodes 5
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
    """Try to import ALFWorld"""
    try:
        import alfworld
        logger.info(f"✅ ALFWorld imported (version: {getattr(alfworld, '__version__', 'unknown')})")
        return True
    except ImportError as e:
        logger.error("❌ ALFWorld not installed!")
        logger.error("\nTo install:")
        logger.error("  conda activate skilltree_py311")
        logger.error("  pip install alfworld")
        return False


def explore_alfworld_api():
    """Explore ALFWorld API to find correct initialization"""
    import alfworld.agents.environment as env_module

    logger.info("Exploring ALFWorld API...")

    available = []
    for name in dir(env_module):
        if not name.startswith('_') and 'Env' in name:
            obj = getattr(env_module, name)
            available.append((name, type(obj).__name__))

    if available:
        logger.info("Available environment classes:")
        for name, obj_type in available:
            logger.info(f"  - {name}: {obj_type}")
    else:
        logger.warning("No environment classes found with 'Env' in name")
        logger.info("All public attributes:")
        for name in dir(env_module):
            if not name.startswith('_'):
                logger.info(f"  - {name}")

    return available


def create_alfworld_env_gym_style(split='train'):
    """Try to create ALFWorld environment using gym-style make function"""

    # Method 1: Try gym.make
    try:
        import gym
        import alfworld

        logger.info(f"Trying gym.make with ALFWorld...")

        # Common ALFWorld gym IDs
        gym_ids = [
            'AlfredTWEnv-v0',
            'AlfredTWEnv-v1',
            'alfworld:AlfredTWEnv-v0',
            'ALFWorld-v0',
        ]

        for gym_id in gym_ids:
            try:
                env = gym.make(gym_id)
                logger.info(f"✅ Created environment with gym.make('{gym_id}')")
                return env
            except:
                continue

    except Exception as e:
        logger.debug(f"gym.make failed: {e}")

    # Method 2: Try direct instantiation
    try:
        import alfworld.agents.environment as alf_env

        logger.info("Trying direct environment class instantiation...")

        # Look for environment classes
        env_classes = explore_alfworld_api()

        for env_name, env_type in env_classes:
            if env_type == 'type':
                try:
                    env_cls = getattr(alf_env, env_name)
                    env = env_cls()
                    logger.info(f"✅ Created {env_name} directly")
                    return env
                except Exception as e:
                    logger.debug(f"{env_name} failed: {e}")

    except Exception as e:
        logger.debug(f"Direct instantiation failed: {e}")

    # Method 3: Try using alfworld's preferred method
    try:
        logger.info("Trying alfworld's default initialization...")

        # Many newer RL frameworks use a build or create function
        import alfworld

        if hasattr(alfworld, 'build'):
            env = alfworld.build()
            logger.info("✅ Created environment with alfworld.build()")
            return env

        if hasattr(alfworld, 'make'):
            env = alfworld.make()
            logger.info("✅ Created environment with alfworld.make()")
            return env

    except Exception as e:
        logger.debug(f"alfworld build/make failed: {e}")

    logger.error("❌ All initialization methods failed")
    logger.info("\nSuggestions:")
    logger.info("1. Run: python scripts/explore_alfworld_api.py")
    logger.info("2. Check ALFWorld documentation: https://github.com/alfworld/alfworld")
    logger.info("3. Check installed version: pip show alfworld")

    return None


def test_with_alfworld_env(num_episodes=5):
    """Test with ALFWorld environment"""

    print_section("Phase 1: Initialize ALFWorld Environment")

    if not try_import_alfworld():
        return False

    env = create_alfworld_env_gym_style()

    if env is None:
        logger.error("\nFalling back to simulated test mode...")
        logger.info("Run: python scripts/explore_alfworld_api.py")
        logger.info("to explore ALFWorld's API and update the test script.")
        return False

    logger.info("✅ Environment created successfully")

    print_section("Phase 2: Generate Agent Tree")

    from core.generator import AgentTreeGenerator

    generator = AgentTreeGenerator()
    tree = generator.generate_initial_tree("alfworld")

    logger.info(f"✅ Generated {len(tree.workers)} workers and {len(tree.managers)} managers")

    print_section("Phase 3: Run Episodes")

    from core.optimizer import PerformanceMonitor, TaskResult, TaskStatus
    import random

    monitor = PerformanceMonitor(window_size=50)
    success_count = 0

    for episode_idx in range(num_episodes):
        try:
            logger.info(f"\n--- Episode {episode_idx + 1}/{num_episodes} ---")

            # Reset environment
            obs = env.reset()
            logger.info(f"Initial observation type: {type(obs)}")

            if isinstance(obs, (list, tuple)):
                obs = obs[0] if len(obs) > 0 else obs

            logger.info(f"Observation: {str(obs)[:100]}...")

            # Select random worker
            agent = random.choice(tree.workers)

            # Run episode
            done = False
            step = 0
            total_reward = 0
            episode_success = False

            while not done and step < 100:
                # Get action (random for now)
                action = env.action_space.sample() if hasattr(env, 'action_space') else "look"
                if isinstance(action, (int, np.integer)):
                    # Convert to string if needed
                    action = str(action)

                # Step
                result = env.step(action)

                # Handle different return formats
                if len(result) == 4:
                    obs, reward, done, info = result
                elif len(result) == 5:
                    obs, reward, done, truncated, info = result
                    done = done or truncated
                else:
                    logger.warning(f"Unexpected step result format: {len(result)} items")
                    break

                if isinstance(reward, (list, tuple)):
                    reward = reward[0]

                total_reward += reward
                step += 1

                if done:
                    episode_success = total_reward > 0
                    break

            logger.info(f"Steps: {step}, Reward: {total_reward:.2f}, Success: {episode_success}")

            # Record result
            result = TaskResult(
                task_id=f"alfworld_ep_{episode_idx}",
                task_type="alfworld_real",
                status=TaskStatus.SUCCESS if episode_success else TaskStatus.FAILURE,
                agent_used=agent.name,
                duration=step * 0.1,
            )
            monitor.record_task_result(result)

            if episode_success:
                success_count += 1

        except Exception as e:
            logger.error(f"Episode {episode_idx + 1} failed: {e}")
            import traceback
            traceback.print_exc()

    logger.info(f"\n✅ Completed {num_episodes} episodes")
    logger.info(f"Success rate: {success_count}/{num_episodes} ({success_count/num_episodes:.1%})")

    print_section("Summary")

    summary = monitor.get_summary()
    logger.info(f"Overall success rate: {summary['overall_success_rate']:.2%}")
    logger.info(f"Total tasks: {summary['total_tasks']}")

    env.close()
    return True


def print_section(title: str):
    """Print formatted section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    import numpy as np

    parser = argparse.ArgumentParser(description="Test with real ALFWorld (updated API)")
    parser.add_argument("--num_episodes", type=int, default=5)
    args = parser.parse_args()

    try:
        test_with_alfworld_env(args.num_episodes)
    except KeyboardInterrupt:
        logger.info("\nTest interrupted")
    except Exception as e:
        logger.error(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
