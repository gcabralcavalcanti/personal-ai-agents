"""Puts src/ on sys.path so tests run with plain `python -m unittest discover -s tests`."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
EXAMPLES = os.path.join(ROOT, "examples")
if SRC not in sys.path:
    sys.path.insert(0, SRC)
