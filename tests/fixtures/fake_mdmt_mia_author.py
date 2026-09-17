#!/usr/bin/env python3
"""Test-only author stand-in that records cwd and argv without scientific work."""
import json
import os
import sys
from pathlib import Path


Path(os.environ["FAKE_AUTHOR_RECORD"]).write_text(
    json.dumps({"cwd": os.getcwd(), "argv": sys.argv[1:]}, sort_keys=True) + "\n",
    encoding="utf-8",
)
print("fake author completed without progress-filter output")
