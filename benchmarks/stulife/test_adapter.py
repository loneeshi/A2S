"""
Test script for StuLife adapter

Verifies that the adapter can load and run tasks correctly.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from benchmarks.stulife import StuLifeAdapter


def test_adapter():
    """Test basic adapter functionality"""
    print("=" * 60)
    print("Testing StuLife Adapter")
    print("=" * 60)

    # Initialize adapter
    print("\n1. Initializing adapter...")
    adapter = StuLifeAdapter()

    # Get available tasks
    print("\n2. Available tasks:")
    tasks = adapter.get_available_tasks()
    print(f"   Found {len(tasks)} tasks: {tasks[:5]}...")

    # Get task info
    if tasks:
        print(f"\n3. Task info for '{tasks[0]}':")
        info = adapter.get_task_info(tasks[0])
        for key, value in info.items():
            print(f"   {key}: {value}")

    # Test reset
    print(f"\n4. Resetting to task '{tasks[0]}'...")
    result = adapter.reset(tasks[0])
    print(f"   Task ID: {result['task_id']}")
    print(f"   Done: {result['done']}")
    print(f"   Observation: {result['observation'][:200]}...")

    # Test a simple action
    print("\n5. Testing action execution...")
    action = "I will answer: B"
    print(f"   Action: {action}")
    result = adapter.step(action)
    print(f"   Done: {result['done']}")
    print(f"   Success: {result['success']}")
    print(f"   Round: {result['info']['round']}/{result['info']['max_round']}")
    print(f"   Observation: {result['observation'][:200]}...")

    # Close adapter
    print("\n6. Closing adapter...")
    adapter.close()

    print("\n" + "=" * 60)
    print("✅ Adapter test completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    test_adapter()
