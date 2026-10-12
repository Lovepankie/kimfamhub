# ADR-037: Strict auto-close of payment proofs

## Status: Accepted (12 Oct 2026)

## Context
- A member shares a bank or mobile-money payment proof in the KimFam WhatsApp group. The agent already classifies the
  file (`/api/agent/classify-doc`), files it (`/api/agent/file-doc`) and comments on the matching action. The action then
  waits for an admin to close it by hand, although the proof often settles it.
- Closing an action wrongly is worse than leaving it open: it hides unpaid work from the register. The Hub has no amount
  column on actions, only a free-text description, and a model reading a receipt can misread or invent a figure.

## Decision
An action is closed (status `done`, `closed_at` set) automatically ONLY when all five rules hold. Otherwise behaviour is
exactly as before: the document is filed and a comment is added.
1. **Succeeded.** The proof says the transfer succeeded (status `success`, and the document text itself says so and does
   not say failed, declined, pending or reversed).
2. **Amount.** The proof amount equals the action amount exactly. The amount is parsed from the description (for example
   `UGX 123,000`); no single clear amount means no auto-close.
3. **Payer is the owner.** The payer name matches a Hub member by whole-word match on the member name (so a surname
   variant still matches), and that member is the action assignee.
4. **On time.** The proof date is on or before the action deadline. No deadline means no auto-close.
5. **Recipient.** The recipient matches a Hub member (same matching), is not the payer, and if the description names a
   person other than the owner, equals that person.

Extra safeguards, all of which must also hold:
- The action is `open` or `in_progress`.
- The proof file has not been used before: a sha256 of the file bytes is claimed in the app-owned table
  `payment_proofs`, created under an advisory lock like `decision_trace.ready()`. The claim, the status update and the
  `action_updates` row are one `db()` transaction, so a lost race or a concurrent close rolls everything back.
- The WhatsApp `sender_phone` belongs to the payer or to an admin.
- The model only proposes. `classify-doc` returns a `payment` object, and code validates it against the document text
  (the amount must literally appear, the date must parse, `success` needs the text to say so). `file-doc` validates again
  from the stored file, so the relayed facts are never trusted.
- Ambiguity fails closed: two members in one name, several assignees, two amounts, a missing field.
- Every auto-close writes an `action_updates` row of type `status_change` by `Rincol AI (auto-close)`, listing the checks
  that passed.
- Undo: `POST /api/internal/actions/reopen {action_ref, by}` (internal key) is allowed only when the latest status change
  on the action is an auto-close; it sets `in_progress` and logs a status change. The proof stays used.
- Kill switch: `KIMFAM_AUTOCLOSE_OFF=1` makes the Hub ignore and not return payment facts.
- Any failure in this path is logged and swallowed; filing and commenting are never affected.

## Consequences
- Better: proofs that clearly settle an action close it at once, with a visible audit line and a one-message undo.
- Worse: a proof that is slightly off (a typo in a name, a fee added to the amount, a missing deadline) is only commented,
  so an admin still closes it by hand. This is intended.
- Watch: member matching is by first name, so a payer string naming two members never matches. The model prompt and the
  rules live in `payment_proof.py` and `main.py`; changing a rule needs a new ADR.

## Amendment (12 Oct 2026, after independent review)
The first build trusted the model for payer, recipient and date, and a negated or look-alike document could pass. Now code verifies every fact against the document text before the five rules run:
- **Status** needs a success word and no failure or negation word ("not successful", "under review", "queued" and similar).
- **Amount** must be the only payment amount printed next to a currency, ignoring figures that follow fee, charge, balance, tax and similar words. Scaled ("4m"), space grouped and fractional amounts, in the document or the action description, are not read, so they never close anything. A bare year before the currency is not an amount.
- **Payer and recipient** must each share a word with a name printed in the document.
- **Date** must be one of the dates printed in the document, read day first for numeric forms, and not in the future. The proof date must also be on or after the action's creation date, so an old receipt cannot close a new recurring action.
- **Reference** (the printed transaction id) is stored with the file hash; a second file with the same reference never closes another action.
- **Sender:** a post from a shared phone (env KIMFAM_SHARED_PHONES, one device used by several people) never auto-closes, even for an admin.
- **Reopen** is allowed only within 7 days and only when payment_proofs recorded the auto-close, not merely because the last status change carries the auto-close author name.
Residual risk, accepted: members are matched by first name, so an outsider who shares a member's first name and prints it on a proof can satisfy the payer or recipient check. The group announcement with its one-line reopen, and the sender and ownership checks, are the mitigation.
