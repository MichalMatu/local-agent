#!/usr/bin/env python3
"""Compatibility module alias for packaged storage policy."""

import sys

from local_agent.foundation import storage as _implementation

sys.modules[__name__] = _implementation
