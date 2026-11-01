#!/usr/bin/env python3
"""Facts about the throwaway scripts Claude wrote, read from Claude Code transcripts.

Usage: script_facts.py --out DIR [--days N] [--projects DIR] [--methods write,heredoc,redirect,cp,git-show]

A throwaway script is a .py/.sh/.bash/.mjs/.js file created under /tmp/, a `.claude/tmp/` folder or
~/.claude/jobs/<id>/tmp/. Creation methods:
  write     the Write tool
  heredoc   cat/tee > file <<EOF (the body is in the transcript)
  redirect  any other `> file`, such as a sed copy of an earlier script
  cp        cp src file
  git-show  git show rev:path > file (a snapshot of real code, not authored)

For each script: session, path, methods, creation time, description (docstring or first comment), lines,
runs (other Bash calls in the same session that run it from its own folder, in any order), and the paths passed to it.
Bodies the transcript holds (write, heredoc) are written to DIR/scripts/<id>-<name>, and the facts to
DIR/facts.json. Facts only: grouping scripts by purpose is left to a reader (see the
promote-to-computation skill).

The window is --days, else CCEVOLVE_TRANSCRIPT_DAYS, else 60 days. Files under DIR are not counted, so a
second run does not count the first run's output. DIR must be outside any git repository: the bodies are
copied from transcripts and may hold anything a session wrote, so they must not be committed by accident.
For the same reason a new DIR is made readable by its owner only, and every file written is mode 0600.
Exit 2 on a bad argument or variable.
"""

import argparse
import collections
import datetime as dt
import glob
import json
import os
import re
import subprocess
import sys

HOME = os.path.expanduser("~")
EXT = re.compile(r"\.(py|sh|mjs|js|bash)$")
TEMP = re.compile(r"^(/tmp/|.*/\.claude/tmp/|" + re.escape(HOME) + r"/\.claude/jobs/[^/]+/tmp/)")
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
METHODS = ("write", "heredoc", "redirect", "cp", "git-show")
DEFAULT_DAYS = 60


def ts_of(rec):
    t = rec.get("timestamp")
    if not t:
        return None
    try:
        return dt.datetime.fromisoformat(t.replace("Z", "+00:00"))
    except ValueError:
        return None


def resolve(path, cwd, env):
    """Expand $VAR/${VAR}/~ and make a relative path absolute against the last `cd` of the command."""
    path = path.strip("'\"")
    path = re.sub(r"\$\{?(\w+)\}?", lambda m: env.get(m.group(1), m.group(0)), path)
    if path.startswith("~"):
        path = HOME + path[1:]
    if not path.startswith("/") and cwd:
        path = os.path.normpath(os.path.join(cwd, path))
    return path


def creations(cmd):
    """Yield (method, path, body) for files a Bash command creates. Tracks `cd` and VAR= in order."""
    env, cwd = {}, None
    lines = cmd.split("\n")
    i = 0
    while i < len(lines):
        stmt = lines[i]
        body = None
        # `<<WORD`, not a here-string (`<<<`) or a shift (`1<<3`); a delimiter that never comes is no heredoc
        hd = re.search(r"(?<!<)<<(?!<)-?\s*['\"]?([A-Za-z_]\w*)['\"]?", stmt)
        if hd:  # keep the heredoc body with its statement
            delim = hd.group(1)
            j = i + 1
            while j < len(lines) and lines[j].strip() != delim:
                j += 1
            if j < len(lines):
                body = "\n".join(lines[i + 1:j])
                i = j
        for part in re.split(r"&&|;|\|\|", stmt):
            part = part.strip()
            m = re.match(r"^(?:export\s+)?(\w+)=(\S+)$", part)
            if m:
                env[m.group(1)] = resolve(m.group(2), cwd, env)
                continue
            m = re.match(r"^cd\s+(\S+)", part)
            if m:
                cwd = resolve(m.group(1), cwd, env)
                continue
            m = re.match(r"^cp\s+(?:-\w+\s+)*(\S+)\s+(\S+)$", part)
            if m:
                yield "cp", resolve(m.group(2), cwd, env), None
                continue
            for r in re.finditer(r"(?<![0-9&])>\s*(\S+)", part):
                target = resolve(r.group(1), cwd, env)
                if not EXT.search(target):
                    continue
                if re.match(r"^(cat|tee)\b", part) and body is not None:
                    yield "heredoc", target, body
                elif re.match(r"^git\s+(?:-C\s+\S+\s+)?show\b", part):
                    yield "git-show", target, None
                else:
                    yield "redirect", target, None
            m = re.match(r"^tee\s+(?:-a\s+)?(\S+)", part)
            if m and body is not None:
                target = resolve(m.group(1), cwd, env)
                if EXT.search(target):
                    yield "heredoc", target, body
        i += 1


