#!/usr/bin/env python3
"""public_filter.py - privacy-by-default filter for publishing a personal dashboard (excerpt/pattern).

The habits agent produces a private dashboard from personal data. The public version is produced by the
SAME generator in "public mode", followed by two independent safety layers (defense in depth):

  1. ALLOWLIST - only habits whose internal ID is listed in PUBLIC_IDS are rendered. A new habit never
     goes public by itself; when in doubt, it stays out. Some categories are refused even if listed.
  2. DENYLIST AUDIT - after rendering, the HTML is normalized (lowercase, accents stripped) and scanned
     for forbidden patterns. One hit aborts the run and NOTHING is written: the previous public file
     stays as it was.

The real lists are private (they would themselves reveal what is being hidden). The lists below are
fictitious examples of the same shape.

Usage:  python src/privacy/public_filter.py <rendered.html>      (exit 1 = forbidden term found)
"""

import re
import sys
import unicodedata

PUBLIC_IDS = ["H01", "H02", "H07"]  # fictitious: e.g. "read 20 pages", "study block", "language practice"
REFUSED_CATEGORIES = {"health", "private"}  # refused even if someone adds the ID above

FORBIDDEN = [  # fictitious examples; matched on lowercase text without accents
    r"\bdiagnos",
    r"\bmedica",
    r"\bsalary\b",
    r"\bdebt\b",
    r"\bbank\b",
    r"@\w+\.(com|br)\b",  # any e-mail address
    r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b",  # Brazilian CPF pattern
]


def normalize(s):
    s = unicodedata.normalize("NFKD", str(s))
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def select(habits):
    """Allowlist step: keep only listed IDs, never a refused category."""
    return [h for h in habits if h["id"] in PUBLIC_IDS and h.get("category") not in REFUSED_CATEGORIES]


def findings(text):
    """[(pattern, context)] for every forbidden pattern found."""
    t = normalize(text)
    out = []
    for p in FORBIDDEN:
        m = re.search(p, t)
        if m:
            out.append((p, t[max(0, m.start() - 30) : m.end() + 30].replace("\n", " ")))
    return out


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    with open(sys.argv[1], encoding="utf-8") as f:
        bad = findings(f.read())
    for p, ctx in bad:
        print(f"[{p}] ...{ctx}...")
    print("ABORT: forbidden term in public output" if bad else "OK: audit clean")
    sys.exit(1 if bad else 0)
