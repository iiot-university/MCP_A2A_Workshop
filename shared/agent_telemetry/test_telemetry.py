#!/usr/bin/env python3
"""
Test script for AgentTelemetry module.

Simulates an agent that:
1. Starts telemetry
2. Updates external connection status
3. Calls a few tools (with simulated work)
4. Records an error
5. Waits for a couple heartbeats
6. Shuts down

Run from the project root:
    cd MCP_A2A_Workshop
    python -m shared.agent_telemetry.test_telemetry

Or directly:
    cd shared/agent_telemetry
    python test_telemetry.py
"""

import logging
import sys
import time
from pathlib import Path

# Configure logging to see telemetry module output
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from shared.agent_telemetry import AgentTelemetry


def simulate_tool_work(duration: float = 0.1):
    """Simulate some work being done."""
    time.sleep(duration)
    return {"result": "success", "value": 42}


def simulate_failing_tool():
    """Simulate a tool that fails."""
    time.sleep(0.05)
    raise ValueError("Simulated error: database connection timeout")


def main():
    print("=" * 60)
    print("Agent Telemetry Test Script")
    print("=" * 60)
    print()

    # Create telemetry instance
    print("[1/7] Creating telemetry instance...")
    telemetry = AgentTelemetry(
        agent_id="test-agent",
        agent_type="test",
        name="Test Agent",
        version="1.0.0",
        description="A test agent for validating telemetry",
        tools=["get_data", "process_data", "failing_tool"],
        capabilities=["mqtt", "mysql"],
        heartbeat_interval=10,  # Shorter interval for testing
    )
    print("    Created: test-agent")
    print()

    # Start telemetry
    print("[2/7] Starting telemetry (connecting to MQTT)...")
    telemetry.start()
    print("    Telemetry started")
    print()

    # Update external status
    print("[3/7] Updating external connection status...")
    telemetry.update_status(mqtt=True, mysql=True)
    print("    Status: mqtt=True, mysql=True")
    print()

    # Simulate successful tool calls
    print("[4/7] Simulating tool calls...")
    
    print("    Calling get_data...")
    with telemetry.track_tool("get_data"):
        result = simulate_tool_work(0.15)
    print(f"    Result: {result}")

    print("    Calling process_data...")
    with telemetry.track_tool("process_data"):
        result = simulate_tool_work(0.08)
    print(f"    Result: {result}")

    print("    Calling get_data again...")
    with telemetry.track_tool("get_data"):
        result = simulate_tool_work(0.12)
    print(f"    Result: {result}")
    print()

    # Simulate a failing tool
    print("[5/7] Simulating a failing tool call...")
    try:
        with telemetry.track_tool("failing_tool"):
            simulate_failing_tool()
    except ValueError as e:
        print(f"    Caught expected error: {e}")
    print()

    # Publish custom activity
    print("[6/7] Publishing custom activity...")
    telemetry.publish_custom_activity("test_event", {
        "message": "This is a custom test event",
        "test_id": 12345,
    })
    print("    Custom activity published")
    print()

    # Wait for heartbeats
    print("[7/7] Waiting for heartbeat cycle (15 seconds)...")
    print("    Watch the UNS for topics under: Enterprise/Dallas/Agents/test-agent/")
    print()
    
    for i in range(15, 0, -1):
        print(f"    Shutting down in {i}s...", end="\r")
        time.sleep(1)
    print()
    print()

    # Stop telemetry
    print("Stopping telemetry...")
    telemetry.stop()
    print("Telemetry stopped")
    print()

    print("=" * 60)
    print("Test complete!")
    print()
    print("Expected UNS topics published:")
    print("  - Enterprise/Dallas/Agents/test-agent/Identity")
    print("  - Enterprise/Dallas/Agents/test-agent/Status")
    print("  - Enterprise/Dallas/Agents/test-agent/Heartbeat")
    print("  - Enterprise/Dallas/Agents/test-agent/Tools/get_data")
    print("  - Enterprise/Dallas/Agents/test-agent/Tools/process_data")
    print("  - Enterprise/Dallas/Agents/test-agent/Tools/failing_tool")
    print("  - Enterprise/Dallas/Agents/test-agent/Activity")
    print("=" * 60)


if __name__ == "__main__":
    main()
