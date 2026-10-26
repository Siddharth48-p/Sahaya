# Sahaya dashboard and elder-ml integration report

## Result

The project’s ML directory is `elder-ml` (there is no separate `elderml` directory). It contains a trained `models/m3_lightgbm.joblib` LightGBM classifier and working inference helpers in `src/acute_model.py`. I loaded the artifact and verified `predict_full` and `model_alerts` on an 80-minute synthetic feature stream. The artifact contains 94 feature names and its saved feature schema matches the model.

The dashboard is connected to the ML pipeline for **replay**: `reports/dashboard_vitals.csv` supplies its precomputed minute values, and `reports/alerts.jsonl` supplies precomputed alerts whose sources include `M3` and rules. The offline `src/cli.py evaluate` path trains or loads the M3 pipeline, calls `predict_full`/`model_alerts`, fuses model and rule alerts, and writes the replay artifacts. The dashboard does not load the joblib model itself.

New dashboard submissions are a separate, clearly labelled demonstration path. `POST /api/readings` validates the entered values, saves them in SQLite, compares them with recent replay baselines using `_classify_demo_input`, and creates a review alert when a configured demo rule fires. `POST /api/simulate` saves labelled synthetic examples. Neither endpoint calls M3 inference. A single submitted reading is not the 94-feature minute history the model requires.

## Data availability and limits

- The local dashboard replay feed and alert file are present in `reports/`. The adjacent `elder_vitals_14day` directory contains only `generate_dataset.py` and its README; the five Parquet streams and `events.csv` are absent. Therefore a new training/evaluation run against the source dataset and live M3 inference on newly submitted readings were not verified or connected.
- Do not interpret replay or demo rules as clinical results. All people, sensor streams, histories, and contact details are synthetic or placeholders. No live wearable stream, emergency response, care contact, or WhatsApp Cloud delivery is connected in this local demo.
- Loading the model emitted a scikit-learn version warning: the artifact’s `LabelEncoder` was saved with scikit-learn 1.8.0 and the installed environment has 1.9.1. Inference completed in the smoke check, but pinning the training environment is advisable before production use.
- Local mode is an unauthenticated loopback presentation server. The Vercel deployment has a separate authentication and API path.

## Fix made

The local server advertised an existing WhatsApp interface button, but `GET /whatsapp.html` returned 404. `src/dashboard.py` now serves the existing `web/whatsapp.html` page. No WhatsApp or ML feature was added.

## Verification performed

- All six tests in `elder-ml/tests` passed with pytest 9.1.1 and LightGBM 4.7.0 available. Tests were run with a temporary workspace-local `tmp_path` fixture because this verification environment denies writes to pytest-created temporary directories outside the writable workspace; pytest’s cache plugin was disabled because the repository itself is read-only here. The tests do not invoke LightGBM inference.
- The model artifact loaded; feature names matched (94); `predict_full` and `model_alerts` completed on a synthetic 80-minute feature frame (zero alerts for that baseline example).
- JavaScript syntax check (`node --check web/app.js`) passed.
- Backend HTTP smoke checks verified the health/state endpoints, static dashboard assets, manual reading persistence and display, synthetic source labelling, alert creation and transitions (`New` → `Action initiated` → `Help reached` → `Resolved`), profile history, and the WhatsApp page route. These use an isolated SQLite file and synthetic inputs.
- Browser-driven visual and click-through checks were not completed; Edge’s accessibility/screenshot capture timed out. No claim is made about pixel-level layout or browser-console errors.

## Run locally on Windows

From a VS Code PowerShell terminal:

```powershell
cd E:\Sahaya\elder-ml
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m src.dashboard
```

Open `http://127.0.0.1:8765`. For the unit suite, install the development dependencies and run:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q tests
```

To run the offline ML evaluation when the raw data files are available:

```powershell
python -m src.cli evaluate
```

The dashboard’s manual input remains a rule-based training demo. To enable M3 inference on live readings, provide the timestamped raw/minute history needed to build the model’s 94-feature causal window, preserve the model’s training dependency versions, and define how model scores combine with the current rule and review workflow. The missing raw streams/events are needed to reproduce training and independently validate that integration.

## Combined local gig-worker MVP verification (26 October 2026)

The dashboard now serves the local Gig Management module from the same Python server and SQLite database. The original CareCircle implementation remains separate and unchanged. See `FINAL_INTEGRATION_REPORT.md` for the full flow, exact commands, and limitations.

- Pytest: **11 passed**, including the two existing dashboard tests and five gig workflow tests.
- Python compilation and `node --check` for both Sahaya scripts passed.
- HTTP end-to-end checks passed for the worker eligibility gate, synthetic alert generation, alert-linked gig publishing, pre-accept privacy, accept/detail reveal, all five gig lifecycle states, notifications, earnings/analytics, Sahaya alert workflow transitions, and persistence across a server restart.
- The live workflow earned ₹450 in its isolated demo database. No Sahaya project database or CareCircle repository data was changed during testing.
- Browser visual inspection, mobile viewport, click-through, and browser-console checks remain unverified: Edge capture timed out twice. HTTP and static route checks succeeded.
- The role switcher, workers, identity state, client details, and gig records are local demonstration data. This is unauthenticated and not production-ready; no real Aadhaar/provider integration, payments, messaging delivery, or mapping service is connected.
