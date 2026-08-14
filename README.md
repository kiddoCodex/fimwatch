# fimwatch

A small file integrity monitor. Snapshot a directory's file hashes, sizes,
and mtimes, then check back later to see exactly what got added, removed,
or modified. Same basic idea as Tripwire or AIDE, just small enough that
you can actually read the whole thing in one sitting.

No external dependencies.

## Usage

Capture a baseline before you care about changes (before deploying, before
handing off a box, before an investigation starts):

```
python3 fimwatch.py baseline /etc -o baseline.json
```

Later, check for drift:

```
python3 fimwatch.py check /etc -b baseline.json
```

```
[*] Comparing /etc against baseline from /etc
[*] 1 added, 1 removed, 1 modified, 0 unreadable

  + cron.d/weird-job
  - motd
  * passwd  (size 2210 -> 2254)
```

`check` exits non-zero if anything changed, so it's easy to drop into a
cron job or CI step and get alerted only when something's actually
different.

Dump the full report to CSV instead of (or in addition to) the console:

```
python3 fimwatch.py check /etc -b baseline.json --csv changes.csv
```

Ignore extra paths beyond the built-in defaults (`.git`, `__pycache__`,
`*.pyc`, `.DS_Store`):

```
python3 fimwatch.py baseline ./project -o baseline.json --ignore "*.log" --ignore "node_modules"
```

## How it works

For every file under the target directory, `fimwatch` records size, mtime,
and a SHA-256 hash. `check` re-walks the directory, hashes everything
again, and diffs the two file lists. Files it can't read (permissions,
broken symlinks, etc.) are counted as skipped rather than causing a crash.

## Limitations

This isn't a replacement for a real EDR/HIDS agent - there's no real-time
watching, no tamper protection on the baseline file itself, and hashing a
big tree takes as long as it takes (no incremental indexing). It's meant
for "did anything change since I last checked" on a directory you care
about, run by hand or from cron.

## License

MIT, see LICENSE.
