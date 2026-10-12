workspace {
    model {
        hillary = person "Hillary Arinda" "KimFam member, developer and system administrator"
        member  = person "KimFam Member"  "Family investment club member"

        kimfam = softwareSystem "KimFam Hub" "Family investment club portal" {
            frontend = container "React SPA" "Vite + React 19 + TS + Tailwind v4. Renders all screens; mobile bottom-sheet modals; design system per docs/design-system.md." "TypeScript / React" {
                designSystem = component "Design System"   "ui/ primitives (Button, Card, Dialog/sheet, Tabs, Badge) + tokens in index.css. shadcn/Radix style."
                projectsUI   = component "Projects UI"      "Cards, Audit/Analysis/Portfolio/Viability-Matrix modals, Team Interest accordion, Express Interest sheet"
                proposalsUI  = component "Proposals UI"      "Submit + AI scorecard (criteria bars, support-readiness), versioned per project owner"
                i18n         = component "i18n"             "react-i18next - en / sw / rny"
                query        = component "Data Layer"       "TanStack Query against the FastAPI JSON API"
            }
            webapp = container "FastAPI Web App" "Gunicorn/Uvicorn. Auth, JSON API, SSE, serves the built SPA." "Python / FastAPI" {
                authApi     = component "Auth API"          "/api/auth/* - login, WhatsApp OTP reset, JWT cookie"
                askApi      = component "Ask KimFam API"    "/api/ask/stream - SSE RAG pipeline"
                financeApi  = component "Finance API"       "Contributions, loans, equity, projects, balances"
                projectApi  = component "Projects API"       "/api/projects/* - detail, audit, narrative, interests, projection (viability matrix), updates[] timeline; /api/portfolio/* ranking + new ventures"
                investmentEngine = component "Investment Projection Engine" "investment.py - pure, unit-tested month-by-month viability matrix (own vs borrowed capital, member-lender payout, mandatory downside). See ADR-024"
                timelineEngine   = component "Project Timeline Builder" "project_timeline.py - pure, unit-tested newest-first update timeline; pins hardcoded media updates, conservative supersede. See ADR-025"
                sheepTracker     = component "Livestock Tracker" "livestock.py + sheep.py - native Postgres tracker for every herd (sheep_* tables scoped by project_id; sheep club-owned, goats owned per family member with per-owner counts and money): entry forms with review-then-confirm, soft deletes, flock/mortality/expenses/charts/alerts, /api/projects/{sheep,goats}/detail and /api/projects/{pid}/livestock/* (also on the internal key with reported_by + source_ref for WhatsApp reports, ADR-030). NOT Google Sheets. See ADR-026, ADR-029, ADR-030"
                projectLedger    = component "Project Ledger" "ledger.py - one native ledger for every project (ledger_products/stock/sales/losses/expenses scoped by project_id, soft delete, source_ref): the AppSheet Financial Statement formulas computed in code, idempotent snapshot import that refuses unless it matches the sheet to the shilling, read models for the chicken card/detail/audit behind the LEDGER_READS flag (off until cut-over day). Replaces Solomon's AppSheet. See ADR-032"
                decisionTrace    = component "Decision Trace" "decision_trace.py: register of decisions (decisions, decision_links, decision_private_meetings; advisory-lock ready(); meetings.is_private is best-effort, the override table is authoritative): transcript chunking, prompt, a check() that drops any decision whose quote is not verbatim in the stored transcript and names a speaker only if the transcript labels the turn, idempotent extract_meeting (private meetings skipped, minutes-only fallback), suggest_links (suggested only; admins confirm/reject at /api/decision-register/*), and the read side (trace chain with quote context from the stored transcript, member register list, admin review) behind the Why? panel. Model is an injected function, so tests run offline. See ADR-034"
                speakerMap       = component "Speaker Map" "speaker_map.py: maps diarized labels (Speaker N) to members per meeting. Pure split_sources, align (pasted named transcript against the audio), addressed_names and suggest (attendees only; a name covering two or more voices is shared; below the evidence floor unknown; never confirmed); app-owned meeting_speakers and speaker_map_log (advisory-lock ready()); a person present or an admin confirms through PUT /api/meetings/{id}/speakers/{label} (JWT only); decisions keep the raw label and the member is resolved at display time from confirmed rows only. Identity is never inferred from account, IP or device. See ADR-034"
                paymentProof     = component "Payment Proof Auto-Close" "payment_proof.py (pure: parse_amount, match_member, validate_facts, decide) plus /api/agent/classify-doc (model proposes a payment object), /api/agent/file-doc (re-validates, closes only when all five rules and the safeguards hold, one transaction with a sha256 claim in payment_proofs) and /api/internal/actions/reopen (undo, only after an auto-close). Kill switch KIMFAM_AUTOCLOSE_OFF=1. See ADR-037"
                decisionReport   = component "Decision Report" "report.py: smart report. Pure evidence pack with stable citation ids, prompt, verify_report that strips any sentence without a valid citation or that names an unset speaker, stable pack hash; decision_reports table (advisory-lock ready(), writes via db.execute); injected model function (Claude via _ask_claude). Cached by pack hash, never generated on GET. See ADR-034"
                klafamApi   = component "KlaFam Tanda API"  "/api/klafam/* - rotating savings (ROSCA): cycles + rotation, own contribution (pay/offset), beneficiary-only cycle acknowledge, and beneficiary/admin record-for-member receipt carrying recorded_by attribution. Two rolling cycles: the previous cycle stays open for late payers until the 14th of the current month (klafam_window.py, previous_cycle in /overview). See ADR-027, ADR-031"
                adminApi    = component "Admin API"         "Member management, config, documents"
                docsApi     = component "Documents API"      "/api/docs - nested category/sub-group repo over R2; serve/preview docx/pdf/pptx/xlsx"
                proposalsApi = component "Proposals API"     "/api/proposals - upload, Claude-only AI scoring vs the Project Proposal Template + reward guidelines, support-readiness, versioning/archiving"
                meetingsApi = component "Meetings API"       "/api/meetings/* - conductor full-call recording, diarized transcription, minutes narrative (Sonnet map-reduce) + docx, publish"
                scheduler   = component "APScheduler"       "Meeting reminders, notification jobs (fcntl lock)"
                chromadb    = component "ChromaDB"          "Local vector store for RAG over governance docs"
            }
            nginx = container "Nginx" "Reverse proxy, SSL, serves SPA index + /assets" "Nginx"
            pg    = container "PostgreSQL" "kimfamhub (prod) / kimfamhub_test (staging): members, families, contributions, loans, project_participation" "PostgreSQL"
            sqlite= container "SQLite stores" "auth (kimfam.db), washing_bay.db income" "SQLite"
        }

        ci          = softwareSystem "GitHub Actions" "CI/CD (repo RincolTech-Solutions-ltd/kimfamhub since ADR-036): push to any branch deploys staging; main promotes to prod after green tests + Claude self-heal" "External"
        designLoop  = softwareSystem "Design Review Loop" "tools/design-loop: Playwright screenshots staging, Gemini critiques vs design-system.md" "External"
        kimfamSheet  = softwareSystem "KimFam Financials Sheet" "Meeting Register, Action Tracker, financial ledger - managed by Hillary/Hellen on the main KimFam Google Sheet" "External"
        solomonSheet = softwareSystem "Solomon's AppSheet" "Chicken project P&L - Solomon's operational records (flock counts, expenses, revenue) entered via AppSheet mobile app, stored in a separate Google Sheet owned by Solomon" "External"
        whatsapp    = softwareSystem "WhatsApp" "OTPs, meeting reminders, group auto-capture" "External"
        cloudflare  = softwareSystem "Cloudflare R2" "Object storage for PDFs, minutes, media" "External"
        claudeCli   = softwareSystem "Claude CLI" "claude -p subprocess on Hetzner (subscription tokens, no API key) - Ask/audit/narrative primary. claude_cli.complete() tries the main account, then a backup account (CLAUDE_CODE_OAUTH_TOKEN_2), treating any limit/login notice as a failure so DeepSeek and Groq fallbacks run. See ADR-036" "External"
        gemini      = softwareSystem "Gemini API" "Gemini 2.5 Flash - AI fallback (gemini-2.0-flash retired, 404) + design-loop critic (nano banana needs paid tier)" "External"
        groq        = softwareSystem "Groq API" "openai/gpt-oss-120b - final AI fallback (llama-3.3-70b decommissioned, 404); Whisper transcription fallback" "External"
        deepgram    = softwareSystem "Deepgram API" "nova-3 speech-to-text with speaker diarization - primary meeting-recording transcription (ADR-022)" "External"
        hetzner     = softwareSystem "Hetzner VPS" "89.167.121.193 - prod + staging hosts" "External"

        member   -> nginx     "HTTPS"
        hillary  -> nginx     "HTTPS / SSH"
        nginx    -> frontend  "Serves SPA"
        nginx    -> webapp    "Proxies /api"
        frontend -> webapp    "JSON / SSE over /api"
        webapp   -> pg        "SQL reads/writes (role: kimfam)"
        webapp   -> sqlite    "Auth + washing bay"
        webapp   -> kimfamSheet  "Sheets API v4 - legacy ledger; meetings and actions live in the app DB (Ask KimFam reads them there, ADR-028)"
        webapp   -> solomonSheet "Sheets API v4 - chicken data read-only"
        webapp   -> whatsapp  "WhatsApp bridge"
        webapp   -> cloudflare "S3-compatible SDK"
        askApi   -> claudeCli "Primary"
        askApi   -> gemini    "Fallback"
        askApi   -> groq      "Final fallback"
        askApi   -> chromadb  "Embedding search (local sentence-transformers)"
        projectApi -> claudeCli "Audit/narrative/portfolio AI"
        projectApi -> investmentEngine "Computes viability matrix (pure function)"
        projectApi -> timelineEngine "Builds per-project updates[] timeline (pure function)"
        projectApi -> sheepTracker "Live sheep analytics (/api/projects/sheep/detail)"
        projectApi -> projectLedger "Chicken card, detail and audit read the ledger once LEDGER_READS=chicken (ADR-032)"
        decisionTrace -> pg "decisions / decision_links / decision_private_meetings (+ meetings.is_private where the role may alter it)"
        speakerMap -> pg "meeting_speakers / speaker_map_log (+ decisions.speaker_label)"
        paymentProof -> pg "payment_proofs (sha256 of the proof file, action_ref); closes actions and writes action_updates status_change rows by Rincol AI (auto-close)"
        paymentProof -> claudeCli "classify-doc asks the model for payment facts via claude_cli.complete (main then backup account); code validates every fact"
        speakerMap -> decisionTrace "Resolves a decision's raw speaker label to a confirmed member at display time (trace, register)"
        projectApi -> speakerMap "GET /api/meetings/{id}/speakers (members), PUT .../{label} (admin or attendee, JWT), POST .../suggest (admin)"
        decisionReport -> pg "decision_reports (cached cited reports)"
        decisionReport -> decisionTrace "Reads the register, actions and trace data for the evidence pack"
        decisionReport -> projectLedger "Reads ledger rows, reconciliation open items and the scorecard"
        projectApi -> decisionReport "GET /api/trace/{project}/report (members, cached); POST (admin JWT) generates, verifies, stores (ADR-034)"
        askApi -> decisionReport "decision_trace tool (Ask KimFam) answers why-questions from the register, citing decision ids; reads /api/trace/{project}/decisions with the internal key"
        projectApi -> decisionTrace "Admin register routes: list, confirm, reject, add link, flag a meeting private, review a decision; member routes GET /api/trace/{project} and /decisions (ADR-034)"
        decisionTrace -> projectLedger "Suggests links from decisions to ledger rows (never confirms)"
        projectLedger -> pg "ledger_products / ledger_stock / ledger_sales / ledger_losses / ledger_expenses"
        sheepTracker -> pg "sheep_animals / sheep_events / sheep_expenses (owned by kimfam role)"
        klafamApi -> pg "klafam_cycles / klafam_contributions (+recorded_by) / klafam_members (owned by kimfam role)"
        member -> klafamApi "Records own contribution; as cycle beneficiary, records receipts from other members"
        projectApi -> financeApi "Reads confirmed bank balance (get_summary) for the projection"
        proposalsApi -> claudeCli "Proposal scoring (Claude only; framework docs as context; SSE progress)"
        proposalsApi -> cloudflare "Stores proposal files (projects/Proposals/<title>/v<n>)"
        proposalsApi -> pg "proposals table (scores, versions, readiness, file_hash, uploaded_at)"
        proposalsApi -> whatsapp "Owner confirmation on submit; deliberate group share (ready for review)"
        meetingsApi -> deepgram "Diarized transcription of the full-call recording (nova-3)"
        meetingsApi -> groq "Whisper transcription fallback"
        meetingsApi -> claudeCli "Minutes narrative (Sonnet map-reduce) + edits"
        meetingsApi -> cloudflare "Publishes minutes docx (7-day link)"
        meetingsApi -> whatsapp "Meeting reminders + minutes links"
        financeApi -> pg "Contributions, per-month arrears detail, receipts (ADR-023)"
        docsApi  -> cloudflare "Lists/serves the document repo"
        ci       -> hetzner   "rsync + systemctl restart (staging, then prod on main)"
        ci       -> claudeCli "Self-heal step on test failure"
        designLoop -> frontend "Screenshots staging"
        designLoop -> gemini  "Critique vs spec"
        webapp   -> hetzner   "Deployed on"
        frontend -> hetzner   "Built dist deployed on"
    }

    views {
        systemContext kimfam "SystemContext" {
            include *
            autoLayout
        }
        container kimfam "Containers" {
            include *
            autoLayout
        }
        component frontend "FrontendComponents" {
            include *
            autoLayout
        }
        theme default
    }
}
