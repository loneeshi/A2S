"""
Test script for StuLife detailed logger.
"""
import time
from stulife_logger import StuLifeLogger


def test_logger():
    """Test the StuLife logger functionality."""

    # Create logger
    run_id = f"test_logger_{time.strftime('%Y%m%d_%H%M%S')}"
    logger = StuLifeLogger(run_id=run_id, output_dir="../../results/stulife")

    print(f"Testing StuLife Logger with run_id: {run_id}")
    print("=" * 80)

    # Simulate episode 1
    logger.start_episode(
        episode_id=0,
        task_id="test_task_001",
        task_description="Navigate to the library and borrow a book",
        max_rounds=3
    )

    # Simulate round 1
    logger.log_round_start(1, 3)
    agent_response = "I will go to the library first."
    logger.log_agent_response(agent_response)
    logger.log_parsed_action("execute", agent_response)
    logger.log_action_execution("execute")
    observation = "You are now at the library entrance."
    logger.log_observation(observation)
    logger.record_round(
        round_num=1,
        agent_response=agent_response,
        parsed_action={"type": "execute", "content": agent_response},
        observation=observation,
        round_duration=1.2
    )

    # Simulate round 2
    logger.log_round_start(2, 3)
    agent_response = "I will enter the library and find the book section."
    logger.log_agent_response(agent_response)
    logger.log_parsed_action("execute", agent_response)
    logger.log_action_execution("execute")
    observation = "You are in the book section. You see many books on the shelves."
    logger.log_observation(observation)
    logger.record_round(
        round_num=2,
        agent_response=agent_response,
        parsed_action={"type": "execute", "content": agent_response},
        observation=observation,
        round_duration=1.5
    )

    # Simulate round 3
    logger.log_round_start(3, 3)
    agent_response = "finish: I have borrowed the book successfully."
    logger.log_agent_response(agent_response)
    logger.log_parsed_action("finish", agent_response)
    logger.log_action_execution("finish")
    observation = "Task completed successfully!"
    logger.log_observation(observation)
    logger.record_round(
        round_num=3,
        agent_response=agent_response,
        parsed_action={"type": "finish", "content": agent_response},
        observation=observation,
        round_duration=0.8
    )

    # End episode
    logger.end_episode(
        success=True,
        finish_reason="task_completed",
        evaluation_outcome="CORRECT",
        rounds_used=3,
        episode_duration=3.5,
        chat_history=[
            {"role": "user", "content": "Navigate to the library"},
            {"role": "assistant", "content": "I will go to the library first."},
            {"role": "user", "content": "You are at the library entrance."},
            {"role": "assistant", "content": "I will enter and find books."},
        ]
    )

    # Save results
    logger.save_detailed_results()

    print("\n" + "=" * 80)
    print("✅ Test completed!")
    print(f"📁 Log file: {logger.log_file}")
    print(f"📁 JSON file: {logger.json_file}")


if __name__ == "__main__":
    test_logger()
