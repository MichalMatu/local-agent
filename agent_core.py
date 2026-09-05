#!/usr/bin/env python3
"""Compatibility module alias for packaged execution core."""

import sys

from local_agent.foundation import core as _implementation

sys.modules[__name__] = _implementation
