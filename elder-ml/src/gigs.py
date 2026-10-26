"""Local-only Sahaya/CareCircle gig workflow backed by the Sahaya SQLite file."""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs

CATEGORIES = [
    "Hospital accompaniment", "Medicine pickup", "Grocery assistance", "Companionship",
    "Walking assistance", "Household assistance", "Technology assistance", "Scheduled welfare check",
]
LOCATIONS = [
    "Udupi", "Manipal", "Malpe", "Brahmavar", "Kaup", "Padubidri", "Karkala", "Hebri",
    "Kundapura", "Byndoor", "Shirva", "Kota", "Parkala", "Indrali", "Alevoor",
    "Santhekatte", "Katapady", "Perdoor", "Hiriadka",
]
FLOW = {"accepted": "on_the_way", "on_the_way": "reached", "reached": "helping", "helping": "done"}
DEMO_IDENTITY_LABEL = "Synthetic demo identity status — not Aadhaar verification"


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def _json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _connect(db_file: str | Path):
    path = Path(db_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=20, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=20000")
    return con


def initialize(db_file: str | Path) -> None:
    """Additive initialization; does not alter Sahaya tables or replay records."""
    con = _connect(db_file)
    con.executescript("""
      CREATE TABLE IF NOT EXISTS gig_workers (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, age INTEGER NOT NULL CHECK(age BETWEEN 18 AND 100),
        phone TEXT NOT NULL UNIQUE, address TEXT NOT NULL, languages_json TEXT NOT NULL,
        skills_json TEXT NOT NULL, categories_json TEXT NOT NULL, location TEXT NOT NULL,
        identity_demo_verified INTEGER NOT NULL DEFAULT 0, admin_approved INTEGER NOT NULL DEFAULT 0,
        training_completed INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1,
        available INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS helper_gigs (
        id TEXT PRIMARY KEY, title TEXT NOT NULL, category TEXT NOT NULL, description TEXT NOT NULL,
        instructions TEXT NOT NULL, client_name TEXT NOT NULL, client_contact TEXT NOT NULL,
        client_address TEXT NOT NULL, location TEXT NOT NULL, scheduled_date TEXT NOT NULL,
        scheduled_time TEXT NOT NULL, duration_hours INTEGER NOT NULL, payout_inr INTEGER NOT NULL,
        required_skills_json TEXT NOT NULL, priority TEXT NOT NULL, related_patient_id TEXT NOT NULL DEFAULT '',
        related_alert_id TEXT NOT NULL DEFAULT '', status TEXT NOT NULL, worker_id TEXT,
        created_at TEXT NOT NULL, published_at TEXT, accepted_at TEXT, completed_at TEXT,
        FOREIGN KEY(worker_id) REFERENCES gig_workers(id)
      );
      CREATE INDEX IF NOT EXISTS helper_gigs_status_created_idx ON helper_gigs(status, created_at DESC);
      CREATE INDEX IF NOT EXISTS helper_gigs_worker_idx ON helper_gigs(worker_id, status, created_at DESC);
      CREATE TABLE IF NOT EXISTS helper_gig_decisions (
        gig_id TEXT NOT NULL REFERENCES helper_gigs(id) ON DELETE CASCADE,
        worker_id TEXT NOT NULL REFERENCES gig_workers(id) ON DELETE CASCADE,
        decision TEXT NOT NULL CHECK(decision IN ('passed','accepted')),
        created_at TEXT NOT NULL, PRIMARY KEY(gig_id, worker_id)
      );
      CREATE TABLE IF NOT EXISTS helper_gig_history (
        id TEXT PRIMARY KEY, gig_id TEXT NOT NULL REFERENCES helper_gigs(id) ON DELETE CASCADE,
        worker_id TEXT NOT NULL REFERENCES gig_workers(id), status TEXT NOT NULL,
        created_at TEXT NOT NULL
      );
      CREATE INDEX IF NOT EXISTS helper_gig_history_gig_idx ON helper_gig_history(gig_id, created_at);
      CREATE TABLE IF NOT EXISTS helper_gig_notifications (
        id TEXT PRIMARY KEY, audience TEXT NOT NULL CHECK(audience IN ('admin','worker')),
        worker_id TEXT, event_type TEXT NOT NULL, title TEXT NOT NULL, message TEXT NOT NULL,
        gig_id TEXT, read_at TEXT, created_at TEXT NOT NULL,
        FOREIGN KEY(worker_id) REFERENCES gig_workers(id),
        FOREIGN KEY(gig_id) REFERENCES helper_gigs(id) ON DELETE SET NULL
      );
      CREATE INDEX IF NOT EXISTS helper_gig_notifications_recent_idx ON helper_gig_notifications(audience, read_at, created_at DESC);
      CREATE TABLE IF NOT EXISTS helper_gig_earnings (
        id TEXT PRIMARY KEY, gig_id TEXT NOT NULL UNIQUE REFERENCES helper_gigs(id),
        worker_id TEXT NOT NULL REFERENCES gig_workers(id), amount_inr INTEGER NOT NULL CHECK(amount_inr>=0),
        created_at TEXT NOT NULL
      );
    """)
    _seed_workers(con)
    con.close()


def _seed_workers(con) -> None:
    if con.execute("SELECT 1 FROM gig_workers LIMIT 1").fetchone():
        return
    now = _now()
    categories = ["Hospital accompaniment", "Medicine pickup", "Grocery assistance", "Companionship", "Walking assistance", "Household assistance", "Technology assistance", "Scheduled welfare check"]
    con.execute("""INSERT INTO gig_workers(id,name,age,phone,address,languages_json,skills_json,categories_json,location,
      identity_demo_verified,admin_approved,training_completed,active,available,created_at)
      VALUES(?,?,?,?,?,?,?,?,?,1,1,1,1,1,?)""",
      ("demo_worker_priya", "Priya Nair (Demo Helper)", 29, "+91 00000 00001", "Synthetic demo address, Manipal, Udupi",
       _json(["Kannada", "English"]), _json(categories), _json(categories), "Manipal", now))
    con.execute("""INSERT INTO gig_workers(id,name,age,phone,address,languages_json,skills_json,categories_json,location,
      identity_demo_verified,admin_approved,training_completed,active,available,created_at)
      VALUES(?,?,?,?,?,?,?,?,?,0,0,0,1,0,?)""",
      ("demo_worker_review", "Kavya Menon (Review Demo)", 27, "+91 00000 00002", "Synthetic demo address, Udupi",
       _json(["Kannada", "English"]), _json(["Companionship"]), _json(["Companionship"]), "Udupi", now))


def _worker(row):
    if not row:
        return None
    return {"id": row["id"], "name": row["name"], "age": row["age"], "phone": row["phone"],
            "address": row["address"], "languages": json.loads(row["languages_json"]),
            "skills": json.loads(row["skills_json"]), "categories": json.loads(row["categories_json"]),
            "location": row["location"], "identity_demo_verified": bool(row["identity_demo_verified"]),
            "identity_label": DEMO_IDENTITY_LABEL, "admin_approved": bool(row["admin_approved"]),
            "training_completed": bool(row["training_completed"]), "active": bool(row["active"]),
            "available": bool(row["available"]), "created_at": row["created_at"]}


def _reasons(worker, skills=None):
    reasons = []
    if not worker["identity_demo_verified"]:
        reasons.append("Synthetic demo identity verification is incomplete.")
    if not worker["admin_approved"]:
        reasons.append("Organisation approval is pending.")
    if not worker["training_completed"]:
        reasons.append("Training completion has not been recorded by the organisation.")
    if not worker["active"]:
        reasons.append("This helper account is inactive.")
    if not worker["available"]:
        reasons.append("Turn availability on before accepting a gig.")
    missing = [skill for skill in (skills or []) if skill.casefold() not in {x.casefold() for x in worker["skills"]}]
    if missing:
        reasons.append("Missing required skills: " + ", ".join(missing) + ".")
    return reasons


def _notify(con, audience, event_type, title, message, gig_id=None, worker_id=None):
    con.execute("INSERT INTO helper_gig_notifications VALUES(?,?,?,?,?,?,?,?,?)",
                (_id("notice"), audience, worker_id, event_type, title, message, gig_id, None, _now()))


def _status_history(con, gig_id):
    return [dict(row) for row in con.execute(
        "SELECT status,created_at FROM helper_gig_history WHERE gig_id=? ORDER BY created_at,id", (gig_id,)).fetchall()]


def _task(con, row, private=True):
    result = dict(row)
    result["required_skills"] = json.loads(result.pop("required_skills_json"))
    worker = con.execute("SELECT name FROM gig_workers WHERE id=?", (result.get("worker_id"),)).fetchone() if result.get("worker_id") else None
    result["worker_name"] = worker["name"] if worker else None
    result["status_history"] = _status_history(con, result["id"])
    result["is_alert_linked"] = bool(result.get("related_alert_id"))
    if not private:
        for key in ("client_name", "client_contact", "client_address", "instructions"):
            result.pop(key, None)
    return result


def _analytics(con):
    def count(sql):
        return con.execute(sql).fetchone()[0] or 0
    workers = count("SELECT COUNT(*) FROM gig_workers")
    approved = count("SELECT COUNT(*) FROM gig_workers WHERE identity_demo_verified=1 AND admin_approved=1 AND active=1")
    trained = count("SELECT COUNT(*) FROM gig_workers WHERE training_completed=1")
    open_gigs = count("SELECT COUNT(*) FROM helper_gigs WHERE status='open'")
    active_gigs = count("SELECT COUNT(*) FROM helper_gigs WHERE status IN ('accepted','on_the_way','reached','helping')")
    completed = count("SELECT COUNT(*) FROM helper_gigs WHERE status='done'")
    cancelled = count("SELECT COUNT(*) FROM helper_gigs WHERE status='cancelled'")
    linked_total = count("SELECT COUNT(*) FROM helper_gigs WHERE related_alert_id!=''")
    linked_done = count("SELECT COUNT(*) FROM helper_gigs WHERE related_alert_id!='' AND status='done'")
    earnings = con.execute("SELECT COALESCE(SUM(amount_inr),0) FROM helper_gig_earnings").fetchone()[0]
    avg = con.execute("SELECT AVG((julianday(accepted_at)-julianday(created_at))*86400) FROM helper_gigs WHERE accepted_at IS NOT NULL").fetchone()[0]
    return {"total_helpers": workers, "approved_helpers": approved, "training_completed": trained,
            "available_gigs": open_gigs, "active_gigs": active_gigs, "completed_gigs": completed,
            "cancelled_gigs": cancelled, "average_acceptance_seconds": round(avg, 1) if avg is not None else None,
            "completed_gig_earnings_inr": earnings, "alert_linked_gigs": linked_total,
            "alert_linked_completed": linked_done}


def state(db_file, role="admin", worker_id="demo_worker_priya"):
    initialize(db_file)
    con = _connect(db_file)
    workers = [_worker(row) for row in con.execute("SELECT * FROM gig_workers ORDER BY created_at,id").fetchall()]
    selected = next((w for w in workers if w["id"] == worker_id), None)
    if selected is None and workers:
        selected = workers[0]
    role = "worker" if role == "worker" else "admin"
    worker_tasks = []
    available_tasks = []
    for row in con.execute("SELECT * FROM helper_gigs ORDER BY created_at DESC").fetchall():
        task = _task(con, row, private=(role == "admin" or row["worker_id"] == (selected or {}).get("id")))
        if role == "admin":
            worker_tasks.append(task)
        elif selected and row["worker_id"] == selected["id"]:
            worker_tasks.append(task)
        elif selected and row["status"] == "open":
            passed = con.execute("SELECT 1 FROM helper_gig_decisions WHERE gig_id=? AND worker_id=? AND decision='passed'", (row["id"], selected["id"])).fetchone()
            skill_list = json.loads(row["required_skills_json"])
            if not passed and not [x for x in skill_list if x.casefold() not in {s.casefold() for s in selected["skills"]}]:
                available_tasks.append(_task(con, row, private=False))
    audience = "admin" if role == "admin" else "worker"
    notice_rows = con.execute("SELECT * FROM helper_gig_notifications WHERE audience=? AND (worker_id IS NULL OR worker_id=?) ORDER BY created_at DESC LIMIT 50",
                              (audience, (selected or {}).get("id"))).fetchall()
    notices = [dict(row) for row in notice_rows]
    result = {"role": role, "demo_only": True, "identity_notice": DEMO_IDENTITY_LABEL,
              "locations": LOCATIONS, "categories": CATEGORIES, "workers": workers if role == "admin" else [{"id": w["id"], "name": w["name"], "location": w["location"]} for w in workers],
              "worker": selected if role == "worker" else None, "eligibility_reasons": _reasons(selected) if role == "worker" and selected else [],
              "can_accept": bool(selected and not _reasons(selected)) if role == "worker" else False,
              "tasks": worker_tasks, "available_tasks": available_tasks, "notifications": notices,
              "analytics": _analytics(con) if role == "admin" else None}
    earnings = con.execute("SELECT COALESCE(SUM(amount_inr),0) AS total,COUNT(*) AS gigs FROM helper_gig_earnings WHERE worker_id=?", ((selected or {}).get("id"),)).fetchone()
    result["earnings"] = {"total_inr": earnings["total"], "completed_gigs": earnings["gigs"],
                           "items": [dict(r) for r in con.execute("SELECT e.amount_inr,e.created_at,g.title,g.category,g.id AS gig_id FROM helper_gig_earnings e JOIN helper_gigs g ON g.id=e.gig_id WHERE e.worker_id=? ORDER BY e.created_at DESC", ((selected or {}).get("id"),)).fetchall()]}
    con.close()
    return result


def _alert_context(alert_id, alerts):
    if not alert_id:
        return None
    alert = next((a for a in alerts if str(a.get("incident_id", "")) == alert_id), None)
    if not alert:
        return None
    return {"alert_id": alert_id, "patient_id": alert.get("person_id", ""),
            "patient_name": alert.get("client_name") or alert.get("name") or alert.get("person_id", "Demo client"),
            "summary": alert.get("summary", "Reviewed Sahaya alert"),
            "reason": alert.get("reason_text", ""), "priority": "high" if alert.get("display_tier") == "Red" else "standard"}


def _text(payload, key, required=True, maximum=500):
    value = str(payload.get(key, "")).strip()
    if required and not value:
        raise ValueError(f"{key.replace('_', ' ').capitalize()} is required.")
    if len(value) > maximum:
        raise ValueError(f"{key.replace('_', ' ').capitalize()} is too long.")
    return value


def _handle(db_file, method, path, payload, query, alerts):
    initialize(db_file)
    if method == "GET" and path == "/api/gigs/state":
        return 200, state(db_file, query.get("role", ["admin"])[0], query.get("worker_id", ["demo_worker_priya"])[0])
    if method == "GET" and path == "/api/gigs/alert-context":
        context = _alert_context(query.get("id", [""])[0], alerts)
        return (200, context) if context else (404, {"error": "This Sahaya alert is no longer open. Refresh the dashboard."})
    if method == "GET" and path == "/api/gigs/health":
        return 200, {"ok": True, "storage": "shared Sahaya SQLite", "demo_only": True}

    parts = path.strip("/").split("/")
    if method == "POST" and path == "/api/gigs/reset":
        con = _connect(db_file)
        con.execute("BEGIN IMMEDIATE")
        for table in ("helper_gig_earnings", "helper_gig_notifications", "helper_gig_history", "helper_gig_decisions", "helper_gigs", "gig_workers"):
            con.execute(f"DELETE FROM {table}")
        _seed_workers(con)
        con.commit(); con.close()
        return 200, state(db_file, "admin")

    if method == "POST" and path == "/api/gigs/workers":
        try:
            name = _text(payload, "name", maximum=100)
            age = int(payload.get("age", 0))
            if not 18 <= age <= 100: raise ValueError("Helpers must be between 18 and 100 years old.")
            location = _text(payload, "location", maximum=80)
            if location not in LOCATIONS: raise ValueError("Choose a service location in Udupi district.")
            languages = payload.get("languages", [])
            skills = payload.get("skills", [])
            categories = payload.get("categories", skills)
            if not isinstance(languages, list) or not languages or not isinstance(skills, list) or not skills:
                raise ValueError("Choose at least one language and one skill.")
            if any(s not in CATEGORIES for s in skills + categories): raise ValueError("Choose supported gig categories only.")
            worker_id = _id("worker")
            con = _connect(db_file); now = _now()
            con.execute("INSERT INTO gig_workers VALUES(?,?,?,?,?,?,?,?,?,0,0,0,1,0,?)",
                        (worker_id, name, age, _text(payload, "phone", maximum=30), _text(payload, "address", maximum=300), _json(languages), _json(skills), _json(categories), location, now))
            _notify(con, "admin", "helper_registered", "New helper registration", f"{name} registered for the local demo.")
            con.commit(); con.close()
            return 201, {"worker": next(w for w in state(db_file, "admin")["workers"] if w["id"] == worker_id), "eligibility_reasons": ["Synthetic demo identity verification is incomplete.", "Organisation approval is pending.", "Training completion has not been recorded by the organisation."]}
        except (ValueError, TypeError) as e:
            return 422, {"error": str(e)}

    if len(parts) >= 4 and parts[:3] == ["api", "gigs", "workers"] and method == "PATCH":
        worker_id = parts[3]
        updates = {"identity_demo_verified": payload.get("identity_demo_verified"), "admin_approved": payload.get("admin_approved"),
                   "training_completed": payload.get("training_completed"), "active": payload.get("active")}
        submitted = [(key, value) for key, value in updates.items() if value is not None]
        if any(type(value) is not bool for _, value in submitted):
            return 422, {"error": "Organisation status values must be true or false."}
        fields = [(key, int(value)) for key, value in submitted]
        if not fields: return 422, {"error": "Choose an organisation-controlled status to update."}
        con = _connect(db_file); con.execute("BEGIN IMMEDIATE")
        row = con.execute("SELECT name FROM gig_workers WHERE id=?", (worker_id,)).fetchone()
        if not row:
            con.rollback(); con.close(); return 404, {"error": "Helper not found."}
        con.execute("UPDATE gig_workers SET " + ",".join(f"{k}=?" for k, _ in fields) + " WHERE id=?", [v for _, v in fields] + [worker_id])
        _notify(con, "admin", "helper_reviewed", "Helper status updated", f"Organisation updated demo status for {row['name']}.")
        con.commit(); con.close()
        return 200, next(w for w in state(db_file, "admin")["workers"] if w["id"] == worker_id)

    if len(parts) == 5 and parts[:3] == ["api", "gigs", "workers"] and parts[4] == "availability" and method == "POST":
        worker_id = parts[3]
        if not isinstance(payload.get("available"), bool): return 422, {"error": "Availability must be true or false."}
        con = _connect(db_file); cur = con.execute("UPDATE gig_workers SET available=? WHERE id=?", (int(payload["available"]), worker_id))
        con.commit(); con.close()
        if not cur.rowcount: return 404, {"error": "Helper not found."}
        return 200, {"worker": next(w for w in state(db_file, "admin")["workers"] if w["id"] == worker_id)}

    if method == "POST" and path == "/api/gigs/tasks":
        try:
            title = _text(payload, "title", maximum=120)
            category = _text(payload, "category", maximum=80)
            if category not in CATEGORIES: raise ValueError("Choose a supported service category.")
            location = _text(payload, "location", maximum=80)
            if location not in LOCATIONS: raise ValueError("Choose a service location in Udupi district.")
            required = payload.get("required_skills") or [category]
            if not isinstance(required, list) or not required or any(s not in CATEGORIES for s in required): raise ValueError("Choose supported required skills.")
            duration = int(payload.get("duration_hours", 1))
            payout = int(payload.get("payout_inr", 0))
            if not 1 <= duration <= 12: raise ValueError("Duration must be between 1 and 12 hours.")
            if not 0 <= payout <= 100000: raise ValueError("Payout must be between ₹0 and ₹100,000.")
            scheduled_date = _text(payload, "scheduled_date", maximum=10)
            scheduled_time = _text(payload, "scheduled_time", maximum=10)
            try:
                parsed_date = datetime.strptime(scheduled_date, "%Y-%m-%d").date()
                datetime.strptime(scheduled_time, "%H:%M")
            except ValueError:
                raise ValueError("Enter a valid scheduled date and time.")
            if parsed_date < datetime.now().date(): raise ValueError("Choose today or a future date for the gig.")
            priority = payload.get("priority", "standard")
            if priority not in ("standard", "high", "urgent"): raise ValueError("Choose a supported priority.")
            alert_id = str(payload.get("related_alert_id", ""))
            context = _alert_context(alert_id, alerts) if alert_id else None
            if alert_id and not context: raise ValueError("The linked Sahaya alert is no longer open.")
            patient_id = context["patient_id"] if context else str(payload.get("related_patient_id", ""))
            worker_id = payload.get("worker_id") or None
            status = "draft"
            if payload.get("publish") is True:
                status = "open"
            created = _now(); gig_id = _id("gig")
            con = _connect(db_file); con.execute("BEGIN IMMEDIATE")
            if worker_id:
                worker = con.execute("SELECT * FROM gig_workers WHERE id=?", (worker_id,)).fetchone()
                if not worker: raise ValueError("Selected helper does not exist.")
                reasons = _reasons(_worker(worker), required)
                if reasons: raise ValueError("Selected helper is not eligible: " + " ".join(reasons))
            con.execute("""INSERT INTO helper_gigs(id,title,category,description,instructions,client_name,client_contact,
              client_address,location,scheduled_date,scheduled_time,duration_hours,payout_inr,required_skills_json,priority,
              related_patient_id,related_alert_id,status,worker_id,created_at,published_at)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
              (gig_id,title,category,_text(payload,"description",maximum=1000),_text(payload,"instructions",required=False,maximum=1500),
               _text(payload,"client_name",maximum=100),_text(payload,"client_contact",maximum=40),_text(payload,"client_address",maximum=400),
               location,scheduled_date,scheduled_time,duration,payout,_json(required),priority,
               patient_id,alert_id,status,worker_id,created,created if status=="open" else None))
            if worker_id and status == "open":
                _notify(con,"worker","gig_offer","New gig offer",f"{title} is available in {location}.",gig_id,worker_id)
            if status == "open":
                _notify(con,"admin","gig_published","Gig published",f"{title} was published to eligible helpers.",gig_id)
            con.commit(); row=con.execute("SELECT * FROM helper_gigs WHERE id=?",(gig_id,)).fetchone(); result=_task(con,row); con.close()
            return 201, result
        except (ValueError, TypeError, sqlite3.IntegrityError) as e:
            try: con.rollback(); con.close()
            except (UnboundLocalError, sqlite3.Error): pass
            return 422, {"error": str(e)}

    if len(parts) == 5 and parts[:3] == ["api", "gigs", "tasks"] and method == "POST":
        gig_id, action = parts[3], parts[4]
        worker_id = str(payload.get("worker_id", ""))
        con = _connect(db_file); con.execute("BEGIN IMMEDIATE")
        task = con.execute("SELECT * FROM helper_gigs WHERE id=?", (gig_id,)).fetchone()
        worker_row = con.execute("SELECT * FROM gig_workers WHERE id=?", (worker_id,)).fetchone()
        if not task or not worker_row:
            con.rollback(); con.close(); return 404, {"error": "Gig or helper not found."}
        worker = _worker(worker_row)
        if action == "pass":
            if task["status"] != "open":
                con.rollback(); con.close(); return 409, {"error": "This gig is no longer open."}
            con.execute("INSERT OR REPLACE INTO helper_gig_decisions VALUES(?,?,?,?)",(gig_id,worker_id,"passed",_now()))
            con.commit(); con.close(); return 200, {"passed": True, "gig_id": gig_id}
        if action == "accept":
            reasons = _reasons(worker, json.loads(task["required_skills_json"]))
            if reasons:
                con.rollback(); con.close(); return 403, {"error": "Helper is not eligible to accept this gig.", "reasons": reasons}
            updated = con.execute("UPDATE helper_gigs SET status='accepted',worker_id=?,accepted_at=?,related_patient_id=related_patient_id WHERE id=? AND status='open' AND worker_id IS NULL",
                                  (worker_id,_now(),gig_id))
            if updated.rowcount != 1:
                con.rollback(); con.close(); return 409, {"error": "Another helper already accepted this gig."}
            now = _now(); con.execute("INSERT INTO helper_gig_decisions VALUES(?,?,?,?)",(gig_id,worker_id,"accepted",now))
            con.execute("INSERT INTO helper_gig_history VALUES(?,?,?,?,?)",(_id("event"),gig_id,worker_id,"accepted",now))
            _notify(con,"admin","gig_accepted","Gig accepted",f"{worker['name']} accepted {task['title']}.",gig_id)
            con.commit(); result=_task(con,con.execute("SELECT * FROM helper_gigs WHERE id=?",(gig_id,)).fetchone()); con.close()
            return 200,result
        if action == "status":
            if task["worker_id"] != worker_id:
                con.rollback(); con.close(); return 403, {"error": "Only the assigned helper can update this task."}
            next_status = str(payload.get("status", ""))
            if FLOW.get(task["status"]) != next_status:
                con.rollback(); con.close(); return 409, {"error": f"Invalid task transition from {task['status']} to {next_status}."}
            now=_now()
            con.execute("UPDATE helper_gigs SET status=?,completed_at=? WHERE id=? AND status=?",(next_status,now if next_status=="done" else None,gig_id,task["status"]))
            con.execute("INSERT INTO helper_gig_history VALUES(?,?,?,?,?)",(_id("event"),gig_id,worker_id,next_status,now))
            _notify(con,"admin","gig_progress","Helper task update",f"{worker['name']}: {task['title']} is now {next_status.replace('_',' ')}.",gig_id)
            if next_status == "done":
                con.execute("INSERT OR IGNORE INTO helper_gig_earnings VALUES(?,?,?,?,?)",(_id("earning"),gig_id,worker_id,task["payout_inr"],now))
                _notify(con,"admin","gig_completed","Helper task completed",f"{worker['name']} completed {task['title']}.",gig_id)
                _notify(con,"worker","earnings_recorded","Earnings recorded",f"₹{task['payout_inr']} recorded for {task['title']}.",gig_id,worker_id)
            con.commit(); result=_task(con,con.execute("SELECT * FROM helper_gigs WHERE id=?",(gig_id,)).fetchone()); con.close()
            return 200,result
        con.rollback(); con.close(); return 404,{"error":"Unknown gig action."}

    if len(parts) == 5 and parts[:3] == ["api", "gigs", "notifications"] and parts[4] == "read" and method == "POST":
        con = _connect(db_file); cur=con.execute("UPDATE helper_gig_notifications SET read_at=? WHERE id=?",(_now(),parts[3])); con.close()
        return (200,{"read":True}) if cur.rowcount else (404,{"error":"Notification not found."})
    return 404, {"error": "Gig API route not found."}


def dispatch(db_file, method, path, body=None, query_string="", alerts=None):
    """Return (HTTP status, JSON body) for local gig endpoints."""
    try:
        query = parse_qs(query_string)
        return _handle(db_file, method, path, body or {}, query, alerts or [])
    except (OSError, sqlite3.Error) as e:
        return 500, {"error": "Local gig data could not be saved.", "detail": str(e)}
