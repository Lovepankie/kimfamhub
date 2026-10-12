# Payment proof auto-close: Hub build report

Branch: feat/payment-proof-auto-close (not merged, not deployed, no PR).

## Built
- payment_proof.py: pure parse_amount, match_member, validate_facts, decide.
- /api/agent/classify-doc returns a validated `payment` object; /api/agent/file-doc accepts `payment` and `sender_phone`,
  re-validates from the stored file, and closes only under the five rules plus safeguards (ADR-037).
- POST /api/internal/actions/reopen (internal key; only after an auto-close).
- payment_proofs table (sha256 primary key) created under an advisory lock; claim, close and audit row in one transaction.
- Kill switch KIMFAM_AUTOCLOSE_OFF=1.
- ADR-037 and the architecture.dsl component.

## Checks
- python -m compileall -q . : clean.
- tests/test_api.py with a local Postgres: 305 passed, 6 failed. The 6 failures are the Ask tests (TestAskPromptFit,
  TestAskRagRetrieval), which fail only because chromadb is not installed; they fail identically on main.
- New tests (37): rules unit tests, each of the five failing alone, all five closing, sender, status, repeated file hash,
  kill switch, failure isolation, reopen rules, internal-key refusals, source structure (writes committed), classify.

## Not covered
- The new tests use an in-memory fake for actions, action_updates and payment_proofs; the SQL has not run against the
  production schema. Check on staging that `actions.closed_at`, `action_updates.old_value/new_value` and `assignees` behave
  as in `/api/internal/actions/done`, which uses the same columns.
- The classify prompt change was not run against the live model.
