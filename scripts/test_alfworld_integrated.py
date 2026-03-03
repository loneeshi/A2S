#!/usr/bin/env python3
"""
Integrated ALFWorld Test Script

This script combines the proven Agent_to_Skills adapter with LLM agent integration
for the auto-expansion agent cluster.

Features:
- Fast reset (0.7-0.9s) using proven adapter
- LLM-powered action selection
- Complete performance tracking
"""

import sys
import logging
import argparse
from pathlib import Path
import time

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from benchmarks.alfworld import AlfworldAdapter
from core.llm import ALFWorldAgent
from core.recorder import ResultsRecorder

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_alfworld_with_llm(num_episodes=3, split='train'):
    """Test ALFWorld with integrated LLM agent"""

    print("\n" + "=" * 80)
    print("  ALFWorld Integrated Test (Fast Adapter + LLM Agent)")
    print("=" * 80 + "\n")

    # Initialize adapter
    logger.info("Initializing ALFWorld adapter...")
    adapter = AlfworldAdapter(
        config_path=None,  # Use default config
        train_eval=split
    )
    logger.info("✅ Adapter initialized\n")

    # Initialize LLM agent
    logger.info("Initializing LLM agent for action selection...")
    llm_agent = ALFWorldAgent(model="gemini-2.5-flash")
    logger.info("✅ LLM agent initialized\n")

    # Initialize results recorder
    logger.info("Initializing results recorder...")
    recorder = ResultsRecorder()
    run_id = recorder.initialize_run(
        benchmark_name="alfworld_integrated",
        config={
            "split": split,
            "num_episodes": num_episodes,
            "model": "gemini-2.5-flash",
            "max_steps": 50
        },
        tree_config={
            "agent_type": "LLM",
            "adapter": "AlfworldAdapter"
        }
    )
    logger.info(f"✅ Results recorder initialized (Run ID: {run_id})\n")

    # Warm-up
    print("=" * 80)
    print("  Phase 1: Warm-up")
    print("=" * 80 + "\n")

    logger.info("Performing warm-up reset...")
    warmup_start = time.time()
    task_desc = adapter.reset()
    warmup_time = time.time() - warmup_start

    logger.info(f"✅ Warm-up completed in {warmup_time:.2f}s")
    if warmup_time < 5:
        logger.info(f"   🚀 Excellent! ({warmup_time:.2f}s < 5s)")
    elif warmup_time < 10:
        logger.info(f"   ✓ Good ({warmup_time:.2f}s)")
    else:
        logger.warning(f"   ⚠️  Slow ({warmup_time:.2f}s > 10s)")

    # Run episodes
    print("\n" + "=" * 80)
    print("  Phase 2: Run Episodes with LLM Agent")
    print("=" * 80 + "\n")

    success_count = 0
    total_steps = 0
    total_skipped_steps = 0  # Track steps skipped due to LLM failures
    total_time = 0

    for episode_idx in range(num_episodes):
        print("\n" + "#" * 60)
        print(f"# Episode {episode_idx + 1}/{num_episodes}")
        print("#" * 60 + "\n")

        # Reset
        logger.info("→ Resetting environment...")
        reset_start = time.time()
        task_desc = adapter.reset()
        reset_time = time.time() - reset_start

        logger.info(f"✅ Reset in {reset_time:.2f}s")
        logger.info(f"Task: {task_desc[:150]}...")

        # Reset LLM agent
        llm_agent.reset()

        # Run episode
        step = 0
        max_steps = 50  # ALFWorld tasks typically require 20-50 steps
        consecutive_failures = 0
        max_consecutive_failures = 3  # Skip episode if too many consecutive LLM failures
        episode_start = time.time()

        while step < max_steps and not adapter.is_done:
            logger.info(f"\n{'='*50}")
            logger.info(f"Step {step + 1}/{max_steps}")
            logger.info(f"{'='*50}")

            # Get admissible commands
            commands = adapter._extract_admissible_commands(adapter.infos)
            logger.info(f"Available commands: {len(commands)}")

            # Select action with LLM
            try:
                logger.info("⏳ LLM agent selecting action...")
                llm_start = time.time()
                action = llm_agent.select_action(
                    observation=adapter.obs,
                    task_description=task_desc,
                    admissible_actions=commands
                )
                llm_time = time.time() - llm_start
                logger.info(f"✅ LLM selected: {action} ({llm_time:.2f}s)")

                # Reset consecutive failures counter on success
                consecutive_failures = 0

            except Exception as e:
                consecutive_failures += 1
                logger.error(f"❌ LLM failed: {e}")
                logger.warning(f"   Skipping step (consecutive failures: {consecutive_failures}/{max_consecutive_failures})")

                # If too many consecutive failures, abort episode
                if consecutive_failures >= max_consecutive_failures:
                    logger.error(f"❌ Too many consecutive LLM failures ({max_consecutive_failures}), aborting episode")
                    break

                # Skip this step - don't execute command or increment step counter
                logger.info("   → Skipping step (no action executed)")
                total_skipped_steps += 1
                continue

            # Execute action
            logger.info(f"⏳ Executing: {action[:50]}...")
            step_start = time.time()
            result = adapter.step(action)
            step_time = time.time() - step_start

            logger.info(f"✅ Step completed in {step_time:.2f}s")
            logger.info(f"   Done: {result['done']}, Won: {result['won']}, Reward: {result['reward']:.2f}")

            # Only increment step counter if action was successfully executed
            step += 1
            total_steps += 1

        episode_time = time.time() - episode_start
        total_time += episode_time

        # Record episode result
        is_success = adapter.is_done and adapter.last_info.get('won', [False])[0]
        if is_success:
            success_count += 1
            logger.info(f"🎉 Episode {episode_idx + 1} SUCCESS!")
        else:
            logger.info(f"⏹️  Episode {episode_idx + 1} ended")

        # Save to results recorder
        recorder.record_episode(
            run_id=run_id,
            episode_id=episode_idx,
            task_type="alfworld_llm",
            agent_used="ALFWorldAgent",
            status="success" if is_success else "failure",
            steps=step,
            reward=adapter.last_reward,
            duration=episode_time,
            error_message=None if is_success else "Episode ended without success"
        )

    # Summary
    print("\n" + "=" * 80)
    print("  Test Summary")
    print("=" * 80 + "\n")

    avg_reset_time = warmup_time  # Approximate
    avg_step_time = total_time / total_steps if total_steps > 0 else 0
    total_attempts = total_steps + total_skipped_steps

    logger.info(f"Episodes: {num_episodes}")
    logger.info(f"Success rate: {success_count}/{num_episodes} ({success_count/num_episodes:.1%})")
    logger.info(f"Steps executed: {total_steps}")
    logger.info(f"Steps skipped (LLM failures): {total_skipped_steps}")
    logger.info(f"Total step attempts: {total_attempts}")
    if total_skipped_steps > 0:
        logger.warning(f"   ⚠️  Skip rate: {total_skipped_steps/total_attempts:.1%}")
    logger.info(f"Total time: {total_time:.2f}s")
    logger.info(f"Avg step time: {avg_step_time:.2f}s")

    # Finalize and save results
    logger.info("\nSaving results...")
    benchmark_results = recorder.finalize_run(run_id)
    logger.info(f"✅ Results saved to: results/alfworld_integrated/{run_id}.*")

    logger.info(f"\n✅ Test completed successfully!")

    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Integrated ALFWorld test with LLM agent"
    )
    parser.add_argument(
        "--num_episodes",
        type=int,
        default=3,
        help="Number of episodes to run (default: 3)"
    )
    parser.add_argument(
        "--split",
        type=str,
        default="train",
        choices=["train", "eval_in_distribution", "eval_out_of_distribution"],
        help="Data split to use (default: train)"
    )

    args = parser.parse_args()

    try:
        success = test_alfworld_with_llm(
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
