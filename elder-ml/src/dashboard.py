"""Local presentation dashboard for the synthetic elder wearable replay."""
from __future__ import annotations

import json
import math
import os
import sqlite3
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import pandas as pd

from .features import minute_features
from .io import data_dir, load_person
from . import gigs

PROJECT = Path(__file__).resolve().parents[1]
WEB = PROJECT / "web"
REPORTS = PROJECT / "reports"
ASSET_DIR = PROJECT / "deployment_data" if os.environ.get("VERCEL") else REPORTS
FEED_FILE = ASSET_DIR / "dashboard_vitals.csv"
DB_FILE = REPORTS / "dashboard_demo.sqlite"
PEOPLE = {
    "E1": {"name": "Maya Chen", "age": 72, "conditions": ["Type 2 diabetes", "Hypertension"], "medications": ["Metformin · example entry", "Losartan · example entry"], "symptoms": ["Dizziness", "Low energy"], "baseline": "HR 76 bpm · SpO₂ 96.5% · BP 138/84", "monitoring_focus": "A dizziness-like episode with a heart-rate rise and systolic pressure drop is highlighted for staff review.", "story": "The profile includes diabetes and hypertension. In this training record, dizziness is paired with a changing heart-rate and blood-pressure pattern.", "possible_context": "A dizziness episode can have many causes. This record shows a personal heart-rate and blood-pressure shift; wearable readings alone cannot confirm low glucose or explain why it occurred.", "client_phone": "+1 (202) 555-0101", "family_name": "Riya Chen · daughter", "family_phone": "+1 (202) 555-0102", "care_site": "Northstar Care Centre · directory example", "care_phone": "+1 (202) 555-0151", "history_examples": [{"date":"2026-10-02 09:20","summary":"Dizziness with lower-than-usual blood pressure","tier":"Yellow","outcome":"Family check-in completed; symptoms settled in the example record."},{"date":"2026-10-05 14:10","summary":"Brief light-headed episode","tier":"Yellow","outcome":"Wellbeing call logged; no further change noted in the example record."}]},
    "E2": {"name": "Arthur Reed", "age": 68, "conditions": ["No chronic condition listed"], "medications": ["No medication listed"], "symptoms": ["Fatigue during illness-like phase"], "baseline": "HR 66 bpm · SpO₂ 97.5% · BP 122/77", "monitoring_focus": "The illness-like phase is shown through changes in resting heart rate, temperature and oxygen relative to baseline.", "possible_context": "A gradual resting heart-rate, temperature or oxygen change may have several explanations, including an illness, activity recovery or sensor variation. This record cannot determine the cause.", "story": "The example record has no chronic condition listed. A gradual resting-pattern shift is used to demonstrate trend review.", "client_phone": "+1 (202) 555-0103", "family_name": "Nina Reed · daughter", "family_phone": "+1 (202) 555-0104", "care_site": "Northstar Care Centre · directory example", "care_phone": "+1 (202) 555-0151", "history_examples": [{"date":"2026-10-03 08:30","summary":"Resting heart-rate trend above baseline","tier":"Yellow","outcome":"Wellbeing call completed; record closed after follow-up."},{"date":"2026-10-06 19:05","summary":"Fatigue and temperature trend review","tier":"Yellow","outcome":"Home check requested; no escalation in the example record."}]},
    "E3": {"name": "Leena Kapoor", "age": 79, "conditions": ["Hypertension"], "medications": ["Amlodipine · example entry", "Lisinopril · example entry"], "symptoms": ["Headache during pressure surges"], "baseline": "HR 80 bpm · SpO₂ 96% · BP 152/92", "monitoring_focus": "Sustained blood-pressure changes are compared with this profile’s higher baseline.", "possible_context": "The report reflects a sustained rise from this profile’s usual pressure. Activity, stress, symptoms, measurement variation and other factors can affect a reading; the alert does not establish a cause.", "story": "The profile includes hypertension and a higher usual blood-pressure range. Sustained changes from the personal baseline are highlighted.", "client_phone": "+1 (202) 555-0105", "family_name": "Arjun Kapoor · son", "family_phone": "+1 (202) 555-0106", "care_site": "Northstar Care Centre · directory example", "care_phone": "+1 (202) 555-0151", "history_examples": [{"date":"2026-10-01 16:40","summary":"Sustained pressure above personal baseline","tier":"Yellow","outcome":"Nurse review arranged; follow-up reading recorded."},{"date":"2026-10-06 17:15","summary":"Evening pressure rise with headache reported","tier":"Red","outcome":"Urgent review initiated in the example record; status later closed."}]},
    "E4": {"name": "Samuel Brooks", "age": 75, "conditions": ["COPD profile"], "medications": ["Inhaler · example entry", "Tiotropium · example entry"], "symptoms": ["Breathlessness", "Night-time oxygen dips"], "baseline": "HR 82 bpm · SpO₂ 93.5% · BP 132/80", "monitoring_focus": "Night-time and activity-related oxygen changes are highlighted against this profile’s lower baseline.", "possible_context": "Oxygen changes may relate to activity, sleep, respiratory symptoms or sensor fit. The pattern is for staff review and does not identify the underlying cause.", "story": "The profile includes COPD and a lower usual oxygen reading. Overnight and activity-related changes are highlighted for staff review.", "client_phone": "+1 (202) 555-0107", "family_name": "Helen Brooks · spouse", "family_phone": "+1 (202) 555-0108", "care_site": "Northstar Care Centre · directory example", "care_phone": "+1 (202) 555-0151", "history_examples": [{"date":"2026-10-02 02:15","summary":"Night-time oxygen change from usual pattern","tier":"Yellow","outcome":"Morning wellbeing call documented in the example record."},{"date":"2026-10-06 11:25","summary":"Breathlessness and oxygen trend during activity","tier":"Red","outcome":"Home assessment requested; later marked resolved in the example record."}]},
    "E5": {"name": "Owen Patel", "age": 70, "conditions": ["AF-like episodes in training record"], "medications": ["No medication listed"], "symptoms": ["Palpitations", "Fall events in record"], "baseline": "HR 72 bpm · SpO₂ 96.8% · BP 134/82", "monitoring_focus": "Irregular-rate patterns and an impact followed by stillness are highlighted for staff review.", "possible_context": "Impact followed by stillness may indicate a fall, but a device impact or removal can look similar. A person should verify the client’s status.", "story": "The profile includes intermittent irregular-rate episodes and prior falls in the training record. An impact followed by stillness is routed to the highest alert tier.", "client_phone": "+1 (202) 555-0109", "family_name": "Dev Patel · son", "family_phone": "+1 (202) 555-0110", "care_site": "Northstar Care Centre · directory example", "care_phone": "+1 (202) 555-0151", "history_examples": [{"date":"2026-10-03 13:20","summary":"Palpitations and irregular-rate pattern","tier":"Yellow","outcome":"Family contacted; check-in completed in the example record."},{"date":"2026-10-07 19:40","summary":"Possible fall pattern followed by stillness","tier":"Red","outcome":"In-person wellbeing check arranged; case later closed in the example record."}]},
}
LOCK = threading.RLock()
STATE = {"index": 0, "speed": 3600, "fraction": 0.0, "paused": False, "last_tick": time.monotonic(), "active": {}, "triggered": set(), "started": False}
FEED: pd.DataFrame | None = None
ALERTS: list[dict] = []
ALERTS_AT: dict[int, list[dict]] = {}
TIME_AXIS: list[pd.Timestamp] = []
TOTAL_MINUTES = 0


