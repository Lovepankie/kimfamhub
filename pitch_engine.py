"""
Project "why join" pitch engine.

A background service that keeps a freshly-cooked, AI-generated enticement line
per project — built from each project's live figures and latest update — so the
"why join" bubble in the app shows compelling, figure-led copy instead of static
text.

Model chain (cheap only, never Sonnet+): DeepSeek -> Claude Haiku (CLI) ->
Gemini Flash -> static category fallback. Results are cached to a JSON file and
regenerated every few hours by a daemon thread started at app startup.
"""
import os
import json
import time
import threading
import logging

log = logging.getLogger("pitch")

_DIR = os.path.dirname(__file__)
_CACHE = os.path.join(_DIR, "data", "project_pitches.json")
_LOCK = os.path.join(_DIR, "data", ".pitch.lock")
REFRESH_SECONDS = 6 * 3600  # re-cook every 6 hours

# Static fallback, mirrors the frontend category pitches (used only if every
# model fails — the app should essentially never show these).
_FALLBACK = {
    "Farming & Agriculture": "A hands-on farming venture with steady produce income. Bring labour, oversight, or capital and share the harvest.",
    "Business Ventures": "A cash-generating service business. Add capital or commercial muscle and earn from every shift.",
    "Unit Trusts": "Grow your money in professionally managed funds. Join with capital and let it compound.",
    "Real Estate": "Build long-term family wealth in property. Contribute capital or oversight and own a piece.",
}


def _static(p):
    return _FALLBACK.get(p.get("category"), "Be part of this venture early. Add your skills, capital, or oversight and share in the returns.")


def _project_brief(p):
    lines = [
        f"Project: {p.get('name')}",
        f"Category: {p.get('category')}",
        f"Status: {p.get('status')}",
        f"Headline: {p.get('headline')}",
    ]
    for d in (p.get("data") or [])[:10]:
        lines.append(f"- {d.get('label')}: {d.get('value')}")
    upd = p.get("update") or {}
    if upd.get("text"):
        lines.append(f"Latest update ({upd.get('date')}): {upd['text'][:500]}")
    return "\n".join(lines)


def _prompt(p):
    return (
        "You write a punchy, exciting one-liner to entice a member of a Ugandan family "
        "investment club to JOIN this venture. Emphasise upside, momentum, and the chance to "
        "get in early.\n\n"
        "HARD RULE ON NUMBERS: use ONLY numbers that appear verbatim in the DATA below. Do NOT "
        "invent, estimate, extrapolate, annualise, or compute any figure, percentage, growth "
        "rate, multiple, or projected return. If a number is not written in the data, do not "
        "state it. If the data has no compelling number, write an enticing qualitative line "
        "with NO numbers at all rather than making one up. Never fabricate returns or growth "
        "rates.\n\n"
        "Lead with the single most compelling REAL figure that IS in the data (money, rate, "
        "yield, count) if one exists. Two sentences maximum, under 240 characters. No em-dashes "
        "or en-dashes, use commas or full stops. No markdown, no surrounding quotes, no "
        "preamble. Output ONLY the pitch.\n\n"
        f"DATA:\n{_project_brief(p)}\n\nPITCH:"
    )


def _via_deepseek(prompt):
    key = os.getenv("DEEPSEEK_API_KEY", "")
    if not key:
        return ""
    try:
        import requests
        r = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": "deepseek-chat",
                  "messages": [{"role": "user", "content": prompt}],
                  "max_tokens": 160, "temperature": 0.7},
            timeout=30,
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
        log.warning("deepseek http %s", r.status_code)
    except Exception as e:
        log.warning("deepseek error: %s", e)
    return ""


def _via_haiku(prompt):
    import subprocess
    env = dict(os.environ)
    env.setdefault("HOME", "/root")
    try:
        out = subprocess.run(
            ["claude", "-p", prompt, "--model", "haiku"],
            capture_output=True, timeout=60, env=env,
        )
        if out.returncode == 0:
            import claude_cli
            return claude_cli.usable(out.stdout.decode())
    except Exception as e:
        log.warning("haiku error: %s", e)
    return ""


def _via_gemini(prompt):
    key = os.getenv("GEMINI_API_KEY", "")
    if not key:
        return ""
    try:
        from google import genai
        resp = genai.Client(api_key=key).models.generate_content(
            model="gemini-2.5-flash", contents=prompt)
        return (resp.text or "").strip()
    except Exception as e:
        log.warning("gemini error: %s", e)
    return ""


def _clean(text):
    if not text:
        return ""
    t = text.replace("—", "-").replace("–", "-").strip()
    t = t.strip('"').strip("'").strip()
    # drop any accidental leading label
    if t.lower().startswith("pitch:"):
        t = t[6:].strip()
    return t[:260].strip()


def generate_pitch(p):
    prompt = _prompt(p)
    for fn in (_via_deepseek, _via_haiku, _via_gemini):
        t = _clean(fn(prompt))
        if t and len(t) > 20:
            return t, fn.__name__.replace("_via_", "")
    return _static(p), "static"


def generate_all(projects):
    out = {}
    for p in projects:
        try:
            pitch, src = generate_pitch(p)
        except Exception as e:
            log.warning("pitch gen failed for %s: %s", p.get("id"), e)
            pitch, src = _static(p), "static"
        out[p["id"]] = {"pitch": pitch, "src": src, "ts": int(time.time())}
    _write(out)
    return out


def _write(data):
    os.makedirs(os.path.dirname(_CACHE), exist_ok=True)
    tmp = _CACHE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, _CACHE)


def load():
    try:
        with open(_CACHE) as f:
            return json.load(f)
    except Exception:
        return {}


def _is_stale():
    try:
        return (time.time() - os.path.getmtime(_CACHE)) > REFRESH_SECONDS
    except Exception:
        return True


def cook_once(projects_fn, force=False):
    """Cook all pitches if stale. A non-blocking file lock ensures only one
    gunicorn worker does the work."""
    import fcntl
    os.makedirs(os.path.dirname(_LOCK), exist_ok=True)
    f = open(_LOCK, "w")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except Exception:
        f.close()
        return  # another worker is cooking
    try:
        if force or _is_stale():
            log.info("Cooking project pitches...")
            n = len(generate_all(projects_fn()))
            log.info("Cooked %d project pitches.", n)
    finally:
        try:
            fcntl.flock(f, fcntl.LOCK_UN)
        except Exception:
            pass
        f.close()


def start_background(projects_fn):
    """Daemon loop: cook on startup, then re-cook every REFRESH_SECONDS."""
    def loop():
        # small delay so the app finishes booting first
        time.sleep(8)
        while True:
            try:
                cook_once(projects_fn)
            except Exception as e:
                log.warning("cook loop error: %s", e)
            time.sleep(REFRESH_SECONDS)
    threading.Thread(target=loop, daemon=True, name="pitch-cook").start()
    log.info("Pitch engine background cook started.")
