#!/usr/bin/env python3
"""Self-tests for the ccevolve hooks, ledger and report.

Run: python3 tests/test_ccevolve.py   (exit 0 = all pass)

Hooks run as subprocesses with JSON on stdin, the way Claude Code invokes them,
against a throwaway project directory set as CLAUDE_PROJECT_DIR. All values
below are synthetic; the "secret" strings are fake.
"""

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS = os.path.join(ROOT, "hooks")
sys.path.insert(0, HOOKS)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from lib import ledger  # noqa: E402
import ledger_report  # noqa: E402

FAILURES = []


def check(name, cond, detail=""):
    print(f"{'ok  ' if cond else 'FAIL'} {name}")
    if not cond:
        FAILURES.append(name)
        print(f"     {detail!r}"[:400])


def run(hook, project, payload, env_extra=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith("CCEVOLVE_")}
    env["CLAUDE_PROJECT_DIR"] = project
    env.update(env_extra or {})
    proc = subprocess.run([sys.executable, os.path.join(HOOKS, hook)], input=json.dumps(payload),
                          capture_output=True, text=True, env=env, timeout=30)
    return proc.returncode, proc.stdout.strip()


def events(project):
    return list(ledger.read(os.path.join(project, ledger.LEDGER_RELPATH)))


def write_transcript(path, n_calls, start=0):
    rows = [{"type": "user", "message": {"role": "user", "content": "please use the advisor"}}]
    for i in range(start, start + n_calls):
        rows.append({"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "text", "text": "consulting"},
            {"type": "server_tool_use", "id": f"srvtoolu_{i:03d}", "name": "advisor", "input": {}}]}})
        rows.append({"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "advisor_tool_result", "tool_use_id": f"srvtoolu_{i:03d}",
             "content": {"type": "advisor_result", "text": "plan"}}]}})
    # Look-alikes that must not count: a client tool named advisor, text mentioning it.
    rows.append({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": "toolu_x", "name": "advisor", "input": {}},
        {"type": "text", "text": "server_tool_use advisor"}]}})
    with open(path, "a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def test_ledger_rejects_unknown_kind_and_bad_lines():
    with tempfile.TemporaryDirectory() as project:
        path = os.path.join(project, ledger.LEDGER_RELPATH)
        check("unknown kind refused", not ledger.append(path, "s", "made_up", "k"))
        check("known kind written", ledger.append(path, "s", "tool_error", "k"))
        with open(path, "a", encoding="utf-8") as f:
            f.write("not json\n{\"kind\": \"made_up\"}\n")
        check("bad lines skipped on read", len(events(project)) == 1, events(project))


def test_advisor_counter():
    with tempfile.TemporaryDirectory() as project:
        transcript = os.path.join(project, "t.jsonl")
        write_transcript(transcript, 4)
        payload = {"session_id": "S1", "transcript_path": transcript, "cwd": project,
                   "hook_event_name": "Stop", "stop_hook_active": False}
        rc, out = run("stop_advisor_counter.py", project, payload)
        recorded = [e for e in events(project) if e["kind"] == "advisor_call"]
        check("advisor: 4 calls recorded (look-alikes ignored)", len(recorded) == 4, recorded)
        check("advisor: crossing 3 notifies once", "called 4 times" in out, out)
        rc, out = run("stop_advisor_counter.py", project, payload)
        check("advisor: same transcript again records nothing", out == "" and
              len([e for e in events(project) if e["kind"] == "advisor_call"]) == 4, out)
        write_transcript(transcript, 2, start=4)
        rc, out = run("stop_advisor_counter.py", project, payload)
        check("advisor: crossing 6 notifies again", "called 6 times" in out, out)
        check("advisor: exit 0", rc == 0, rc)


def test_advisor_threshold_and_opt_out():
    with tempfile.TemporaryDirectory() as project:
        transcript = os.path.join(project, "t.jsonl")
        write_transcript(transcript, 4)
        payload = {"session_id": "S1", "transcript_path": transcript, "cwd": project}
        rc, out = run("stop_advisor_counter.py", project, payload, {"CCEVOLVE_ADVISOR_NOTIFY_AT": "5"})
        check("advisor: below a raised threshold stays quiet", out == "", out)
    with tempfile.TemporaryDirectory() as project:
        transcript = os.path.join(project, "t.jsonl")
        write_transcript(transcript, 4)
        rc, out = run("stop_advisor_counter.py", project,
                      {"session_id": "S1", "transcript_path": transcript, "cwd": project},
                      {"CCEVOLVE_LEDGER": "0"})
        check("CCEVOLVE_LEDGER=0: nothing written", events(project) == [] and out == "", out)


def test_permission_observer_keeps_no_command_line():
    with tempfile.TemporaryDirectory() as project:
        secret = "FAKE_SECRET_VALUE_1234567890"
        rc, out = run("permission_observer.py", project, {
            "session_id": "S1", "cwd": project, "hook_event_name": "PermissionRequest",
            "permission_mode": "default", "tool_name": "Bash",
            "tool_input": {"command": f"API_TOKEN={secret} /usr/bin/git push origin main"}})
        run("permission_observer.py", project, {
            "session_id": "S1", "cwd": project, "hook_event_name": "PermissionDenied",
            "permission_mode": "auto", "tool_name": "WebFetch", "tool_input": {"url": "https://example.com"}})
        run("permission_observer.py", project, {"session_id": "S1", "cwd": project,
                                               "hook_event_name": "PreToolUse", "tool_name": "Bash"})
        ev = events(project)
        check("permission: two events (other events ignored)", len(ev) == 2, ev)
        check("permission: key is tool + program name", ev and ev[0]["key"] == "Bash:git", ev)
        check("permission: outcomes recorded", [e["detail"]["outcome"] for e in ev] == ["asked", "auto_denied"], ev)
        raw = open(os.path.join(project, ledger.LEDGER_RELPATH), encoding="utf-8").read()
        check("permission: no command line or secret in the ledger", secret not in raw and "push" not in raw, raw)
        check("permission: no decision returned", out == "", out)


def test_failure_detector():
    with tempfile.TemporaryDirectory() as project:
        base = {"session_id": "S1", "cwd": project, "hook_event_name": "PostToolUseFailure",
                "tool_name": "Bash", "tool_input": {"command": "npm test"},
                "error": "Exit code 1\nError: Cannot find module '/home/u/app/express' token abcdefghijklmnopqrstuvwx12"}
        rc, out = run("posttoolusefailure_error_detector.py", project, base)
        check("failure: first occurrence quiet", out == "", out)
        rc, out = run("posttoolusefailure_error_detector.py", project, dict(base, error=base["error"].replace("12", "99")))
        ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"] if out else ""
        check("failure: second occurrence adds context for Claude", "2回目" in ctx and "計算" in ctx, out)
        key = events(project)[0]["key"]
        check("failure: key normalized (path, token, number)", "<path>" in key and "<token>" in key
              and "abcdefghij" not in key, key)
        run("posttoolusefailure_error_detector.py", project, dict(base, is_interrupt=True))
        run("posttoolusefailure_error_detector.py", project, dict(base, hook_event_name="PostToolUse"))
        check("failure: interrupts and other events ignored", len(events(project)) == 2, events(project))


def test_keys_from_review():
    """Review findings: ordinary long words stay readable; cd-prefixed commands key on the real program."""
    import permission_observer as po
    import posttoolusefailure_error_detector as fd
    check("error key: long option without digits is not masked",
          "--untracked-files=allxyz" in fd.normalize_error("Exit code 2\nerror: unknown option --untracked-files=allxyz"),
          fd.normalize_error("Exit code 2\nerror: unknown option --untracked-files=allxyz"))
    check("error key: token-like string with digits is masked",
          "<token>" in fd.normalize_error("Exit code 1\nbad credential ghx_ab12cd34ef56gh78ij90"),
          fd.normalize_error("Exit code 1\nbad credential ghx_ab12cd34ef56gh78ij90"))
    cases = {
        "cd /tmp/repo && git push": "Bash:git",
        "(cd x; make)": "Bash:make",
        "cd x": "Bash:cd",
        "pushd a; FOO=1 npm test": "Bash:npm",
        "sudo rm -rf x": "Bash:sudo",
    }
    for cmd, want in cases.items():
        got = po.prompt_key("Bash", {"command": cmd})
        check(f"permission key: {cmd!r} -> {want}", got == want, got)


def test_report():
    with tempfile.TemporaryDirectory() as project:
        path = os.path.join(project, ledger.LEDGER_RELPATH)
        for _ in range(3):
            ledger.append(path, "S1", "permission_prompt", "Bash:curl")
        ledger.append(path, "S1", "tool_error", "Bash: once")
        ledger.append(path, "S1", "advisor_call", "advisor", event_id="a")
        ledger.append(path, "S2", "advisor_call", "advisor", event_id="b")
        old = {"ts": (datetime.now(timezone.utc) - timedelta(days=90)).isoformat(), "session_id": "S0",
               "kind": "permission_prompt", "key": "Bash:old", "id": None, "detail": {}}
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(old) + "\n")
        r = ledger_report.report(path, days=30, min_count=3)
        keys = [c["key"] for c in r["candidates"]]
        check("report: key seen 3 times is a candidate", keys == ["Bash:curl"], r["candidates"])
        check("report: events outside the window ignored", "Bash:old" not in keys and r["by_kind"]["permission_prompt"] == 3, r)
        check("report: advisor calls per session", r["advisor_calls_per_session"] == {"S1": 1, "S2": 1}, r)


def main():
    for t in sorted(k for k in globals() if k.startswith("test_")):
        globals()[t]()
    if FAILURES:
        print(f"\n{len(FAILURES)} failure(s)")
        return 1
    print("\nall tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