def _db():
    con = sqlite3.connect(DB_FILE)
    con.execute("CREATE TABLE IF NOT EXISTS snapshots (minute TEXT NOT NULL, person_id TEXT NOT NULL, hr REAL, spo2 REAL, sbp REAL, dbp REAL, temp REAL, motion REAL, PRIMARY KEY(minute, person_id))")
    con.execute("CREATE TABLE IF NOT EXISTS workflow (incident_id TEXT PRIMARY KEY, status TEXT NOT NULL, updated TEXT NOT NULL, note TEXT NOT NULL DEFAULT '')")
    con.execute("CREATE TABLE IF NOT EXISTS workflow_log (entry_id INTEGER PRIMARY KEY AUTOINCREMENT, incident_id TEXT NOT NULL, status TEXT NOT NULL, updated TEXT NOT NULL)")
    con.execute("CREATE TABLE IF NOT EXISTS demo_readings (reading_id TEXT PRIMARY KEY, person_id TEXT NOT NULL, observed_at TEXT NOT NULL, values_json TEXT NOT NULL, simulated INTEGER NOT NULL DEFAULT 0)")
    con.execute("CREATE INDEX IF NOT EXISTS demo_readings_person_time_idx ON demo_readings(person_id,observed_at DESC)")
    con.execute("CREATE TABLE IF NOT EXISTS demo_incidents (incident_id TEXT PRIMARY KEY, person_id TEXT NOT NULL, start_ts TEXT NOT NULL, tier TEXT NOT NULL, summary TEXT NOT NULL, reason_text TEXT NOT NULL, sources TEXT NOT NULL, source_label TEXT NOT NULL)")
    return con


