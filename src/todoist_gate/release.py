#!/usr/bin/env python3
"""release.py - opens and closes the R2 / R36 locks of gate_hook.py, only after the human's ok in chat.

    python src/todoist_gate/release.py I7       # allow update-tasks with dueString (approved schedule change)
    python src/todoist_gate/release.py DELETE   # allow delete-object / uncomplete-tasks
    python src/todoist_gate/release.py --close  # remove both flags

Flags live in $GATE_FLAGS_DIR (default <repo>/.flags, out of git) and expire after 15 minutes.
"""

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FLAGS = os.environ.get("GATE_FLAGS_DIR") or os.path.join(REPO, ".flags")
NAMES = {"I7": "I7-OK", "DELETE": "DELETE-OK"}


def main(args):
    if args == ["--close"]:
        for n in NAMES.values():
            p = os.path.join(FLAGS, n)
            if os.path.exists(p):
                os.remove(p)
        print("locks closed")
        return 0
    if len(args) != 1 or args[0] not in NAMES:
        print(__doc__)
        return 2
    os.makedirs(FLAGS, exist_ok=True)
    p = os.path.join(FLAGS, NAMES[args[0]])
    open(p, "w").close()
    os.utime(p, None)
    print(f"{NAMES[args[0]]} open for 15 min - close with --close when done")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
