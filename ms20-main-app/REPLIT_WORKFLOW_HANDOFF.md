# MS2.0 Replit Workflow Handoff

Use this handoff when a fresh Codex chat gets stuck testing only `127.0.0.1` from the local desktop workspace. The correct continuation is Replit-first for live product testing.

## Current Transfer Status

As of 2026-07-09, `ms20-main-app/` has been added to the GitHub/Replit project as the Main App-first product surface. After pulling the latest `origin/main` in Replit, verify the Main App from Replit Shell:

```bash
cd ms20-main-app
npm run verify
npm run check
```

Use `https://$REPLIT_DEV_DOMAIN/main-app/` as the phone-openable link. The bare Replit domain can remain the preserved backend status route.

## Copy-Paste Script Title

MS2.0 REPLIT LIVE TESTING CONTINUATION SCRIPT FOR NEW CODEX CHAT

## Script

```text
MS2.0 REPLIT LIVE TESTING CONTINUATION SCRIPT FOR NEW CODEX CHAT

You are continuing the existing MS2.0 project. This is not a new project.

Critical correction:
- Do not continue local-only `127.0.0.1` desktop testing.
- Do not use the local desktop workspace as proof of live readiness.
- Use the real GitHub/Replit project workflow.
- Work from the active Replit project files and Replit Shell when live verification is needed.
- Produce the real Replit public/dev URL that can open on a phone.
- Continue Main App live product testing only.
- Do not return to WhatsApp live testing now.

Project identity:
- Product name: MS2.0.
- MS2.0 is a Pharmacy Operating Intelligence Platform, not an AI chatbot.
- The Main App is now the primary product surface.
- WhatsApp/Baileys is preserved as an optional external integration layer for later.
- The current test focus is Main App screens, editable cards, offline-first behavior, and owner usability.

Core engineering rules:
- Offline-first.
- Local-first before AI.
- AI only when useful and explicitly required.
- Editable cards instead of heavy typing.
- Common workflows must be three steps or less.
- Do not rebuild stable systems.
- Extend through adapters.
- Protect OpenAI/API tokens.
- No unnecessary OpenAI/API calls.
- Preserve backend, offline app, Baileys bridge, Google Sheets integration, reports, stock/sales safety, secrets, and runtime config.
- If blocked, stop and report the exact blocker instead of looping.

What the previous successful Codex/Replit workflow did:
1. Identified the actual Replit workspace by checking:
   - current directory
   - `REPLIT_DEV_DOMAIN`
   - `REPL_ID`
   - `REPL_OWNER`
   - `REPL_SLUG`
   - top-level files
   - git branch and remote
2. Used the real Replit Shell and project filesystem, not only local desktop localhost.
3. Pulled from the real GitHub remote inside Replit with a safe merge command.
4. Preserved existing runtime files, secrets, Baileys auth/session, Google Sheets config, offline app, and backend.
5. Started runtime from Replit Shell.
6. Verified backend routes such as `/health`, `/debug/version`, `/status`, `/live/readiness`, and `/offline_app/index.html`.
7. Used `$REPLIT_DEV_DOMAIN` or the Replit public/dev URL to produce a phone-openable app link.
8. Guided live tests one action at a time, waited for screenshots/results, fixed verified friction, then resumed from the paused step.

Important project files/docs to read first:
- `ms20-main-app/README.md`
- `ms20-main-app/FINAL_REPORT.md`
- `ms20-main-app/CODEX_CONTINUATION_HANDOFF.md`
- `ms20-main-app/CURRENT_ARCHITECTURE_SNAPSHOT.md`
- `ms20-main-app/LIVE_APP_TEST_PLAN.md`
- `ms20-main-app/REPLIT_WORKFLOW_HANDOFF.md`
- `ms20-main-app/package.json`
- `ms20-main-app/tools/serve.mjs`
- `ms20-main-app/tools/verify-architecture.mjs`
- `ms20-main-app/src/app.js`
- `ms20-main-app/src/services/liveBackendGateway.js`
- `ms20-main-app/src/services/backendAdapters.js`
- `ms20-main-app/src/contracts/integrationContracts.js`
- `ms20-main-app/src/routes/routeRegistry.js`
- `ms20-main-app/src/cards/editableCards.js`
- root `README.md` if present
- root `README_PRODUCTION.md` if present
- root `DEPLOY_NOW.md` if present
- root `.replit` if present
- root `replit.nix` if present
- root `start.sh` if present
- root `requirements.txt`
- root `package.json` if present
- backend files under `app/`, especially:
  - `app/main.py`
  - `app/live_runtime.py`
  - `app/local_first_parser.py`
  - `app/intake.py`
  - `app/sheets.py`
  - `app/reports.py`
  - `app/medicine_brain.py`
  - `app/reliability.py`
  - `app/provisioning.py`
  - `app/deployment.py`
  - `app/live_pilot.py`
  - `app/whatsapp.py`
- offline app files if present:
  - `offline_app/index.html`
  - `static/offline_app/index.html`
  - `static/offline_app/app.js`
  - `static/offline_app/manifest.json`
- bridge/runtime files if present:
  - `baileys-bridge.js`
  - `local_whatsapp_bridge.js`
  - `whatsapp-web-bridge.js`
  - `bridge.log`
  - `server.log`
- tests:
  - `tests/`
  - `ms20-main-app` verification scripts

What was completed before this handoff:
- Safe Main App merge completed in `ms20-main-app`.
- Main App shell preserved.
- Existing backend preserved.
- Existing offline app preserved.
- Baileys bridge preserved.
- Adapter slots added.
- Live backend gateway added.
- Route registry added.
- Integration contracts added.
- Editable card mapping added.
- Verification tooling added.
- User-facing branding is MS2.0.
- No secrets touched.
- No production WhatsApp runtime modified.
- No OpenAI/API usage introduced.

Known current state:
- Main App is the primary product now.
- Main App has safe adapters/placeholders and backend route metadata.
- Main App cards currently use protected queue-only behavior until live write sync is deliberately enabled and tested.
- Main App may not yet directly mutate every live production sale/stock flow from every screen. That is expected after the safe merge.
- The next job is Main App live product testing and verified friction fixing, not WhatsApp live testing.

Commands/tests previously run and passed:
- `cd ms20-main-app && npm run verify` -> PASS.
- `cd ms20-main-app && npm run check` -> PASS.
- `cd ms20-main-app && node --check src/services/liveBackendGateway.js` -> PASS.
- `python -m py_compile app/main.py app/live_runtime.py app/local_first_parser.py app/sheets.py` -> PASS.
- HTTP check for Main App local route -> PASS.
- Browser load inspection -> PASS.
- Browser console error check -> PASS, zero console errors.
- Deterministic card proof for `Panadol 2 cash` -> PASS, zero OpenAI/API calls.

Replit workflow rule:
- Give the user one Replit Shell command at a time only when user action is required.
- If you can run commands directly in the actual active environment, do so.
- Do not give many commands at once.
- Do not loop.
- Do not repeat broad scans unless the result requires it.
- If a command fails, inspect the exact failure and fix the root cause.

First Replit identification command pattern:
Use this in Replit Shell to prove you are in the real Replit project:

python - <<'PY'
import os, json, pathlib, subprocess
root = pathlib.Path.cwd()
def run(cmd):
    try:
        p = subprocess.run(cmd, cwd=root, text=True, capture_output=True, timeout=20)
        return {"ok": p.returncode == 0, "code": p.returncode, "out": p.stdout.strip(), "err": p.stderr.strip()}
    except Exception as e:
        return {"ok": False, "error": repr(e)}
report = {
    "cwd": str(root),
    "replit": {
        "REPLIT_DEV_DOMAIN": os.environ.get("REPLIT_DEV_DOMAIN"),
        "REPL_ID": os.environ.get("REPL_ID"),
        "REPL_OWNER": os.environ.get("REPL_OWNER"),
        "REPL_SLUG": os.environ.get("REPL_SLUG"),
        "PORT": os.environ.get("PORT"),
    },
    "git": {
        "inside": run(["git", "rev-parse", "--is-inside-work-tree"]),
        "branch": run(["git", "branch", "--show-current"]),
        "status": run(["git", "status", "--short", "--branch"]),
        "remote": run(["git", "remote", "-v"]),
        "last_commit": run(["git", "log", "-1", "--oneline"]),
    },
    "top_level": sorted([p.name for p in root.iterdir() if not p.name.startswith(".")])[:120],
    "main_app_present": (root / "ms20-main-app" / "package.json").exists(),
    "backend_present": (root / "app" / "main.py").exists(),
}
print(json.dumps(report, indent=2, sort_keys=True))
PY

Safe GitHub/Replit sync pattern:
Only after checking status/remotes, use:

git pull --no-rebase --no-edit origin main

If Git reports divergent branches, use merge mode, not rebase, unless the user explicitly requests otherwise. Preserve Replit runtime config and secrets. Do not reset hard. Do not wipe auth/session files.

Main App verification pattern in Replit:

cd ms20-main-app
npm run verify
npm run check
node --check src/services/liveBackendGateway.js

Backend compile verification pattern from repo root:

python -m py_compile app/main.py app/live_runtime.py app/local_first_parser.py app/sheets.py

Start Main App in Replit:
- Prefer the backend-served Main App route for phone testing: `/main-app/`.
- Restart the Replit app after pulling backend route changes so `app/main.py` is reloaded.
- Use the Replit Shell for verification.
- Do not enable WhatsApp bridge.

Standalone Main App server pattern for focused module checks only:

cd ms20-main-app && PORT=${PORT:-5177} npm run serve

If Replit has a reserved `$PORT`, respect it. If not, port 5177 is acceptable for local-in-Replit checks. It may not be the public phone route when the backend owns the Replit domain.

Find the Replit phone-openable URL:

python - <<'PY'
import os
domain = os.environ.get("REPLIT_DEV_DOMAIN")
if domain:
    print("https://" + domain + "/main-app/")
else:
    print("REPLIT_DEV_DOMAIN missing. Use the Replit Webview/Open in new tab URL shown by Replit.")
PY

Expected Main App Replit URL shape:
- `https://$REPLIT_DEV_DOMAIN/main-app/`
- If the bare domain returns `{"status":"running"}`, the backend is active and the owner should open `/main-app/`.