def _load_feed():
    global FEED, ALERTS, ALERTS_AT, TIME_AXIS, TOTAL_MINUTES
    if not os.environ.get("VERCEL"):
        REPORTS.mkdir(exist_ok=True)
    if FEED_FILE.exists():
        FEED = pd.read_csv(FEED_FILE, parse_dates=["minute"])
    else:
        parts = []
        root = data_dir()
        for person in PEOPLE:
            raw = load_person(person, root)
            mins = minute_features(raw)
            keep = mins[["minute", "hr_bpm_mean", "spo2_pct_mean", "sbp_mmhg_mean", "dbp_mmhg_mean", "skin_temp_c_mean", "motion_g_mean"]].copy()
            keep.insert(1, "person_id", person)
            keep.columns = ["minute", "person_id", "hr", "spo2", "sbp", "dbp", "temp", "motion"]
            parts.append(keep)
            del raw, mins
        FEED = pd.concat(parts, ignore_index=True)
        FEED.to_csv(FEED_FILE, index=False)
    FEED["minute"] = pd.to_datetime(FEED.minute)
    FEED = FEED.sort_values(["minute", "person_id"]).reset_index(drop=True)
    TIME_AXIS = [pd.Timestamp(ts) for ts in FEED.minute.drop_duplicates()]
    TOTAL_MINUTES = len(TIME_AXIS)
    id_to_index = {ts: i for i, ts in enumerate(TIME_AXIS)}
    alert_file = ASSET_DIR / "alerts.jsonl"
    if alert_file.exists():
        for line in alert_file.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
                row["_index"] = id_to_index.get(pd.Timestamp(row["start_ts"]).floor("min"), 0)
                # The dashboard has two urgency zones: Orange model/rule escalations are shown as Red.
                row["display_tier"] = "Red" if row.get("tier") in {"Red", "Orange"} else "Yellow"
                row["summary"] = _summary(row)
                ALERTS.append(row)
                ALERTS_AT.setdefault(row["_index"], []).append(row)
            except (ValueError, KeyError, TypeError):
                continue
    ALERTS.sort(key=lambda a: (a["_index"], a["person_id"]))


def _restore_demo_incidents():
    con = _db()
    rows = con.execute("SELECT d.*,COALESCE(w.status,'New') FROM demo_incidents d LEFT JOIN workflow w ON w.incident_id=d.incident_id WHERE COALESCE(w.status,'New')!='Resolved'").fetchall()
    con.close()
    for row in rows:
        incident_id, person_id, start_ts, tier, summary, reason, sources, source_label, status = row
        STATE["active"][incident_id] = {"incident_id": incident_id, "person_id": person_id,
            "start_ts": start_ts, "tier_reached_ts": start_ts, "end_ts": start_ts,
            "tier": tier, "sources": sources, "reason_text": reason,
            "suggested_action": "Human review of submitted demonstration input",
            "_index": STATE["index"], "display_tier": tier, "summary": summary,
            "source_label": source_label, "status": status}
        STATE["triggered"].add(incident_id)
    if STATE["active"]:
        STATE["paused"] = True


