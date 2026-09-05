#!/usr/bin/env python3
"""Compatibility module alias for packaged runtime configuration."""

import sys

from local_agent import config as _implementation

sys.modules[__name__] = _implementation
