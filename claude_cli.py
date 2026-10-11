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
