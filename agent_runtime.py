#!/usr/bin/env python3
"""Compatibility module alias for packaged task runtime executor."""

import sys

from local_agent.runtime import executor as _implementation

sys.modules[__name__] = _implementation
