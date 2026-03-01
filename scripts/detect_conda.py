#!/usr/bin/env python3
"""
Detect and use conda environments
"""

import os
import sys
import subprocess
from pathlib import Path


def find_conda_env():
    """Find conda environment skilltree_py311"""
    env_name = "skilltree_py311"

    # Possible conda installation paths
    base_paths = [
        Path.home() / "anaconda3",
        Path.home() / "miniconda3",
        Path.home() / "opt" / "anaconda3",
        Path.home() / "opt" / "miniconda3",
        Path("/usr/local") / "anaconda3",
        Path("/usr/local") / "miniconda3",
    ]

    for base_path in base_paths:
        env_path = base_path / "envs" / env_name
        if env_path.exists():
            python_path = env_path / "bin" / "python"
            if python_path.exists():
                return str(python_path)

    return None


def run_test():
    """Run ALFWorld test in conda environment"""
    print("=" * 80)
    print("  ALFWorld Test - Conda Environment Detector")
    print("=" * 80)
    print()

    # Find conda environment
    python_path = find_conda_env()

    if python_path:
        print(f"✅ Found conda environment: {python_path}")
        print()

        # Run test
        test_script = Path(__file__).parent / "test_alfworld_real.py"

        if not test_script.exists():
            print(f"❌ Test script not found: {test_script}")
            return 1

        print(f"Running test script: {test_script}")
        print()

        result = subprocess.run(
            [python_path, str(test_script), "--num_episodes", "3"],
            cwd=Path(__file__).parent.parent,
        )

        return result.returncode

    else:
        print("❌ Could not find conda environment 'skilltree_py311'")
        print()
        print("Searched in:")
        for base in [
            "~/anaconda3/envs/",
            "~/miniconda3/envs/",
            "~/opt/anaconda3/envs/",
            "~/opt/miniconda3/envs/",
        ]:
            print(f"  - {base}")
        print()
        print("Please ensure:")
        print("  1. Conda is installed")
        print("  2. Environment 'skilltree_py311' exists")
        print("  3. Run: conda activate skilltree_py311")
        print()

        return 1


if __name__ == "__main__":
    try:
        exit_code = run_test()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nTest interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
