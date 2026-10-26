# Sahaya

This repository contains presentation and development projects from the ELDER workspace.

## Projects

- **elder-ml/** — elder wearable alerting dashboard, model artifacts, presentation replay data, and WhatsApp webhook/deployment prototype.
- **elder_vitals_14day/** — documentation and reproducible generator for the synthetic wearable benchmark.
- **WhatsUp/** — Flutter and Firebase chat application.
- **ibm_bob_proj/** — CareCircle elderly-support service prototype.

## Dataset files

The large raw Parquet and CSV benchmark datasets are not included. The generator and dataset documentation are included in `elder_vitals_14day/`. Regenerate the data locally before training or rebuilding the raw-data replay. Prepared presentation artifacts remain in `elder-ml/deployment_data/`.

## Local configuration

Environment files containing local tokens, webhook verification tokens, private runtime databases, logs, build outputs, and nested Git metadata are intentionally excluded. Use the included `.env.example` files to configure local development. Never commit actual credentials.

These are demonstration projects. Do not use sample profiles or model output for real care decisions.

## Combined Sahaya + Gig Worker localhost MVP

`elder-ml/` now serves the health replay and local CareCircle-style helper module from one Python process and one SQLite database (`elder-ml/reports/dashboard_demo.sqlite`). The original CareCircle project in `ibm_bob_proj/` remains separate and unchanged. The local Gig Management role switch is intentionally unauthenticated and is not access control.

Start from a VS Code PowerShell terminal:

```powershell
cd E:\Sahaya\elder-ml
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m src.dashboard
```

Open `http://127.0.0.1:8765`. In Sahaya, use **Simulate alert input**, review the new alert, then choose **Assign Helper / Create Gig**. Publish a Hospital accompaniment gig, switch to **Gig Worker**, select **Priya Nair (Demo Helper)**, accept it, and advance it through the task statuses. Switch back to **Organisation** to review progress, notifications, analytics, and completed-gig earnings. **Reset Demo** in Gig Management resets gig data only; the Sahaya timeline reset remains separate.

The M3 model remains connected through the prepared historical replay. New manual readings remain explicitly labelled rule-based demonstration inputs; the local demo does not invent the rolling feature history required for live M3 inference. See [FINAL_INTEGRATION_REPORT.md](FINAL_INTEGRATION_REPORT.md) for implementation details and verification limitations.