def _summary(alert):
    source = alert.get("sources", "")
    text = alert.get("reason_text", "")
    if "fall" in source.lower() or "fall" in text.lower():
        return "Possible fall detected · impact followed by sustained stillness"
    if "spo2" in text.lower() or "oxygen" in text.lower() or "desaturation" in text.lower():
        return "Oxygen trend moved outside this profile’s recent pattern"
    if "pressure" in text.lower() or "bp" in source.lower():
        return "Blood pressure pattern moved outside this profile’s recent pattern"
    if "heart" in text.lower() or "af" in source.lower():
        return "Heart-rate pattern moved outside this profile’s recent pattern"
    return "Multiple signals changed from this profile’s recent pattern"


def _category(alert):
    source = alert.get("sources", "").lower()
    summary = alert.get("summary", "").lower()
    if "fall" in source or "fall" in summary or "impact" in summary: return "fall"
    if "oxygen" in summary or "spo2" in summary or "desaturation" in source: return "oxygen"
    if "pressure" in summary or "hypertens" in source: return "pressure"
    if "heart" in summary or "af" in source: return "rhythm"
    return "general"


def _decorate_alert(alert):
    profile = PEOPLE[alert["person_id"]]
    category = _category(alert)
    previous = [a for a in ALERTS if a["person_id"] == alert["person_id"] and a["_index"] < alert["_index"] and _category(a) == category]
    similar = list(profile.get("history_examples", [])) + [{"date": a["start_ts"], "summary": a["summary"], "tier": a["display_tier"], "outcome": "Example outcome: staff check-in completed and case marked resolved in the training record."} for a in previous[-3:]]
    red = alert["display_tier"] == "Red"
    if red:
        actions = ["Confirm the client’s immediate status using the organisation’s on-call process.", "Request help at home or an in-person check if the client cannot be reached.", "Contact the hospital through the organisation-approved pathway; follow local emergency procedures if there may be immediate danger."]
    else:
        actions = ["Arrange a wellbeing call and ask about current symptoms.", "Ask staff to review the latest readings and repeat the measurement if appropriate.", "Consider a home check if the change persists or the client feels worse."]
    if category == "fall":
        actions = ["Try the client contact and request an immediate in-person wellbeing check.", "If the client is injured or cannot be reached, use the organisation’s urgent escalation procedure.", "Record who accepted the response and when."]
    return {**alert, "source_label": alert.get("source_label") or ("Model + rule replay" if "M3" in alert.get("sources", "") else "Rule replay"),
            "client_name": profile["name"], "profile_story": profile["story"],
            "why_flagged": alert.get("reason_text") or alert["summary"], "similar_cases": similar[-4:],
            "similar_case_count": len(profile.get("history_examples", [])) + len(previous), "actions": actions,
            "contacts": [{"label": "Client", "name": profile["name"], "number": profile["client_phone"]},
                         {"label": "Family contact", "name": profile["family_name"], "number": profile["family_phone"]},
                         {"label": "Hospital / care centre", "name": profile["care_site"], "number": profile["care_phone"]}]}


def _snapshot_rows(index):
    assert FEED is not None
    start = index * len(PEOPLE)
    rows = FEED.iloc[start:start + len(PEOPLE)]
    ts = rows.minute.iloc[0]
    return ts, {r.person_id: r for r in rows.itertuples(index=False)}


def _store_snapshot(index):
    ts, rows = _snapshot_rows(index)
    con = _db()
    con.executemany("INSERT OR REPLACE INTO snapshots VALUES (?,?,?,?,?,?,?,?)", [
        (ts.isoformat(), p, _num(r.hr), _num(r.spo2), _num(r.sbp), _num(r.dbp), _num(r.temp), _num(r.motion)) for p, r in rows.items()
    ])
    con.commit(); con.close()


