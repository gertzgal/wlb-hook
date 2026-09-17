#!/usr/bin/env python3
"""Entry point for UserPromptSubmit: the work-life-balance Gate."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from wlb_hook import gate, shim

if __name__ == "__main__":
    sys.exit(shim.run(gate.user_prompt_submit))
