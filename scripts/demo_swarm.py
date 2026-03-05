import sys
import os
import time

# Ensure core is in path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from core.ui_bridge import UIBridge

def run_demo_swarm():
    """
    Full-Stack Demo: SPEC_v1.0 Swarm UI Integration
    Simulates a real agent session on macOS.
    """
    print("--- SWARM CORE INITIALIZING ---")

    # 1. Spawn Agents in UI
    UIBridge.emit_agent_update("m-01", "Master Orchestrator", "thinking", tokens=120)
    time.sleep(1)

    UIBridge.emit_log("m-01", "system", "Agent M-01 synchronized with macOS Core.")
    UIBridge.emit_log("m-01", "reasoning", "Analyzing task metadata from benchmark: StuLife.2.0")

    # 2. Handoff to Worker
    UIBridge.emit_agent_update("w-01", "Browser Specialist", "idle")
    time.sleep(1.5)

    UIBridge.emit_log("m-01", "content", "Handoff to Browser Specialist for environment exploration.")
    UIBridge.emit_handoff("m-01", "w-01", payload_size=3)

    UIBridge.emit_agent_update("m-01", "Master Orchestrator", "idle")
    UIBridge.emit_agent_update("w-01", "Browser Specialist", "running", tokens=850, latency=140)

    # 3. Simulate Worker Activity
    time.sleep(2)
    UIBridge.emit_log("w-01", "tool_call", "geography.walk_to(target='B025')")
    time.sleep(1)
    UIBridge.emit_log("w-01", "tool_result", "STATUS: SUCCESS. Location: Student Center (B025)")

    # 4. Final Handoff back
    time.sleep(2)
    UIBridge.emit_handoff("w-01", "m-01", is_animating=True)
    UIBridge.emit_agent_update("w-01", "Browser Specialist", "completed")
    UIBridge.emit_agent_update("m-01", "Master Orchestrator", "completed", tokens=4500)

    UIBridge.emit_log("m-01", "system", "TASK COMPLETE. Final success rate: 1.0")

if __name__ == "__main__":
    run_demo_swarm()