Backend route verification pattern:
If backend is running separately on port 5000, verify:

python - <<'PY'
import urllib.request
for path in ["/health", "/debug/version", "/debug/main-app", "/main-app/", "/status", "/live/readiness", "/offline_app/index.html"]:
    url = "http://127.0.0.1:5000" + path
    print("\n" + path)
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            body = r.read().decode("utf-8", "replace")
            print("HTTP", r.status)
            print(body[:1200])
    except Exception as e:
        print("ERROR", repr(e))
PY

Standalone Main App route verification pattern:
If the standalone Main App server is running on `$PORT` or 5177, verify:

python - <<'PY'
import os, urllib.request
port = os.environ.get("PORT") or "5177"
for path in ["/", "/index.html", "/manifest.json"]:
    url = f"http://127.0.0.1:{port}{path}"
    print("\n" + url)
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            body = r.read().decode("utf-8", "replace")
            print("HTTP", r.status)
            print(body[:500])
    except Exception as e:
        print("ERROR", repr(e))
PY

Browser verification:
- Open the Replit public/dev Main App URL, not local-only `127.0.0.1`: `https://$REPLIT_DEV_DOMAIN/main-app/`.
- Confirm title says `MS2.0 Main App`.
- Confirm dashboard loads.
- Confirm backend status strip appears.
- Confirm offline app link appears.
- Check browser console if tool/browser access is available.
- If console automation is flaky, do not loop; use manual screenshot plus route checks.

