#!/usr/bin/env python3
"""Compatibility module alias for packaged process foundation."""

import sys

from local_agent.foundation import process as _implementation

sys.modules[__name__] = _implementation
