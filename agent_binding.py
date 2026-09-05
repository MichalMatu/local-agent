#!/usr/bin/env python3
"""Compatibility module alias for packaged repository binding contracts."""

import sys

from local_agent.repository import binding as _implementation

sys.modules[__name__] = _implementation