def _tick_locked():
    now = time.monotonic()
    if not STATE["started"]:
        STATE["last_tick"] = now
        return
    elapsed = max(0, now - STATE["last_tick"])
    STATE["last_tick"] = now
    if STATE["paused"] or FEED is None:
        return
    # Playback speed follows normal clock speed: 60 simulated minutes per real hour at 1×.
    accumulated = elapsed * STATE["speed"] / 60 + STATE["fraction"]
    total = int(accumulated)
    STATE["fraction"] = accumulated - total
    if total <= 0:
        return
    last = TOTAL_MINUTES - 1
    target = min(last, STATE["index"] + total)
    con = _db()
    for idx in range(STATE["index"] + 1, target + 1):
        ts, rows = _snapshot_rows(idx)
        con.executemany("INSERT OR REPLACE INTO snapshots VALUES (?,?,?,?,?,?,?,?)", [
            (ts.isoformat(), p, _num(r.hr), _num(r.spo2), _num(r.sbp), _num(r.dbp), _num(r.temp), _num(r.motion)) for p, r in rows.items()
        ])
        new_alerts = [a for a in ALERTS_AT.get(idx, []) if a["incident_id"] not in STATE["triggered"]]
        for alert in new_alerts:
            STATE["triggered"].add(alert["incident_id"])
            STATE["active"][alert["incident_id"]] = {**alert, "status": "New"}
        STATE["index"] = idx
        if new_alerts:
            STATE["paused"] = True
            STATE["fraction"] = 0.0
            STATE["last_tick"] = time.monotonic()
            break
    con.commit()
    con.close()
    if STATE["index"] >= last:
        STATE["paused"] = True


def _num(v):
    return None if pd.isna(v) else round(float(v), 2)


def _vitals(index):
    ts, rows = _snapshot_rows(index)
    result = {}
    for pid in PEOPLE:
        r = rows.get(pid)
        result[pid] = {"hr": _num(r.hr) if r else None, "spo2": _num(r.spo2) if r else None,
                       "sbp": _num(r.sbp) if r else None, "dbp": _num(r.dbp) if r else None,
                       "temp": _num(r.temp) if r else None, "motion": _num(r.motion) if r else None}
    con = _db()
    recent = con.execute("SELECT person_id,observed_at,values_json,simulated FROM demo_readings ORDER BY observed_at DESC").fetchall()
    con.close()
    seen = set()
    for pid, observed_at, values_json, simulated in recent:
        values = json.loads(values_json)
        if pid not in seen:
            seen.add(pid)
            result[pid]["input_source"] = "Synthetic demo input" if simulated else "Submitted reading"
            result[pid]["input_time"] = observed_at
        for key, value in values.items():
            if key not in result[pid].get("_input_values", {}):
                result[pid].setdefault("_input_values", {})[key] = value
    for pid in seen:
        result[pid].update(result[pid].pop("_input_values", {}))
    return ts, result


def _baseline(person_id, field, limit=180):
    column = {"hr": "hr", "spo2": "spo2", "sbp": "sbp", "dbp": "dbp", "temp": "temp", "motion": "motion"}[field]
    ts, _ = _snapshot_rows(STATE["index"])
    rows = FEED[(FEED.person_id == person_id) & (FEED.minute <= ts)][column].dropna().tail(limit)
    return float(rows.median()) if not rows.empty else None


def _classify_demo_input(person_id, values):
    """Conservative demonstration rules. These are not ML inference or clinical thresholds."""
    baseline = {key: _baseline(person_id, key) for key in values}
    if values.get("motion", 0) >= 1.5:
        return "Red", "Impact-like movement reading", "High movement value recorded; check the person directly. A single sensor reading cannot confirm a fall."
    if values.get("spo2", 100) <= 88 or values.get("hr", 0) >= 140 or values.get("hr", 100) <= 40 or values.get("sbp", 0) >= 200:
        return "Red", "Configured demonstration threshold crossed", "One submitted value crossed a demonstration threshold; verify the measurement and check the person directly."
    changes = []
    if "spo2" in values and baseline.get("spo2") is not None and values["spo2"] <= baseline["spo2"] - 3:
        changes.append("oxygen below the recent replay baseline")
    if "hr" in values and baseline.get("hr") is not None and abs(values["hr"] - baseline["hr"]) >= 25:
        changes.append("heart rate changed from the recent replay baseline")
    if "sbp" in values and baseline.get("sbp") is not None and abs(values["sbp"] - baseline["sbp"]) >= 30:
        changes.append("systolic pressure changed from the recent replay baseline")
    if changes:
        return "Yellow", "Submitted reading differs from replay baseline", "; ".join(changes) + ". This is a rule-based demo indicator for human review, not a diagnosis."
    return None


