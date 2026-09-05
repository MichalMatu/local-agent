"""Compatibility module alias for packaged release version."""

import sys

from local_agent import version as _implementation

sys.modules[__name__] = _implementation