def describe(body):
    for line in (body or "").splitlines():
        s = line.strip()
        if not s or s.startswith("#!"):
            continue
        if s.startswith('"""') or s.startswith("'''"):
            t = s.strip("\"' ")
            if t:
                return t[:160]
            continue
        if s.startswith("#") or s.startswith("//"):
            return s.lstrip("#/ ").strip()[:160]
        return ""
    return ""


def window_days(arg):
    """--days, else CCEVOLVE_TRANSCRIPT_DAYS, else 60."""
    if arg is not None:
        return arg
    raw = os.environ.get("CCEVOLVE_TRANSCRIPT_DAYS", "").strip()
    if not raw:
        return DEFAULT_DAYS
    if not raw.isdigit() or int(raw) < 1:
        raise ValueError(f"CCEVOLVE_TRANSCRIPT_DAYS must be a positive whole number of days, not {raw!r}")
    return int(raw)


def repo_root(path):
    """The git repository holding path (or its nearest existing parent), or None."""
    d = os.path.abspath(path)
    while not os.path.isdir(d):
        d = os.path.dirname(d)
    r = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=d, capture_output=True, text=True)
    if r.returncode == 0:
        return r.stdout.strip()
    if "not a git repository" in r.stderr:
        return None
    raise ValueError(f"cannot tell whether --out is inside a git repository: {r.stderr.strip()[:200]}")


def collect(projects, cutoff, methods, out_dir):
    scripts, bash_by_session = {}, collections.defaultdict(list)
    oldest, files_read = None, 0
    out_prefix = os.path.realpath(out_dir) + os.sep
    for jl in glob.glob(os.path.join(projects, "**", "*.jsonl"), recursive=True):
        sess = (UUID.findall(jl) or [jl])[0]  # subagent transcripts count for their parent session
        try:
            fh = open(jl, encoding="utf-8", errors="replace")
        except OSError:
            continue
        files_read += 1
        with fh:
            for line in fh:
                if '"timestamp"' not in line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                t = ts_of(rec)
                if t is None or t < cutoff:
                    continue
                if oldest is None or t < oldest:
                    oldest = t
                content = (rec.get("message") or {}).get("content")
                if not isinstance(content, list):
                    continue
                for b in content:
                    if not isinstance(b, dict) or b.get("type") != "tool_use":
                        continue
                    inp = b.get("input") or {}
                    found = []
                    if b.get("name") == "Write":
                        found.append(("write", str(inp.get("file_path", "")), str(inp.get("content", ""))))
                    elif b.get("name") == "Bash":
                        cmd = str(inp.get("command", ""))
                        bash_by_session[sess].append(cmd)
                        found.extend(creations(cmd))
                    for method, fp, body in found:
                        if method not in methods or not EXT.search(fp) or not TEMP.search(fp):
                            continue
                        if os.path.realpath(fp).startswith(out_prefix):
                            continue
                        f = scripts.setdefault((sess, fp), {
                            "session": sess, "path": fp, "basename": os.path.basename(fp),
                            "methods": [], "created": t.isoformat()[:16], "writes": 0,
                            "description": "", "lines": None, "body": None,
                        })
                        f["writes"] += 1
                        if method not in f["methods"]:
                            f["methods"].append(method)
                        if body:
                            f["body"] = body
                            f["lines"] = body.count("\n") + 1
                            f["description"] = describe(body) or f["description"]
    for f in scripts.values():
        count_runs(f, bash_by_session.get(f["session"], ()))
    return scripts, oldest, files_read


