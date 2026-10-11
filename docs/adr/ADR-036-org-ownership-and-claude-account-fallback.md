# ADR-036: Repository moves to the RincolTech org; Claude calls fall over to a backup account

## Status: Accepted (11 Oct 2026)

## Context
- The repository lived under a personal GitHub account, so a teammate (Solomon, the farm recorder) could not be given
  full access without sharing that account.
- On 11 Oct 2026 the Claude login used by the Hub hit its weekly usage limit. The Claude CLI printed "You've hit your
  weekly limit" on stdout and exited 0. Every call site treated "exit 0 and some text" as the model's answer, so meeting
  processing failed with "Couldn't extract minutes" and the DeepSeek and Groq fallbacks never ran.

## Decision
1. **Ownership.** The repository is now `RincolTech-Solutions-ltd/kimfamhub` (transferred, same visibility: public).
   Actions secrets (deploy key, staging test password) moved with it. CI was verified green from the new location. The
   server directories are not git clones (CI deploys over SSH), so nothing on the servers changed. Local clones repoint
   with `git remote set-url origin git@github.com:RincolTech-Solutions-ltd/kimfamhub.git`. Solomon has admin on the
   repository. Write access already lets a person change the deploy workflow and so reach the production deploy key;
   admin adds settings, secrets management and deletion. This is accepted knowingly.
2. **A CLI notice is a failure.** `claude_cli.usable()` rejects short plain-text limit, login, credit and token notices
   (JSON and long answers are never rejected). Every call site goes through `claude_cli.complete()`.
3. **Account chain.** `complete()` tries `CLAUDE_CODE_OAUTH_TOKEN` (main account), then `CLAUDE_CODE_OAUTH_TOKEN_2`
   (backup account, set in the Hub `.env` on prod and staging), and returns "" when both fail. The existing callers then
   continue to DeepSeek, then Groq. Tokens are never logged; the last failure reason (stderr or the notice) is kept for the
   AI health record, so a rejected token still shows the restart hint.

## Consequences
- Better: a limited account no longer breaks minutes, Ask KimFam, agenda, audit or pitch features; the backup keeps Claude
  quality. A limit notice can no longer be mistaken for an answer anywhere.
- Worse: two secrets to rotate (`claude setup-token` for each account, then restart kimfamhub and kimfamhub-staging).
  Both accounts share the Hub's call volume. The WhatsApp agent has its own token file and does not use the backup yet.
- Watch: if both accounts are limited the chain ends at DeepSeek (lower quality for minutes). The public repository must
  keep holding no real names, money figures or transcript text.
