#!/usr/bin/env python3
"""Operational launcher for local_agent.daemon.service."""

from local_agent.daemon.service import run

if __name__ == "__main__":
    raise SystemExit(run())
