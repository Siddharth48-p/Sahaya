# Sahaya + CareCircle Local MVP Integration Report

## Summary

The existing Sahaya Python dashboard now includes a local gig-worker module in the same standard-library HTTP server and the same SQLite database file. CareCircle's original project files and data were not used or changed. The worker role selector is a local-demo convenience, not authentication or an authorization boundary.

The health dashboard continues to display prepared replay data. The existing M3 model artifact is available for the offline/replay ML pipeline; new manually entered readings continue to use explicitly labelled demonstration rule logic. No live M3 inference was added because a single reading does not provide the model's required 94-feature causal history, and the raw benchmark streams are absent.

## Features implemented and verified

- Additive SQLite tables for demo workers, gigs, decisions, status history, notifications, and earnings, initialized in the existing dashboard database.
- Seeded synthetic `Priya Nair (Demo Helper)` to demonstrate the eligible worker flow, plus a pending synthetic helper to show eligibility gating.
- Admin gig create, draft/publish, list/manage, alert association for active Sahaya alerts, local area/category/date/payout fields, and admin analytics.
- Worker registration and editable profile/statuses. The backend blocks acceptance until identity is marked verified, admin approval is granted, training completion is recorded, the worker is active and available, and the worker has the gig's required skills.
- Pending offers omit client contact/address/instructions. Accepting the gig reveals full task details to the assigned worker. Pass is recorded per worker.
- Atomic gig acceptance, sequential status workflow (`accepted` → `on_way` → `reached` → `helping` → `done`), worker/admin notifications, and earnings recorded only at completion.
- Sahaya active alert cards link to gig creation with the selected alert prefilled; the dashboard polls the shared database for gig progress.
- Mobile responsive layout and explicit local-demo/synthetic-data labels in the Gig Management UI.
- Demo reset clears gig-module tables and re-seeds demo workers; it does not clear health readings or alerts.

## Files changed

- `README.md` and `elder-ml/README.md`: localhost setup, demo steps, safety boundary, and pointers to this report.
- `elder-ml/src/dashboard.py`: serves the gig assets/API, initializes the additive tables, links active alerts to gig creation, and displays/polls gig progress.
- `elder-ml/src/gigs.py`: SQLite schema and seed data, eligibility rules, gig/worker/task APIs, lifecycle validation, notices, earnings, analytics, and reset behavior.
- `elder-ml/web/index.html`, `app.js`, `styles.css`: Sahaya navigation and active-alert action/progress panel.
- `elder-ml/web/gigs.html`, `gigs.js`, `gigs.css`: admin/helper views and responsive local demo interface.
- `elder-ml/tests/test_gigs.py`: five gig integration tests. `elder-ml/tests/test_dashboard_inputs.py` was already an existing local change and was preserved; it was included in the full test run.
- `INTEGRATION_REPORT.md`: updated verification summary; `FINAL_INTEGRATION_REPORT.md`: this full integration report.

## Shared database and API

Gig tables are created additively in Sahaya's configured `DB_FILE`; existing health tables and feed files are preserved. The gig module uses `gig_workers`, `helper_gigs`, `helper_gig_decisions`, `helper_gig_history`, `helper_gig_notifications`, and `helper_gig_earnings`. Startup initialization is idempotent and seeds clearly synthetic helpers when absent. The demo's role/worker selector is a request parameter for convenience, not security.

The local API is served by the existing Sahaya handler, including `GET /api/gigs/state`, `GET /api/gigs/alert-context?id=…`, `GET /api/gigs/health`, `POST /api/gigs/workers`, `PATCH /api/gigs/workers/{id}`, `POST /api/gigs/workers/{id}/availability`, `POST /api/gigs/tasks`, `POST /api/gigs/tasks/{id}/accept`, `POST /api/gigs/tasks/{id}/pass`, `POST /api/gigs/tasks/{id}/status`, and `POST /api/gigs/reset`. Sahaya health data continues through its existing `/api/state`, `/api/readings`, `/api/simulate`, and `/api/workflow` endpoints. The gig API stores the Sahaya alert ID and patient ID on the task and never resolves the medical alert automatically when a gig is done.

