#!/usr/bin/env python3
"""
fimwatch - a tiny file integrity monitor.

Takes a hash+mtime+size snapshot of a directory tree, then lets you compare
a later snapshot against it to see what changed. This is the same basic
idea behind tools like Tripwire/AIDE, just small enough to actually read
and modify in an afternoon.

Usage:
    python3 fimwatch.py baseline /etc -o baseline.json
    python3 fimwatch.py check /etc -b baseline.json
    python3 fimwatch.py check /etc -b baseline.json --csv changes.csv
"""

import argparse
import fnmatch
import hashlib
import json
import os
import sys
import time

DEFAULT_IGNORES = [".git", "__pycache__", "*.pyc", ".DS_Store"]


def should_ignore(name, patterns):
    return any(fnmatch.fnmatch(name, pat) for pat in patterns)


def hash_file(path, algo="sha256", chunk_size=65536):
    h = hashlib.new(algo)
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                h.update(chunk)
    except (OSError, PermissionError):
        return None
    return h.hexdigest()


def walk_files(root, ignores):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not should_ignore(d, ignores)]
        for name in filenames:
            if should_ignore(name, ignores):
                continue
            yield os.path.join(dirpath, name)


def snapshot(root, algo, ignores):
    root = os.path.abspath(root)
    entries = {}
    skipped = 0
    for path in walk_files(root, ignores):
        try:
            st = os.stat(path)
        except OSError:
            skipped += 1
            continue
        digest = hash_file(path, algo)
        if digest is None:
            skipped += 1
            continue
        rel = os.path.relpath(path, root)
        entries[rel] = {"size": st.st_size, "mtime": st.st_mtime, "hash": digest}
    return {
        "root": root,
        "algo": algo,
        "created": time.time(),
        "file_count": len(entries),
        "files": entries,
    }, skipped


def cmd_baseline(args):
    data, skipped = snapshot(args.directory, args.algo, DEFAULT_IGNORES + args.ignore)
    with open(args.output, "w") as f:
        json.dump(data, f, indent=2)
    print(f"[*] Baseline captured: {data['file_count']} file(s), {skipped} skipped (unreadable)")
    print(f"[*] Written to {args.output}")


def cmd_check(args):
    with open(args.baseline) as f:
        base = json.load(f)

    current, skipped = snapshot(args.directory, base["algo"], DEFAULT_IGNORES + args.ignore)

    old_files = base["files"]
    new_files = current["files"]

    added = sorted(set(new_files) - set(old_files))
    removed = sorted(set(old_files) - set(new_files))
    modified = sorted(
        p for p in (set(old_files) & set(new_files))
        if old_files[p]["hash"] != new_files[p]["hash"]
    )

    print(f"[*] Comparing {args.directory} against baseline from {base.get('root', '?')}")
    print(f"[*] {len(added)} added, {len(removed)} removed, {len(modified)} modified, "
          f"{skipped} unreadable\n")

    for p in added:
        print(f"  + {p}")
    for p in removed:
        print(f"  - {p}")
    for p in modified:
        old_size = old_files[p]["size"]
        new_size = new_files[p]["size"]
        print(f"  * {p}  (size {old_size} -> {new_size})")

    if not (added or removed or modified):
        print("[*] No changes detected.")

    if args.csv:
        import csv
        with open(args.csv, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["status", "path", "old_size", "new_size"])
            for p in added:
                writer.writerow(["added", p, "", new_files[p]["size"]])
            for p in removed:
                writer.writerow(["removed", p, old_files[p]["size"], ""])
            for p in modified:
                writer.writerow(["modified", p, old_files[p]["size"], new_files[p]["size"]])
        print(f"\n[*] Full change report written to {args.csv}")

    if added or removed or modified:
        sys.exit(1)  # non-zero exit makes this easy to hook into a cron job / CI check


def main():
    ap = argparse.ArgumentParser(description="Small file integrity monitor (baseline + check).")
    sub = ap.add_subparsers(dest="command", required=True)

    p_base = sub.add_parser("baseline", help="capture a baseline snapshot of a directory")
    p_base.add_argument("directory")
    p_base.add_argument("-o", "--output", default="baseline.json", help="baseline file to write")
    p_base.add_argument("--algo", default="sha256", help="hash algorithm (default: sha256)")
    p_base.add_argument("--ignore", action="append", default=[],
                         help="extra glob pattern to ignore (repeatable)")
    p_base.set_defaults(func=cmd_baseline)

    p_check = sub.add_parser("check", help="compare a directory against a baseline")
    p_check.add_argument("directory")
    p_check.add_argument("-b", "--baseline", required=True, help="baseline file from 'baseline'")
    p_check.add_argument("--csv", metavar="FILE", help="write the full change report to CSV")
    p_check.add_argument("--ignore", action="append", default=[],
                          help="extra glob pattern to ignore (repeatable)")
    p_check.set_defaults(func=cmd_check)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
