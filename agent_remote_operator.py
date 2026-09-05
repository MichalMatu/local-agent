#!/usr/bin/env python3
"""Temporary module alias for packaged remote operator control."""

import sys

from local_agent.operator import remote as _implementation

# Keep the old import name only while remaining callers are migrated. Making the
# alias point at the implementation module preserves monkeypatch/test semantics
# without maintaining a second wrapper layer.
sys.modules[__name__] = _implementation
