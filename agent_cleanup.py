#!/usr/bin/env python3
"""Compatibility module alias for packaged repository cleanup."""

import sys

from local_agent.repository import cleanup as _implementation

sys.modules[__name__] = _implementation
