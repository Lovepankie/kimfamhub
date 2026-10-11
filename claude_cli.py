"""claude_cli.py: the Claude Code CLI prints a usage-limit or login notice on stdout and exits 0, so a caller that
trusts 'exit 0 and some text' treats "You've hit your weekly limit" as the model's answer. On 11 Oct 2026 that made
meeting processing fail with "Couldn't extract minutes" and stopped every fallback (DeepSeek, Groq) from running.
usable() is the single check every call site uses: a notice is a failure, so the fallback chain runs."""
import re

_NOTICE = re.compile(
    r"(hit your (weekly |daily |monthly |5-hour |usage )?limit|usage limit|weekly limit reached|limit reached|"
    r"not logged in|please run /login|invalid api key|credit balance is too low|oauth token (has )?expired|"
    r"rate limit exceeded|you.ve reached your)", re.I)


def is_notice(text):
    """True when `text` is a CLI limit, login or credit notice rather than a model answer. Notices are short."""
    t = (text or "").strip()
    if not t or t[0] in "{[`":
        return False          # JSON (or a fenced block) is an answer, even one that mentions a limit
    return len(t) < 400 and bool(_NOTICE.search(t))


def usable(text):
    """-> the stripped text when it is a real answer, else ''."""
    t = (text or "").strip()
    return "" if (not t or is_notice(t)) else t


def tokens(env=None):
    """OAuth tokens to try, in order: the main account, then the backup (CLAUDE_CODE_OAUTH_TOKEN_2). Values, never logged."""
    import os
    env = os.environ if env is None else env
    out = []
    for k in ("CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN_2"):
        v = (env.get(k) or "").strip()
        if v and v not in out:
            out.append(v)
    return out or [None]          # None: no token configured, use whatever the CLI is logged in as


def complete(prompt, model="haiku", timeout=120, env=None, runner=None):
    """One Claude CLI completion that falls over to the backup account. A limit or login notice on one account counts as a
    failure and the next account is tried; '' when every account fails (the caller then goes to DeepSeek or Groq).
    `runner(args, env, timeout) -> (returncode, stdout)` is injectable for tests. Blocking: async callers use
    asyncio.to_thread."""
    import os
    import subprocess
    import logging

    def _run(args, e, t):
        r = subprocess.run(args, capture_output=True, text=True, timeout=t, env=e)
        return r.returncode, r.stdout

    run = runner or _run
    base = dict(os.environ if env is None else env)
    base["HOME"] = "/root"
    for i, tok in enumerate(tokens(base)):
        e = dict(base)
        if tok:
            e["CLAUDE_CODE_OAUTH_TOKEN"] = tok
        try:
            rc, out = run(["claude", "-p", prompt, "--model", model], e, timeout)
        except Exception as ex:
            logging.getLogger("main").warning("claude CLI account %d failed: %s", i + 1, type(ex).__name__)
            continue
        ans = usable(out)
        if rc == 0 and ans:
            return ans
        logging.getLogger("main").warning("claude CLI account %d gave no usable answer (rc=%s): %.80s", i + 1, rc, (out or "").strip())
    return ""