def _record_reading(person_id, values, simulated=False):
    observed = datetime.now().astimezone().isoformat(timespec="seconds")
    reading_id = f"{person_id}-input-{int(time.time() * 1000)}"
    indicator = _classify_demo_input(person_id, values)
    con = _db()
    con.execute("INSERT INTO demo_readings(reading_id,person_id,observed_at,values_json,simulated) VALUES (?,?,?,?,?)",
                (reading_id, person_id, observed, json.dumps(values, allow_nan=False), int(simulated)))
    if indicator:
        tier, summary, reason = indicator
        incident_id = f"{reading_id}-alert"
        raw = {"incident_id": incident_id, "person_id": person_id, "start_ts": observed,
               "tier_reached_ts": observed, "end_ts": observed, "tier": tier,
               "sources": "demo_rule", "reason_text": reason, "suggested_action": "Human review of submitted demonstration input",
               "_index": STATE["index"], "display_tier": tier, "summary": summary,
               "source_label": "Rule-based demo input" if simulated else "Rule-based submitted reading", "status": "New"}
        con.execute("INSERT INTO demo_incidents VALUES (?,?,?,?,?,?,?,?)",
                    (incident_id, person_id, observed, tier, summary, reason, "demo_rule", raw["source_label"]))
        con.execute("INSERT OR REPLACE INTO workflow(incident_id,status,updated,note) VALUES (?,?,?,?)", (incident_id, "New", observed, summary))
        STATE["active"][incident_id] = raw
        STATE["triggered"].add(incident_id)
        STATE["paused"] = True
        STATE["fraction"] = 0.0
    con.commit(); con.close()
    return indicator


