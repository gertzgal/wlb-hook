#!/usr/bin/env python3
"""Entry point for user_prompt_submit. Thin: locate src/, delegate to shim."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from wlb_hook import core, shim

if __name__ == "__main__":
    sys.exit(shim.run(core.user_prompt_submit))
