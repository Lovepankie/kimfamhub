"""payment_proof.py: strict, pure rules for closing an action from a payment proof (ADR-037).

Nothing here touches the database, the network or the model. The model only PROPOSES facts
(validate_facts checks each against the document text); decide() then applies five rules and a few
extra safeguards. Any doubt means "do not close": the caller then behaves exactly as before (comment only).
"""
import re
from datetime import date, datetime

CHECKS = ("succeeded", "amount_matches", "payer_is_owner", "on_time", "recipient_ok")

_CHECK_LABELS = {
    "succeeded": "the proof says the transfer succeeded",
    "amount_matches": "the amount equals the action amount",
    "payer_is_owner": "the payer is the action owner",
    "on_time": "the proof date is on or before the deadline",
    "recipient_ok": "the recipient is a member (and the named person, if the action names one)",
}

_CCY = r"(?:UGX|USH|UShs?|Shs?\.?|UG\s?X)"
_NUM = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
_AMOUNT_A = re.compile(r"(?<![A-Za-z])" + _CCY + r"\s*[:.]?\s*(" + _NUM + r")(?![\d,])", re.I)
_AMOUNT_B = re.compile(r"(?<![\d,.])(" + _NUM + r")\s*(?:/=|" + _CCY + r"(?![A-Za-z]))", re.I)
# "UGX 4m", "UGX 4 million" and space grouped "UGX 4 000 000" are not read: no guess, so no auto-close
_SCALED_RE = re.compile(r"(?<![A-Za-z])" + _CCY + r"\s*[:.]?\s*(?:\d+(?:\.\d+)?\s?(?:m|k|mn|bn|million|thousand|billion)\b|\d{1,3}(?:[ \u00a0]\d{3})+)", re.I)
_NOT_A_PAYMENT_AMOUNT = re.compile(r"(fee|fees|charge|charges|balance|tax|duty|commission|levy|excise)\W{0,12}$", re.I)


def _to_int(num):
    """'4,000,000' -> 4000000; '4000000.00' -> 4000000; '12.5' -> None (not whole shillings)."""
    s = num.replace(",", "")
    try:
        if "." in s:
            whole, frac = s.split(".", 1)
            if frac.strip("0"):
                return None
            s = whole
        v = int(s)
    except ValueError:
        return None
    return v if v > 0 else None


def parse_amount(text):
    """The single clear UGX amount in `text`, else None. 'UGX 4,000,000', 'UGX4000000', '4,000,000/=' and
    '4,000,000 UGX' all count. The same figure repeated is one amount; two different figures, or none, give None."""
    found = _amounts(text)
    return next(iter(found)) if found is not None and len(found) == 1 else None


def _amounts(text, skip_fees=False):
    """The set of currency-adjacent whole-shilling amounts in `text`; None when any is unreadable (scaled, space
    grouped, fractional). A bare year before the currency is not an amount. skip_fees drops figures that follow
    fee, charge, balance, tax and similar words (a statement lists those next to the payment)."""
    text = text or ""
    if _SCALED_RE.search(text):
        return None
    found = set()
    for rx in (_AMOUNT_A, _AMOUNT_B):
        for m in rx.finditer(text):
            raw = m.group(1)
            if rx is _AMOUNT_B and re.fullmatch(r"(19|20)\d\d", raw):
                continue                                # "Fees 2026 UGX ..." : a year, not an amount
            if skip_fees and _NOT_A_PAYMENT_AMOUNT.search(text[max(0, m.start() - 30):m.start()]):
                continue
            v = _to_int(raw)
            if v is None:
                return None
            found.add(v)
    return found


def _names(members):
    out = []
    for m in members or []:
        n = (m.get("name") if isinstance(m, dict) else m) or ""
        n = str(n).strip()
        if n:
            out.append(n)
    return out


def members_in(text, members):
    """Member names that appear in `text` as whole words (case-insensitive), in member-list order."""
    t = text or ""
    return [n for n in _names(members) if re.search(r"(?<![A-Za-z])" + re.escape(n) + r"(?![A-Za-z])", t, re.I)]


