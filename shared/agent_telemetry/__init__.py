"""
Agent Telemetry Module

Shared module for publishing agent/server state to the Unified Namespace (UNS).
Enables real-time visibility into what agents are doing.
"""

from .telemetry import AgentTelemetry

__all__ = ["AgentTelemetry"]
__version__ = "1.0.0"