def _state():
    _tick_locked()
    ts, vitals = _vitals(STATE["index"])
    alert_by_person = {}
    for alert in STATE["active"].values():
        alert_by_person.setdefault(alert["person_id"], []).append(alert)
    clients = []
    for pid, profile in PEOPLE.items():
        clients.append({"id": pid, **profile, "vitals": vitals[pid], "alerts": alert_by_person.get(pid, [])})
    current_active = [_decorate_alert(a) for a in STATE["active"].values()]
    return {"now": ts.isoformat(), "speed": STATE["speed"], "paused": STATE["paused"], "started": STATE["started"],
            "complete": STATE["index"] >= TOTAL_MINUTES - 1, "index": STATE["index"], "total": TOTAL_MINUTES,
            "clients": clients, "active_alerts": current_active,
            "yellow_count": sum(a["display_tier"] == "Yellow" for a in current_active),
            "red_count": sum(a["display_tier"] == "Red" for a in current_active)}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def _send(self, body, code=200, mime="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else (json.dumps(body, ensure_ascii=False, default=str).encode("utf-8") if mime.startswith("application/json") else body.encode("utf-8"))
        self.send_response(code); self.send_header("Content-Type", mime); self.send_header("Content-Length", str(len(data))); self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/" or path == "/index.html":
            return self._send((WEB / "index.html").read_bytes(), mime="text/html; charset=utf-8")
        if path == "/whatsapp.html":
            return self._send((WEB / "whatsapp.html").read_bytes(), mime="text/html; charset=utf-8")
        if path == "/gigs.html":
            return self._send((WEB / "gigs.html").read_bytes(), mime="text/html; charset=utf-8")
        if path in {"/gigs.css", "/gigs.js"}:
            mime = "text/css; charset=utf-8" if path.endswith(".css") else "text/javascript; charset=utf-8"
            return self._send((WEB / path[1:]).read_bytes(), mime=mime)
        if path in {"/styles.css", "/app.js"}:
            return self._send((WEB / path[1:]).read_bytes(), mime="text/css; charset=utf-8" if path.endswith("css") else "text/javascript; charset=utf-8")
        if path == "/api/health":
            return self._send({"ok": FEED is not None, "profiles": len(PEOPLE), "replay_minutes": TOTAL_MINUTES,
                               "replay_alerts": len(ALERTS), "reading_input": True})
        if path.startswith("/api/gigs/"):
            with LOCK:
                alerts = [_decorate_alert(a) for a in STATE["active"].values()]
                code, result = gigs.dispatch(DB_FILE, "GET", path,
                    query_string=urlparse(self.path).query, alerts=alerts)
            return self._send(result, code)
        with LOCK:
            if path == "/api/state": return self._send(_state())
            if path == "/api/profile":
                pid = parse_qs(urlparse(self.path).query).get("id", [""])[0]
                if pid not in PEOPLE: return self._send({"error": "Unknown profile"}, 404)
                ts, vitals = _vitals(STATE["index"])
                con = _db()
                history = con.execute("SELECT minute,hr,spo2,sbp,dbp FROM snapshots WHERE person_id=? ORDER BY minute DESC LIMIT 180", (pid,)).fetchall()
                actions = con.execute("SELECT incident_id,status,updated FROM workflow_log WHERE incident_id IN (SELECT incident_id FROM workflow WHERE incident_id LIKE ?) ORDER BY entry_id DESC LIMIT 20", (f"{pid}-%",)).fetchall()
                input_rows = con.execute("SELECT observed_at,values_json FROM demo_readings WHERE person_id=? ORDER BY observed_at DESC LIMIT 180", (pid,)).fetchall()
                manual_alerts = con.execute("SELECT d.*,COALESCE(w.status,'New') FROM demo_incidents d LEFT JOIN workflow w ON w.incident_id=d.incident_id WHERE d.person_id=? ORDER BY d.start_ts", (pid,)).fetchall()
                history.reverse()
                history = [{"minute": r[0], "hr": r[1], "spo2": r[2], "sbp": r[3], "dbp": r[4]} for r in history]
                history.extend({"minute": r[0], **json.loads(r[1])} for r in reversed(input_rows))
                profile_alerts = [_decorate_alert(a) for a in ALERTS if a["person_id"] == pid and a["_index"] <= STATE["index"]]
                for a in manual_alerts:
                    raw = {"incident_id": a[0], "person_id": a[1], "start_ts": a[2], "tier": a[3], "summary": a[4], "reason_text": a[5], "sources": a[6], "source_label": a[7], "status": a[8], "display_tier": a[3], "_index": STATE["index"]}
                    profile_alerts.append(_decorate_alert(raw))
                con.close()
                return self._send({"id": pid, **PEOPLE[pid], "vitals": vitals[pid], "now": ts.isoformat(), "history": history, "workflow_history": [{"incident_id": r[0], "status": r[1], "updated": r[2]} for r in actions], "alerts": profile_alerts})
        return self._send({"error": "Not found"}, 404)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 16_384:
                return self._send({"error": "Request must contain a JSON body smaller than 16 KB."}, 413 if length > 16_384 else 400)
            data = json.loads(self.rfile.read(length))
        except (ValueError, TypeError, json.JSONDecodeError):
            return self._send({"error": "Invalid JSON request body."}, 400)
        with LOCK:
            path = urlparse(self.path).path
            if path.startswith("/api/gigs/"):
                alerts = [_decorate_alert(a) for a in STATE["active"].values()]
                code, result = gigs.dispatch(DB_FILE, "POST", path, data,
                    query_string=urlparse(self.path).query, alerts=alerts)
                return self._send(result, code)
            if self.path in {"/api/readings", "/api/simulate"}:
                person_id = str(data.get("person_id", ""))
                if person_id not in PEOPLE:
                    return self._send({"error": "Choose a client from the demonstration directory."}, 422)
                simulated = self.path == "/api/simulate"
                if simulated:
                    scenario = data.get("scenario", "low_oxygen")
                    if scenario == "baseline_change":
                        base = _baseline(person_id, "hr") or 72
                        values = {"hr": round(base + 30, 1)}
                    elif scenario == "normal":
                        values = {"hr": round(_baseline(person_id, "hr") or 72, 1), "spo2": round(_baseline(person_id, "spo2") or 96, 1)}
                    else:
                        base = _baseline(person_id, "spo2") or 96
                        values = {"spo2": round(min(88, base - 9), 1)}
                else:
                    payload = data.get("values")
                    if not isinstance(payload, dict):
                        return self._send({"error": "Enter at least one vital or activity reading."}, 422)
                    limits = {"hr": (25, 240), "spo2": (50, 100), "sbp": (50, 300), "dbp": (30, 200), "temp": (25, 45), "motion": (0, 16)}
                    if not payload or any(k not in limits for k in payload):
                        return self._send({"error": "Use heart rate, oxygen, blood pressure, temperature, or movement fields."}, 422)
                    values = {}
                    for key, value in payload.items():
                        try: value = float(value)
                        except (TypeError, ValueError): return self._send({"error": f"Enter a number for {key}."}, 422)
                        low, high = limits[key]
                        if not math.isfinite(value) or not low <= value <= high:
                            return self._send({"error": f"{key} must be between {low} and {high}."}, 422)
                        values[key] = value
                indicator = _record_reading(person_id, values, simulated)
                state = _state()
                state["input_notice"] = ("Demo reading saved; a rule-based indicator was raised for human review." if indicator else "Reading saved; no configured demo rule was crossed.")
                state["input_source"] = "synthetic" if simulated else "submitted"
                return self._send(state)
            if self.path == "/api/control":
                action = data.get("action")
                if action == "start": STATE["started"] = True; STATE["paused"] = False; _store_snapshot(STATE["index"])
                elif action == "pause": STATE["paused"] = True
                elif action == "resume" and not STATE["active"]: STATE["paused"] = False; STATE["started"] = True
                elif action == "reset":
                    STATE.update(index=0, speed=3600, fraction=0.0, paused=False, last_tick=time.monotonic(), active={}, triggered=set(), started=False)
                    con = _db(); con.execute("DELETE FROM snapshots"); con.execute("DELETE FROM workflow"); con.execute("DELETE FROM workflow_log"); con.execute("DELETE FROM demo_readings"); con.execute("DELETE FROM demo_incidents"); con.commit(); con.close()
                STATE["last_tick"] = time.monotonic()
                return self._send(_state())
            if self.path == "/api/speed":
                STATE["speed"] = int(data.get("speed", 3600)); STATE["last_tick"] = time.monotonic()
                return self._send(_state())
            if self.path == "/api/workflow":
                incident_id, action = data.get("incident_id"), data.get("action")
                alert = STATE["active"].get(incident_id)
                if alert:
                    allowed = {"New": "Action initiated", "Action initiated": "Help reached", "Help reached": "Resolved"}
                    if allowed.get(alert["status"]) == action:
                        alert["status"] = action
                        updated = datetime.now().isoformat(timespec="seconds")
                        con = _db(); con.execute("INSERT OR REPLACE INTO workflow(incident_id,status,updated,note) VALUES (?,?,?,?)", (incident_id, action, updated, action)); con.execute("INSERT INTO workflow_log(incident_id,status,updated) VALUES (?,?,?)", (incident_id, action, updated)); con.commit(); con.close()
                        if action == "Resolved": del STATE["active"][incident_id]
                        if not STATE["active"]:
                            STATE["paused"] = False; STATE["started"] = True; STATE["last_tick"] = time.monotonic()
                return self._send(_state())
        return self._send({"error": "Not found"}, 404)


def main():
    _load_feed()
    _restore_demo_incidents()
    gigs.initialize(DB_FILE)
    print("Synthetic presentation dashboard: http://127.0.0.1:8765")
    print("Building / loading the minute-by-minute synthetic replay may take a few minutes on first launch.")
    ThreadingHTTPServer(("127.0.0.1", 8765), Handler).serve_forever()


if __name__ == "__main__": main()