## Repeatable local demo walkthrough

1. Start Sahaya using the commands below and open `http://127.0.0.1:8765`.
2. Choose a synthetic profile and use the dashboard's simulated alert input. Review the alert's explicit demo/rule or replay source label.
3. Select **Assign Helper / Create Gig** on that alert. The gig form carries the alert and patient references. Choose **Hospital accompaniment**, enter synthetic task/contact details, set a future date and payout, and publish.
4. Open **Gig Management**, switch from **Organisation** to **Gig Worker**, and select **Priya Nair (Demo Helper)**. The new eligible offer appears in the queue/popup. The pending card hides private client details.
5. Accept the offer. Check that full synthetic client details appear, then advance it in order: **On the Way**, **Reached**, **Helping**, **Done**.
6. Switch back to **Organisation**. Review helper/task status, in-app notices, completed-gig analytics, and worker earnings. The Sahaya alert remains in its existing workflow until an organisation separately updates it.
7. Use **Reset Demo** in Gig Management to reset only gig-worker demo tables and seeded worker profiles. Use Sahaya's existing control to reset its timeline separately.

## Verification

- Automated pytest suite in `elder-ml/tests`: **11 passed**. This includes the existing dashboard tests and five gig integration tests for eligibility, alert linkage/privacy, complete lifecycle/persistence, competing acceptance, and assets/labels.
- Python compilation passed for `src/dashboard.py` and `src/gigs.py`.
- `node --check` passed for `web/app.js` and `web/gigs.js`.
- The module tests use isolated SQLite databases. Static routes for the health dashboard, existing WhatsApp page, and Gig Management page/assets returned HTTP 200.
- Live HTTP workflow on `127.0.0.1:8765` verified worker registration and denial before approval/training, labelled synthetic reading and alert creation, alert-linked gig publishing, private-field redaction before acceptance, detail reveal after acceptance, full task lifecycle, admin notifications, earnings/analytics, and health-alert acknowledgement through `Action initiated` → `Help reached` → `Resolved`.
- After a server restart using the same isolated SQLite database, the completed gig, ₹450 earnings, and resolved alert state persisted.
- A live visible browser and mobile viewport check could not be completed. Edge window capture timed out twice. Therefore visual responsive layout, button click-through in a browser, and browser-console errors remain unverified. JavaScript syntax passed, but that does not replace browser testing.

## Limits and remaining integration work

- Local demo is unauthenticated and intended only for loopback development. Do not expose it to a network or use real personal/health information.
- Identity verification is an explicit synthetic demo status only; there is no Aadhaar verification, document collection, or external identity provider.
- Gig contact details and helper profiles are synthetic. No matching service, map/geocoding, payment/payout provider, SMS, WhatsApp delivery, or real care-provider integration is connected.
- Health replay and gig records share one SQLite file, but there is no transactional automatic alert closure when a gig completes. A completed task is not proof that a health incident is resolved.
- The app polls every five seconds; it does not use push delivery.
- Browser visual/responsive inspection, actual browser button click-through, and browser-console verification remain unverified because Edge capture timed out twice. The HTTP workflow and static assets were exercised independently.
- The M3 model remains a historical/offline/replay path. Live inference requires source minute-level streams, feature-window construction, dependency pinning, and a clinically reviewed policy for model score/alert disposition.

## Run locally (Windows / VS Code PowerShell)

```powershell
cd E:\Sahaya\elder-ml
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m src.dashboard
```

Open `http://127.0.0.1:8765`. To run tests in a development environment:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q tests
```

Verification command results for this integration change: `python -m pytest -q tests` (11 passed), `python -m py_compile src/dashboard.py src/gigs.py`, `node --check web/app.js`, and `node --check web/gigs.js`.

The suite was run from the final `E:\Sahaya\elder-ml` tree: **11 passed**. The target tree's Python files also compiled in memory, and both JavaScript syntax checks passed. Live HTTP checks were run against the staged full workflow and then the final target server with isolated SQLite files; no test database was retained in the project.

The default database is `elder-ml/reports/dashboard_demo.sqlite`. Keep local database files private and do not commit them.
