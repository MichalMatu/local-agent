#!/usr/bin/env python3
"""Compatibility module alias for packaged repository context."""

import sys

from local_agent.repository import context as _implementation

sys.modules[__name__] = _implementation
