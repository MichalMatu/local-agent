#!/usr/bin/env python3
"""Compatibility module alias for packaged remote operator control."""

import sys

from local_agent.operator import remote as _implementation

sys.modules[__name__] = _implementation