def count_runs(f, commands):
    """Bash calls in the same session that run the script from its own folder, other than the calls that
    create it (a plugin's script with the same name does not count), and the paths passed to it. Order is not
    checked: a run before the script was rewritten at the same path counts too."""
    base, folder = f["basename"], os.path.dirname(f["path"])
    pat = re.compile(r"(?<![\w.-])" + re.escape(base) + r"(?![\w.-])")
    runs, argpaths = 0, collections.Counter()
    for cmd in commands:
        if not pat.search(cmd):
            continue
        env = {m.group(1): m.group(2).strip("'\"") for m in re.finditer(r"(?:^|[\s;&])(\w+)=(\S+)", cmd)}
        expanded = re.sub(r"\$\{?(\w+)\}?", lambda m: env.get(m.group(1), m.group(0)), cmd).replace("~", HOME)
        if f["path"] not in expanded and folder not in expanded:
            continue
        if any(p == f["path"] for _, p, _ in creations(cmd)):
            continue
        if not re.search(r"\b(python3?|bash|sh|node|uv run)\b[^\n]*" + re.escape(base), cmd):
            continue
        runs += 1
        tail = cmd[cmd.find(base) + len(base):].split("\n")[0]
        for tok in re.findall(r"(?:^|\s)(/[^\s'\"]+|~/[^\s'\"]+|\.claude/[^\s'\"]+)", tail):
            argpaths[UUID.sub("<uuid>", tok)] += 1
    f["runs"] = runs
    f["arg_paths"] = [p for p, _ in argpaths.most_common(5)]


def private(path):
    """Open path for writing as mode 0600, also when it already exists."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(fd, 0o600)
    return os.fdopen(fd, "w", encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--days", type=int, help="window in days (default: CCEVOLVE_TRANSCRIPT_DAYS, else 60)")
    ap.add_argument("--out", required=True, help="output directory, outside any git repository")
    ap.add_argument("--projects", default=os.path.join(HOME, ".claude", "projects"))
    ap.add_argument("--methods", default=",".join(METHODS))
    a = ap.parse_args(argv)
    try:
        days = window_days(a.days)
        if days < 1:
            raise ValueError("--days must be 1 or more")
        methods = set(a.methods.split(","))
        if not methods <= set(METHODS):
            raise ValueError(f"unknown method(s): {', '.join(sorted(methods - set(METHODS)))}")
        root = repo_root(a.out)
        if root:
            raise ValueError(f"--out is inside a git repository ({root}); script bodies copied from transcripts "
                             "must not be committed by accident")
    except ValueError as e:
        print(f"script_facts: {e}", file=sys.stderr)
        return 2

    now = dt.datetime.now(dt.timezone.utc)
    scripts, oldest, files_read = collect(a.projects, now - dt.timedelta(days=days), methods, a.out)
    os.makedirs(a.out, mode=0o700, exist_ok=True)
    os.makedirs(os.path.join(a.out, "scripts"), mode=0o700, exist_ok=True)
    rows = []
    for i, f in enumerate(sorted(scripts.values(), key=lambda f: f["created"])):
        sid = f"s{i:04d}"
        if f["body"]:
            with private(os.path.join(a.out, "scripts", f"{sid}-{f['basename']}")) as w:
                w.write(f["body"])
        rows.append({"id": sid, **{k: v for k, v in f.items() if k != "body"}, "body_saved": bool(f["body"])})
    with private(os.path.join(a.out, "facts.json")) as w:
        json.dump(rows, w, ensure_ascii=False, indent=1)

    span = (now - oldest).days if oldest else 0
    print(f"Window: transcripts under {a.projects} on this machine ({files_read} files). Asked for {days} days; "
          f"the oldest record in it is {oldest.date() if oldest else '-'} (about {span} days). "
          "Other machines and other users are not included.")
    print("methods:", ",".join(sorted(methods)))
    print("scripts:", len(rows), "sessions:", len({r["session"] for r in rows}))
    print("by method:", dict(collections.Counter(m for r in rows for m in r["methods"])))
    print("bodies saved:", sum(r["body_saved"] for r in rows))
    print("facts:", os.path.join(a.out, "facts.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
