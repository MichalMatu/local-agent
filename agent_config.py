#!/usr/bin/env python3
"""Legacy root import surface for Local Agent runtime configuration."""

from local_agent.config import MIN_TIMEOUT, TIMEOUTS, TimeoutConfig, load_timeout_config

__all__ = [
    "MIN_TIMEOUT",
    "TIMEOUTS",
    "TimeoutConfig",
    "load_timeout_config",
]
