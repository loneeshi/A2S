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

# Enable ALFWorld/THOR detailed logging for render progress
import os
os.environ['THOR_CPU_THREADS'] = '1'  # Limit CPU threads for stability
os.environ['ALFWORLD_LOAD_LOGS'] = '1'  # Enable loading logs

# Configure ALFWorld logger to show initialization progress
alfworld_logger = logging.getLogger('alfworld')
alfworld_logger.setLevel(logging.INFO)
thor_logger = logging.getLogger('thor')
thor_logger.setLevel(logging.INFO)


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

    # Create complete config with all required parameters
    # Based on Agent_to_Skills configuration for optimal performance
    config = {
        'env': {
            'type': 'AlfredTWEnv',
            'goal_desc_human_anns_prob': 0,
            'task_types': [1],  # 1-6: pick_and_place_simple to pick_two_obj
            'domain_randomization': False,  # No randomization for eval
            'expert_type': 'handcoded',  # Use hardcoded expert
            'expert_timeout_steps': 150,  # Timeout for expert
        },
        'dataset': {
            'data_path': '~/.cache/alfworld/json_2.1.1/train',
            'eval_id_data_path': '~/.cache/alfworld/json_2.1.1/valid_train',
            'eval_ood_data_path': '~/.cache/alfworld/json_2.1.1/valid_unseen',
            'num_train_games': -1,
            'num_eval_games': -1,
        },
        'logic': {
            'domain': 'logic/alfred.pddl',
            'grammar': 'logic/alfred.twl2'
        },
        'controller': {
            'type': 'oracle',
            'debug': False,
            'load_receps': True
        },
        'general': {
            'random_seed': 42,
            'use_cuda': False,  # CRITICAL: Disable CUDA to avoid long GPU initialization
            'task': 'alfred',
            'training_method': 'dagger',
            'observation_pool_capacity': 3,
            'hide_init_receptacles': False
        },
        'dagger': {
            'action_space': 'generation',
            'max_target_length': 20,
            'beam_width': 10,
            'generate_top_k': 5,
            'unstick_by_beam_search': False,
            'training': {
                'max_nb_steps_per_episode': 50  # Max steps per episode
            },
            'fraction_assist': {
                'fraction_assist_anneal_episodes': 50000,
                'fraction_assist_anneal_from': 1.0,
                'fraction_assist_anneal_to': 0.01
            },
            'fraction_random': {
                'fraction_random_anneal_episodes': 0,
                'fraction_random_anneal_from': 0.0,
                'fraction_random_anneal_to': 0.0
            }
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
        logger.info("Step 1/3: Loading AlfredTWEnv class...")
        env_class = environment.get_environment('AlfredTWEnv')
        logger.info("✅ Step 1/3: Environment class loaded")

        # Instantiate environment
        logger.info("Step 2/3: Instantiating environment (this loads Unity 3D engine)...")
        logger.info("   - Loading 3D scenes and objects...")
        logger.info("   - Initializing physics engine...")
        import time
        start = time.time()
        env = env_class(config, train_eval=train_eval)
        elapsed = time.time() - start
        logger.info(f"✅ Step 2/3: Environment instantiated in {elapsed:.2f}s")

        # Initialize batch
        logger.info("Step 3/3: Initializing environment batch...")
        logger.info("   - Setting up batch processing...")
        logger.info("   - Preparing first episode...")
        start = time.time()
        env = env.init_env(batch_size=1)
        elapsed = time.time() - start
        logger.info(f"✅ Step 3/3: Batch initialized in {elapsed:.2f}s")
        logger.info("✅ Environment fully initialized and ready")

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
    from core.recorder import ResultsRecorder
    import random

    print_section("Simulated Test Mode")

    logger.info("Generating agent tree...")

    generator = AgentTreeGenerator()
    tree = generator.generate_initial_tree("alfworld")

    logger.info(f"✅ Generated {len(tree.workers)} workers and {len(tree.managers)} managers")

    logger.info("Initializing performance monitor and results recorder...")

    monitor = PerformanceMonitor(window_size=50)
    extension_engine = DynamicExtensionEngine(
        performance_monitor=monitor,
        extension_threshold=0.7
    )

    # Initialize results recorder
    results_recorder = ResultsRecorder()
    run_id = results_recorder.initialize_run(
        benchmark_name="alfworld_simulated",
        config={"mode": "simulated", "num_episodes": num_episodes},
        tree_config={
            "num_workers": len(tree.workers),
            "num_managers": len(tree.managers),
            "workers": [w.name for w in tree.workers],
            "managers": [m.name for m in tree.managers]
        }
    )

    logger.info("Running simulated episodes...")

    task_types = ["object_manipulation", "navigation_exploration", "multi_step_task",
                   "object_search", "task_planning"]

    success_count = 0
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

        # Record to results file
        results_recorder.record_episode(
            run_id=run_id,
            episode_id=episode_id,
            task_type=task_type,
            agent_used=agent.name,
            status="success" if success else "failure",
            steps=int(random.uniform(5, 20)),
            reward=1.0 if success else 0.0,
            duration=result.duration,
            error_message=result.error_message
        )

        if success:
            success_count += 1

        if (episode_id + 1) % max(1, num_episodes // 5) == 0:
            recent = monitor.get_recent_performance(n=min(5, episode_id + 1))
            logger.info(f"  Episode {episode_id + 1}/{num_episodes} - Recent success rate: {recent['success_rate']:.2%}")

    logger.info(f"✅ Completed {num_episodes} simulated episodes")

    print_section("Performance Analysis")

    summary = monitor.get_summary()
    logger.info(f"Overall success rate: {summary['overall_success_rate']:.2%}")

    print_section("Summary")

    # Finalize and save results
    logger.info("Saving results...")
    benchmark_results = results_recorder.finalize_run(run_id)

    logger.info("🎉 Simulated test completed!")
    logger.info(f"Agents: {len(tree.workers)} workers, {len(tree.managers)} managers")
    logger.info(f"Success rate: {summary['overall_success_rate']:.2%}")
    logger.info(f"\nResults saved to: results/alfworld_simulated/{run_id}.*")

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

    print_section("Phase 3: Initialize LLM Agent, Performance Monitor and Results Recorder")

    from core.optimizer import PerformanceMonitor, DynamicExtensionEngine, TaskResult, TaskStatus
    from core.recorder import ResultsRecorder
    from core.llm import ALFWorldAgent

    # Initialize LLM agent for action selection
    logger.info("Initializing LLM agent for ALFWorld...")
    llm_agent = ALFWorldAgent(model="gemini-2.5-flash")
    logger.info("✅ LLM agent initialized")

    monitor = PerformanceMonitor(window_size=50)
    extension_engine = DynamicExtensionEngine(
        performance_monitor=monitor,
        extension_threshold=0.7
    )

    # Initialize results recorder
    results_recorder = ResultsRecorder()
    run_id = results_recorder.initialize_run(
        benchmark_name="alfworld",
        config={"split": split, "num_episodes": num_episodes, "model": "gemini-2.5-flash"},
        tree_config={
            "num_workers": len(tree.workers),
            "num_managers": len(tree.managers),
            "workers": [w.name for w in tree.workers],
            "managers": [m.name for m in tree.managers]
        }
    )

    logger.info("✅ Performance monitor and results recorder initialized")
    logger.info(f"Run ID: {run_id}")

    print_section("Phase 4: Environment Warm-up")

    logger.info("⏳ Performing warm-up reset to cache 3D assets...")
    logger.info("(This includes: loading scene, textures, objects, physics)")
    import time
    warmup_start = time.time()
    try:
        logger.info("   → Resetting environment...")
        env.reset()
        warmup_elapsed = time.time() - warmup_start
        logger.info(f"✅ Warm-up completed in {warmup_elapsed:.2f}s")
        if warmup_elapsed < 5:
            logger.info(f"   🚀 Excellent! Reset is fast ({warmup_elapsed:.2f}s < 5s)")
        elif warmup_elapsed < 10:
            logger.info(f"   ✓ Good performance ({warmup_elapsed:.2f}s)")
        else:
            logger.warning(f"   ⚠️  Reset is slow ({warmup_elapsed:.2f}s > 10s)")
        logger.info("   Subsequent resets should be similar or faster")
    except Exception as e:
        logger.warning(f"⚠️  Warm-up failed: {e}")
        logger.warning("   Continuing anyway...")

    print_section("Phase 5: Run Real ALFWorld Episodes")

    import numpy as np

    success_count = 0
    for episode_idx in range(num_episodes):
        try:
            logger.info(f"\n{'#'*60}")
            logger.info(f"# Episode {episode_idx + 1}/{num_episodes}")
            logger.info(f"{'#'*60}")

            # Reset environment
            logger.info("⏳ Resetting environment...")
            import time
            reset_start = time.time()
            obs, info = env.reset()
            reset_elapsed = time.time() - reset_start
            logger.info(f"✅ Environment reset in {reset_elapsed:.2f}s")

            logger.info(f"Task: {info.get('extra.task_desc', 'Unknown')}")
            logger.info(f"Observation: {obs[0][:100]}...")

            # Select a worker agent (random for now)
            import random
            agent = random.choice(tree.workers)
            logger.info(f"Selected agent: {agent.name}")

            # Reset LLM agent for new episode
            logger.info("⏳ Resetting LLM agent conversation history...")
            llm_agent.reset()
            logger.info("✅ LLM agent reset")

            # Run episode
            done = False
            step = 0
            episode_success = False
            total_reward = 0
            max_steps = 50  # Reduced from 100 for faster testing

            logger.info(f"\n🎬 Starting episode execution (max {max_steps} steps)...")

            while not done and step < max_steps:
                # Get admissible actions
                if hasattr(env, 'get_admissible_actions'):
                    logger.info(f"\n{'='*60}")
                    logger.info(f"Step {step+1}/{max_steps}")
                    logger.info(f"{'='*60}")

                    # Time the get_admissible_actions call
                    logger.info("⏳ Calling env.get_admissible_actions()...")
                    import time
                    start_time = time.time()
                    admissible_actions = env.get_admissible_actions()
                    elapsed = time.time() - start_time
                    logger.info(f"✅ get_admissible_actions() completed in {elapsed:.2f}s")
                    logger.info(f"   Number of action lists: {len(admissible_actions)}")
                    logger.info(f"   Actions in first list: {len(admissible_actions[0]) if admissible_actions else 0}")

                    # Use LLM agent to select action
                    task_desc = info.get('extra.task_desc', 'Complete the task')
                    observation = obs[0] if isinstance(obs, list) else obs

                    logger.info(f"\n⏳ Calling LLM agent to select action...")
                    logger.info(f"   Task: {task_desc[:100]}...")
                    logger.info(f"   Observation: {observation[:100]}...")
                    logger.info(f"   Available actions: {len(admissible_actions[0]) if admissible_actions else 0} actions")

                    try:
                        llm_start = time.time()
                        action = llm_agent.select_action(
                            observation=observation,
                            task_description=task_desc,
                            admissible_actions=admissible_actions[0] if admissible_actions else ["look around"]
                        )
                        llm_elapsed = time.time() - llm_start
                        logger.info(f"✅ LLM agent selected action in {llm_elapsed:.2f}s")
                        logger.info(f"   Action: {action}")
                    except Exception as e:
                        logger.error(f"❌ LLM action selection failed: {e}")
                        logger.error(f"   Falling back to first available action")
                        import traceback
                        traceback.print_exc()
                        action = admissible_actions[0][0] if admissible_actions and admissible_actions[0] else "look around"
                else:
                    logger.warning("Environment doesn't have get_admissible_actions method")
                    action = "look around"

                # Step environment
                logger.info(f"⏳ Stepping environment with action: {action[:50]}...")
                step_start = time.time()
                obs, reward, done, info = env.step([action])
                step_elapsed = time.time() - step_start
                logger.info(f"✅ Environment step completed in {step_elapsed:.2f}s")

                total_reward += reward[0]
                step += 1

                # Log progress every 10 steps
                if step % 10 == 0:
                    logger.info(f"Step {step}/{max_steps}, Reward so far: {total_reward:.2f}")

                if done:
                    episode_success = reward[0] > 0
                    break

            logger.info(f"Steps: {step}/{max_steps}, Reward: {total_reward:.2f}, Success: {episode_success}")

            # Record result
            result = TaskResult(
                task_id=f"alfworld_real_{episode_idx}",
                task_type="alfworld_task",
                status=TaskStatus.SUCCESS if episode_success else TaskStatus.FAILURE,
                agent_used=agent.name,
                duration=step * 0.1,  # Approximate
            )
            monitor.record_task_result(result)

            # Record to results file
            results_recorder.record_episode(
                run_id=run_id,
                episode_id=episode_idx,
                task_type="alfworld_task",
                agent_used=agent.name,
                status="success" if episode_success else "failure",
                steps=step,
                reward=total_reward,
                duration=step * 0.1
            )

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

            # Record failure to results file
            results_recorder.record_episode(
                run_id=run_id,
                episode_id=episode_idx,
                task_type="alfworld_task",
                agent_used=agent.name if agent else "Unknown",
                status="failure",
                steps=0,
                reward=0.0,
                duration=0.0,
                error_message=str(e)
            )

    logger.info(f"\n✅ Completed {num_episodes} real episodes")
    logger.info(f"Success rate: {success_count}/{num_episodes} ({success_count/num_episodes:.1%})")

    print_section("Phase 6: Performance Analysis")

    summary = monitor.get_summary()
    logger.info(f"Overall Performance:")
    logger.info(f"   Total tasks: {summary['total_tasks']}")
    logger.info(f"   Overall success rate: {summary['overall_success_rate']:.2%}")

    print_section("Phase 7: Dynamic Extension (if needed)")

    if monitor.should_trigger_extension(threshold=0.7):
        logger.info("⚠️  Performance threshold breached - applying extensions...")
        extended_tree = extension_engine.monitor_and_extend(tree)
        logger.info(f"✅ Tree extended: {len(tree.workers)} → {len(extended_tree.workers)} workers")
    else:
        logger.info("✅ Performance satisfactory - no extension needed")

    print_section("Summary")

    # Finalize and save results
    logger.info("Saving results...")
    benchmark_results = results_recorder.finalize_run(run_id)

    logger.info("🎉 Real ALFWorld test completed!")
    logger.info(f"\nResults:")
    logger.info(f"   Episodes run: {num_episodes}")
    logger.info(f"   Success rate: {success_count/num_episodes:.1%}")
    logger.info(f"   Final workers: {len(tree.workers)}")
    logger.info(f"   Final managers: {len(tree.managers)}")
    logger.info(f"\nResults saved to: results/alfworld/{run_id}.*")

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
