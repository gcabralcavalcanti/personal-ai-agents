#!/usr/bin/env python3
"""job_delta.py - public job-board collection with a delta state (excerpt of the career agent's collector).

Reads a CSV of company career pages, fetches each PUBLIC page (never LinkedIn or anything behind a login),
extracts internship/trainee titles (Greenhouse: public JSON API; other pages: text pattern), and compares
with the previous run stored in a state file. Output: a Markdown report of ONLY what changed - new
openings, openings that disappeared, page changed, errors.

Idempotent by design: running it twice in a row reports "unchanged" the second time; nothing is
duplicated, and it writes only to its own output folder (no task manager, no spreadsheet).

Usage:  python src/career/job_delta.py <sources.csv> <out_dir> [--dry]
CSV columns (semicolon-separated): area;company;link        (see examples/job_sources.csv)
"""

import csv
import hashlib
import json
import os
import re
import sys
import time
import urllib.request
from datetime import date

UA = {"User-Agent": "Mozilla/5.0 job-delta/1.0 (personal, low-frequency)"}
BLOCKED = ("linkedin.com", "glassdoor", "instagram.com", "facebook.com", "whatsapp", "mail.google")
KEYWORDS = re.compile(r"(?i)intern|est[aá]gi|trainee|summer|junior|analyst|associate")
OPENING = re.compile(r"(?i)[^.|\n]{0,40}(intern(ship)?|est[aá]gi[oa]|trainee|summer job)[^.|\n]{0,60}")


def http_get(url, timeout=25):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", "replace")


def titles_greenhouse(board, get=http_get):
    _, body = get(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=false")
    jobs = json.loads(body).get("jobs", [])
    return sorted(
        {
            f"{j['title'].strip()} - {(j.get('location') or {}).get('name', '')}"
            for j in jobs
            if KEYWORDS.search(j.get("title") or "")
        }
    )


def titles_generic(html):
    html = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", html)
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))
    return text, sorted({m.group(0).strip() for m in OPENING.finditer(text)})[:25]


def collect(url, get=http_get):
    """{'kind', 'items', 'hash', 'error'?} for one source. Never raises: an error is a result."""
    if any(b in url.lower() for b in BLOCKED):
        return {"kind": "blocked", "items": [], "hash": None, "error": "source the agent does not open"}
    try:
        m = re.search(r"boards(?:-api)?\.greenhouse\.io/(?:v1/boards/)?([\w-]+)", url)
        if m:
            items = titles_greenhouse(m.group(1), get)
            return {"kind": "greenhouse", "items": items, "hash": hashlib.sha1("\n".join(items).encode()).hexdigest()}
        status, html = get(url)
        if status >= 400:
            return {"kind": "http", "items": [], "hash": None, "error": f"HTTP {status}"}
        text, items = titles_generic(html)
        base = "\n".join(items) if items else re.sub(r"\d", "", text)[:20000]  # digits removed: dates/counters
        return {"kind": "page", "items": items, "hash": hashlib.sha1(base.encode("utf-8", "ignore")).hexdigest()}
    except Exception as e:
        return {"kind": "error", "items": [], "hash": None, "error": str(e)[:160]}


def diff(prev, res):
    """Compare one source with its previous state. Returns (status, new, gone)."""
    before, now = set(prev.get("items", [])), set(res["items"])
    new = sorted(now - before) if prev else []
    gone = sorted(before - now) if prev else []
    if res.get("error"):
        return f"error: {res['error']}", new, gone
    if not prev:
        return f"first read ({len(now)} items)", new, gone
    if new or gone:
        return f"CHANGED: +{len(new)} -{len(gone)}", new, gone
    if res["hash"] != prev.get("hash"):
        return "page changed (no new opening detected)", new, gone
    return "unchanged", new, gone


def read_sources(path):
    with open(path, encoding="utf-8") as f:
        return [(r["area"], r["company"], r["link"].strip()) for r in csv.DictReader(f, delimiter=";") if r.get("link")]


def run(sources, state, today, get=http_get, pause=1.0):
    new_state, rows = {}, []
    for area, company, url in sources:
        res = collect(url, get)
        status, new, gone = diff(state.get(url, {}), res)
        rows.append((area, company, url, status, new, gone))
        new_state[url] = {
            "area": area,
            "company": company,
            "hash": res["hash"],
            "items": sorted(res["items"]),
            "date": today,
            "error": res.get("error"),
        }
        time.sleep(pause)  # polite crawling
    return new_state, rows


def render(rows, today):
    n_new = sum(len(r[4]) for r in rows)
    md = [
        f"# Job-board delta - {today}",
        "",
        f"{len(rows)} sources - {n_new} new openings",
        "",
        "| Area | Company | Status | New | Gone |",
        "|---|---|---|---|---|",
    ]
    for area, company, url, status, new, gone in rows:
        if status.startswith(("CHANGED", "first", "error")):
            md.append(
                f"| {area} | [{company}]({url}) | {status} | {' / '.join(new) or '-'} | {' / '.join(gone) or '-'} |"
            )
    return "\n".join(md) + "\n"


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    if len(args) < 2:
        print(__doc__)
        return 2
    out_dir = args[1]
    state_path = os.path.join(out_dir, "state.json")
    state = {}
    if os.path.exists(state_path):
        with open(state_path, encoding="utf-8") as f:
            state = json.load(f)
    today = date.today().isoformat()
    new_state, rows = run(read_sources(args[0]), state, today)
    md = render(rows, today)
    print(md)
    if "--dry" not in argv:
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, f"delta-{today}.md"), "w", encoding="utf-8") as f:
            f.write(md)
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(new_state, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