def match_member(name, members):
    """The Hub member a payer or recipient name refers to, else None. Whole-word match on the member's name, so
    'Alpha Surname' matches Alpha and 'Alphabet' does not. Two different members in one string is ambiguous: None."""
    hit = members_in(name, members)
    return hit[0] if len(hit) == 1 else None


def _as_date(v):
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        try:
            return datetime.strptime(v.strip()[:10], "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


_MONTHS = {m: i for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}
_MON = r"(Jan[a-z]*|Feb[a-z]*|Mar[a-z]*|Apr[a-z]*|May|Jun[a-z]*|Jul[a-z]*|Aug[a-z]*|Sep[a-z]*|Oct[a-z]*|Nov[a-z]*|Dec[a-z]*)"
_D_ISO = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
_D_NUM = re.compile(r"(?<![\d./-])(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})(?!\d)")
_D_DMY = re.compile(r"(?<!\d)(\d{1,2})(?:st|nd|rd|th)?[\s,.-]+" + _MON + r"\.?[\s,.-]+(\d{4})(?!\d)", re.I)
_D_MDY = re.compile(_MON + r"\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})(?!\d)", re.I)


def parse_dates(text):
    """Every date printed in `text` as real dates. Numeric dates are read day first (dd/mm/yyyy, the local
    convention); the caller also refuses a date in the future, which rules out the month-first reading for
    recent proofs. Month names and ISO dates are unambiguous."""
    out = set()

    def add(y, mo, d):
        try:
            out.add(date(int(y), int(mo), int(d)))
        except ValueError:
            pass
    t = text or ""
    for y, mo, d in _D_ISO.findall(t):
        add(y, mo, d)
    for d, mo, y in _D_NUM.findall(t):
        add(y, mo, d)
    for d, mon, y in _D_DMY.findall(t):
        add(y, _MONTHS.get(mon[:3].lower(), 0), d)
    for mon, d, y in _D_MDY.findall(t):
        add(y, _MONTHS.get(mon[:3].lower(), 0), d)
    return out


def _name_in_text(name, text):
    """True when a word of the proposed name (3+ letters) appears in the document text as a whole word."""
    words = re.findall(r"[A-Za-z]{3,}", name or "")
    return any(re.search(r"(?<![A-Za-z])" + re.escape(w) + r"(?![A-Za-z])", text or "", re.I) for w in words)


_FAIL_WORDS = re.compile(r"\b(fail(ed|ure)?|declined|rejected|reversed|unsuccessful|insufficient|cancel(l)?ed|error|pending|processing|in progress|awaiting|under review|on hold|queued|scheduled|not\s+(?:been\s+)?(?:successful|successfully|completed|sent|paid|confirmed|approved|processed|received))\b", re.I)
_OK_WORDS = re.compile(r"\b(success(ful(ly)?)?|completed|confirmed|sent|transferred|approved|paid)\b", re.I)


def validate_facts(raw, text, today=None):
    """Turn the model's proposed `payment` object into trusted facts using the document text. The model only
    proposes: status needs a success word and no failure or negation word; the amount must be the ONLY payment
    amount printed next to a currency (fees and balances aside); payer and recipient must each contain a word that
    is printed in the document; the date must be one of the dates printed in the document and not in the future;
    a reference must be printed. Anything that cannot be verified becomes unknown/None."""
    raw = raw if isinstance(raw, dict) else {}
    text = text or ""
    today = today or date.today()
    status = str(raw.get("status") or "unknown").strip().lower()
    if status not in ("success", "failed", "pending", "unknown"):
        status = "unknown"
    if status == "success" and (_FAIL_WORDS.search(text) or not _OK_WORDS.search(text)):
        status = "unknown"
    amount = raw.get("amount_ugx")
    if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
        amount = None
    if amount is not None:
        printed = _amounts(text, skip_fees=True)
        if printed is None or printed != {amount}:
            amount = None
    d = _as_date(raw.get("date"))
    if d is not None and (d not in parse_dates(text) or (d - today).days > 1):
        d = None

    def _s(v):
        v = str(v).strip() if isinstance(v, str) else ""
        return v[:80] or None

    payer, recipient = _s(raw.get("payer")), _s(raw.get("recipient"))
    if payer and not _name_in_text(payer, text):
        payer = None
    if recipient and not _name_in_text(recipient, text):
        recipient = None
    ref = _s(raw.get("reference"))
    if ref and not (re.fullmatch(r"[A-Za-z0-9._-]{6,40}", ref) and ref in text):
        ref = None
    return {"status": status, "amount_ugx": amount, "payer": payer, "recipient": recipient,
            "date": d.isoformat() if d else None, "reference": ref}


def failed_checks(result):
    return [k for k in CHECKS if not result["checks"].get(k)]


def checks_text(result):
    """One line listing the five checks that passed (for the audit trail)."""
    return "; ".join(_CHECK_LABELS[k] for k in CHECKS if result["checks"].get(k))


def decide(facts, action, members, guards=None):
    """-> {'close': bool, 'checks': {five named booleans}, 'reasons': [str]}.

    `facts` are validated payment facts; `action` has description, assignee, assignees (optional), deadline, status;
    `members` is auth.MEMBERS. `guards` carries what only the server knows: {'sender_ok': bool, 'proof_used': bool}.
    Missing guards fail closed. close is True only when all five checks and every safeguard hold."""
    facts = facts if isinstance(facts, dict) else {}
    action = action or {}
    guards = guards or {}
    reasons = []
    desc = action.get("description") or ""

    succeeded = facts.get("status") == "success"
    if not succeeded:
        reasons.append("proof does not say the transfer succeeded")

    want = parse_amount(desc)
    got = facts.get("amount_ugx")
    amount_ok = want is not None and isinstance(got, int) and got == want
    if want is None:
        reasons.append("action description has no single clear amount")
    elif not amount_ok:
        reasons.append("proof amount does not equal the action amount")

    owner = match_member(action.get("assignee") or "", members)
    others = {match_member(str(x), members) for x in (action.get("assignees") or []) if x}
    others.discard(None)
    if owner and others - {owner}:
        owner = None                                  # several assignees: the owner is not clear
    payer = match_member(facts.get("payer") or "", members)
    payer_ok = bool(owner and payer and owner == payer)
    if not payer_ok:
        reasons.append("payer is not the action owner")

    proof_day, deadline = _as_date(facts.get("date")), _as_date(action.get("deadline"))
    created = _as_date(action.get("created_at"))
    on_time = bool(proof_day and deadline and created and created <= proof_day <= deadline)
    if not deadline:
        reasons.append("action has no deadline")
    elif not created:
        reasons.append("action creation date unknown")
    elif not on_time:
        reasons.append("proof date is missing, after the deadline, or older than the action")

    recipient = match_member(facts.get("recipient") or "", members)
    named = [n for n in members_in(desc, members) if n != owner]
    recipient_ok = bool(recipient and recipient != payer and (not named or (len(named) == 1 and recipient == named[0])))
    if not recipient_ok:
        reasons.append("recipient is not a member, or not the person the action names")

    checks = {"succeeded": succeeded, "amount_matches": amount_ok, "payer_is_owner": payer_ok,
              "on_time": on_time, "recipient_ok": recipient_ok}
    all_five = all(checks.values())

    status_ok = action.get("status") in ("open", "in_progress")
    if not status_ok:
        reasons.append("action is not open or in progress")
    if not guards.get("sender_ok"):
        reasons.append("sender is neither the payer nor an admin")
    if guards.get("proof_used", True) is not False:
        reasons.append("this proof was already used for an action")
    close = bool(all_five and status_ok and guards.get("sender_ok") and guards.get("proof_used") is False)
    return {"close": close, "checks": checks, "reasons": reasons}