Phone-openable link requirement:
- Always give the user the Replit URL, not `http://127.0.0.1`.
- The user needs a phone-openable URL.
- Use `/main-app/` when the backend owns the bare Replit domain.
- If only localhost is available, report BLOCKED: Replit public/dev URL not available, and give the exact Replit action needed.

Preservation rules:
- Do not rebuild stable backend.
- Do not rebuild existing offline app.
- Do not touch secrets.
- Do not break Google Sheets.
- Do not turn on WhatsApp/Baileys unless explicitly asked.
- Do not consume OpenAI/API tokens.
- Keep local-first tests first.
- Do not rename internal folders or repository unless explicitly required.
- Do not reset or wipe Git/Replit state.

How previous live tests were executed:
- One live test action at a time.
- Wait for user screenshot/result.
- Identify PASS or FRICTION.
- If FRICTION, fix the root cause broadly across shared templates/services/adapters rather than only patching the single test.
- Run focused verification for the fix.
- Continue from the paused test step.
- Keep friction/fix notes.

Main App live product testing sequence to begin now:
1. Confirm Replit project and route.
2. Pull/sync safely if needed.
3. Run `npm run verify`.
4. Start Main App in Replit.
5. Produce the Replit phone-openable URL.
6. Open Main App in browser and phone if possible.
7. Test Dashboard.
8. Test Chat Workspace.
9. Test editable sale card.
10. Test stock workflow.
11. Test report workflow.
12. Test restock workflow.
13. Test voice workspace placeholder without AI.
14. Test photo/invoice placeholder without AI.
15. Test offline framework and queued card behavior.
16. Test sync/offline states.
17. Test error states.
18. Test mobile layout and owner usability.

Main App live testing rules:
- Do not test WhatsApp.
- Do not start WhatsApp bridge.
- Do not send WhatsApp messages.
- Do not call OpenAI/API.
- Do not claim production readiness from placeholder behavior.
- Separate PASS, FRICTION, and BLOCKED clearly.

Expected output format during testing:
CURRENT STEP:
COMMAND OR ACTION:
WHAT USER SHOULD SEND BACK:
PASS/FAIL/FRICTION:
NEXT ACTION:

If READY, provide:
- exact Replit Main App link
- exact backend/offline app link if available
- what passed
- next Main App test step

If BLOCKED, provide:
- exact blocker
- exact action needed from the user
- no long explanation

Start now by proving the active Replit project/workspace, then run Main App verification, then produce the Replit phone-openable URL. Do not continue local-only localhost testing.
```
