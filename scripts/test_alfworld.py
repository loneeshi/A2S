#!/usr/bin/env python3
"""
Test script for ALFWorld benchmark with Auto-Expansion Agent Cluster

This script demonstrates:
1. Reading ALFWorld benchmark intro
2. Generating agent tree from description
3. Running test episodes
4. Monitoring performance and triggering extensions
"""

import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.generator import (
    BenchmarkDescriptionReader,
    AgentTreeGenerator,
    EnvironmentExplorer,
)
from core.optimizer import (
    PerformanceMonitor,
    DynamicExtensionEngine,
    TaskResult,
    TaskStatus,
)
from core.recorder import ResultsRecorder

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_section(title: str):
    """Print a formatted section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def test_alfworld_benchmark():
    """Test ALFWorld benchmark with auto-expansion agents"""

    print_section("Phase 1: Read ALFWorld Benchmark Intro")

    # Step 1: Read benchmark intro
    reader = BenchmarkDescriptionReader()
    try:
        intro = reader.read_benchmark_intro("alfworld")
        logger.info(f"✅ Loaded benchmark: {intro.benchmark['name']}")
        logger.info(f"   Domain: {intro.benchmark['domain']}")
        logger.info(f"   Difficulty: {intro.benchmark['difficulty']}")
        logger.info(f"   Task types: {len(intro.task_types)}")
        for task in intro.task_types:
            logger.info(f"   - {task.name} ({task.complexity}): {len(task.tools)} tools")
    except FileNotFoundError as e:
        logger.error(f"❌ Failed to load ALFWorld benchmark: {e}")
        return

    print_section("Phase 2: Generate Initial Agent Tree")

    # Step 2: Generate agent tree
    generator = AgentTreeGenerator(reader)
    tree = generator.generate_initial_tree("alfworld")

    logger.info(f"✅ Generated agent tree:")
    logger.info(f"   Workers: {len(tree.workers)}")
    for worker in tree.workers:
        logger.info(f"   - {worker.name} ({worker.domain}): {len(worker.tools)} tools")
    logger.info(f"   Managers: {len(tree.managers)}")
    for manager in tree.managers:
        logger.info(f"   - {manager.name}: {manager.metadata.get('type', 'N/A')}")

    print_section("Phase 3: Initialize Performance Monitor and Results Recorder")

    # Step 3: Setup performance monitoring
    monitor = PerformanceMonitor(window_size=50)
    extension_engine = DynamicExtensionEngine(
        performance_monitor=monitor,
        extension_threshold=0.7,
        max_workers=15,
        max_managers=4
    )
    logger.info("✅ Performance monitor and extension engine initialized")
    logger.info(f"   Extension threshold: 70% success rate")
    logger.info(f"   Window size: 50 tasks")

    # Get task types and episode count for results recorder config
    import random
    task_types = [task.name for task in intro.task_types]
    num_episodes = 20

    # Initialize results recorder
    results_recorder = ResultsRecorder()
    run_id = results_recorder.initialize_run(
        benchmark_name="alfworld_simulated",
        config={"num_episodes": num_episodes},
        tree_config={
            "num_workers": len(tree.workers),
            "num_managers": len(tree.managers),
            "workers": [w.name for w in tree.workers],
            "managers": [m.name for m in tree.managers]
        }
    )
    logger.info(f"✅ Results recorder initialized")
    logger.info(f"   Run ID: {run_id}")

    print_section("Phase 4: Run Test Episodes")

    # Step 4: Run simulated test episodes
    logger.info(f"Running {num_episodes} test episodes...")

    for episode_id in range(num_episodes):
        # Select random task type
        task_type = random.choice(task_types)
        agent = random.choice(tree.workers)

        # Simulate task execution (70% success rate for now)
        success = random.random() < 0.7

        result = TaskResult(
            task_id=f"alfworld_task_{episode_id}",
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

        # Print progress every 5 episodes
        if (episode_id + 1) % 5 == 0:
            recent = monitor.get_recent_performance(n=5)
            logger.info(
                f"   Episode {episode_id + 1}/{num_episodes} - "
                f"Recent success rate: {recent['success_rate']:.2%}"
            )

    logger.info(f"✅ Completed {num_episodes} episodes")

    print_section("Phase 5: Performance Analysis")

    # Step 5: Analyze performance
    summary = monitor.get_summary()
    logger.info(f"Overall Performance:")
    logger.info(f"   Total tasks: {summary['total_tasks']}")
    logger.info(f"   Overall success rate: {summary['overall_success_rate']:.2%}")

    logger.info(f"\nAgent Performance:")
    for agent_name, metrics in summary['agent_metrics'].items():
        logger.info(
            f"   {agent_name}: "
            f"{metrics['success_rate']:.2%} "
            f"({metrics['total_tasks']} tasks)"
        )

    logger.info(f"\nTask Type Performance:")
    for task_type, metrics in summary['task_type_metrics'].items():
        logger.info(
            f"   {task_type}: "
            f"{metrics['success_rate']:.2%} "
            f"({metrics['total']} tasks, "
            f"{metrics['successful']} success, "
            f"{metrics['failed']} failed)"
        )

    print_section("Phase 6: Dynamic Extension (if needed)")

    # Step 6: Check if extension is triggered
    if monitor.should_trigger_extension(threshold=0.7):
        logger.info("⚠️  Performance threshold breached - analyzing for extension...")

        underperforming = monitor.get_underperforming_agents(threshold=0.7)
        if underperforming:
            logger.info(f"   Underperforming agents: {underperforming}")

        difficult_tasks = monitor.get_difficult_task_types(threshold=0.5)
        if difficult_tasks:
            logger.info(f"   Difficult task types: {difficult_tasks}")

        # Apply extensions
        logger.info("Applying extensions...")
        extended_tree = extension_engine.monitor_and_extend(tree)

        logger.info(f"✅ Tree extended:")
        logger.info(f"   Workers: {len(tree.workers)} → {len(extended_tree.workers)}")
        logger.info(f"   Managers: {len(tree.managers)} → {len(extended_tree.managers)}")

        # Show extension history
        history = extension_engine.get_extension_history()
        if history:
            logger.info(f"\nExtensions applied:")
            for i, ext in enumerate(history, 1):
                logger.info(f"   {i}. {ext['type']}: {ext['reason'][:80]}...")
    else:
        logger.info("✅ Performance satisfactory - no extension needed")

    print_section("Summary")

    # Finalize and save results
    logger.info("Saving results...")
    benchmark_results = results_recorder.finalize_run(run_id)

    logger.info("🎉 ALFWorld benchmark test completed!")
    logger.info(f"\nFinal tree configuration:")
    logger.info(f"   Workers: {len(tree.workers)}")
    logger.info(f"   Managers: {len(tree.managers)}")
    logger.info(f"   Overall success rate: {monitor.get_overall_success_rate():.2%}")
    logger.info(f"\nResults saved to: results/alfworld_simulated/{run_id}.*")

    logger.info(f"\nNext steps:")
    logger.info(f"   1. Implement actual ALFWorld environment integration")
    logger.info(f"   2. Run real tasks instead of simulated episodes")
    logger.info(f"   3. Fine-tune extension thresholds")
    logger.info(f"   4. Analyze cache hit rates for prompts")


if __name__ == "__main__":
    try:
        test_alfworld_benchmark()
    except KeyboardInterrupt:
        logger.info("\n\nTest interrupted by user")
    except Exception as e:
        logger.error(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
