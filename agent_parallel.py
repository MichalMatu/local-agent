#!/usr/bin/env python3
"""Root launcher and compatibility alias for the packaged parallel supervisor."""
from __future__ import annotations

import sys

from local_agent.supervisor import orchestrator as _implementation

# Preserve the historical root-derived worker/restart paths until the packaged
# orchestrator owns explicit repo-root path resolution.
_implementation.__file__ = __file__

if __name__ == "__main__":
    raise SystemExit(_implementation.main())

sys.modules[__name__] = _implementation
