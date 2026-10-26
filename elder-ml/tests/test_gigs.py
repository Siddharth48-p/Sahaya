from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from src import gigs


def payload(**overrides):
    value = {
        "title": "Hospital visit support", "category": "Hospital accompaniment",
        "description": "Accompany a demo client to a scheduled appointment.",
        "instructions": "Meet at the entrance and assist with check-in.",
        "client_name": "Demo client", "client_contact": "+91 00000 00000",
        "client_address": "Synthetic address, Manipal, Udupi", "location": "Manipal",
        "scheduled_date": "2026-11-02", "scheduled_time": "10:00",
        "duration_hours": 2, "payout_inr": 500,
        "required_skills": ["Hospital accompaniment"], "priority": "standard", "publish": True,
    }
    value.update(overrides)
    return value


def call(db, method, path, body=None, alerts=None):
    return gigs.dispatch(db, method, path, body or {}, alerts=alerts or [])


def make_eligible(db, worker_id):
    for field in ("identity_demo_verified", "admin_approved", "training_completed", "active"):
        code, _ = call(db, "PATCH", f"/api/gigs/workers/{worker_id}", {field: True})
        assert code == 200
    code, _ = call(db, "POST", f"/api/gigs/workers/{worker_id}/availability", {"available": True})
    assert code == 200


def register(db, name="Test helper"):
    code, result = call(db, "POST", "/api/gigs/workers", {
        "name": name, "age": 28, "phone": "+91 00000 00003", "address": "Synthetic address in Udupi",
        "location": "Udupi", "languages": ["Kannada"],
        "skills": ["Hospital accompaniment", "Companionship"],
    })
    assert code == 201
    return result["worker"]["id"]


def test_worker_registration_review_and_server_side_acceptance_block(tmp_path):
    db = tmp_path / "sahaya.sqlite"
    gigs.initialize(db)
    worker_id = register(db)
    gig_code, gig = call(db, "POST", "/api/gigs/tasks", payload())
    assert gig_code == 201
    code, result = call(db, "POST", f"/api/gigs/tasks/{gig['id']}/accept", {"worker_id": worker_id})
    assert code == 403
    assert len(result["reasons"]) >= 3
    make_eligible(db, worker_id)
    code, _ = call(db, "POST", f"/api/gigs/tasks/{gig['id']}/accept", {"worker_id": worker_id})
    assert code == 200


def test_alert_linked_published_gig_is_sanitized_in_worker_queue(tmp_path):
    db = tmp_path / "alert.sqlite"
    gigs.initialize(db)
    alerts = [{"incident_id": "E1-alert-1", "person_id": "E1", "client_name": "Synthetic elder",
               "summary": "Rule-based demo change", "reason_text": "Synthetic input", "display_tier": "Red"}]
    code, task = call(db, "POST", "/api/gigs/tasks", payload(related_alert_id="E1-alert-1"), alerts)
    assert code == 201 and task["related_patient_id"] == "E1" and task["status"] == "open"
    state = gigs.state(db, "worker", "demo_worker_priya")
    offer = next(item for item in state["available_tasks"] if item["id"] == task["id"])
    assert offer["is_alert_linked"] and "client_name" not in offer and "client_contact" not in offer and "client_address" not in offer
    code, error = call(db, "POST", "/api/gigs/tasks", payload(related_alert_id="unknown"), alerts)
    assert code == 422 and "alert" in error["error"].lower()


def test_pass_accept_progress_notifications_earnings_and_persistence(tmp_path):
    db = tmp_path / "workflow.sqlite"
    gigs.initialize(db)
    code, task = call(db, "POST", "/api/gigs/tasks", payload())
    assert code == 201
    code, _ = call(db, "POST", f"/api/gigs/tasks/{task['id']}/pass", {"worker_id": "demo_worker_priya"})
    assert code == 200
    assert all(t["id"] != task["id"] for t in gigs.state(db, "worker", "demo_worker_priya")["available_tasks"])
    worker_id = register(db)
    make_eligible(db, worker_id)
    code, accepted = call(db, "POST", f"/api/gigs/tasks/{task['id']}/accept", {"worker_id": worker_id})
    assert code == 200 and accepted["client_contact"] == "+91 00000 00000"
    code, error = call(db, "POST", f"/api/gigs/tasks/{task['id']}/status", {"worker_id": worker_id, "status": "helping"})
    assert code == 409
    for status in ("on_the_way", "reached", "helping", "done"):
        code, result = call(db, "POST", f"/api/gigs/tasks/{task['id']}/status", {"worker_id": worker_id, "status": status})
        assert code == 200 and result["status"] == status
    worker_state = gigs.state(db, "worker", worker_id)
    assert worker_state["earnings"]["total_inr"] == 500 and worker_state["earnings"]["completed_gigs"] == 1
    admin_state = gigs.state(db, "admin")
    assert admin_state["analytics"]["completed_gigs"] == 1
    assert admin_state["analytics"]["alert_linked_completed"] == 0
    assert any(n["event_type"] == "gig_completed" for n in admin_state["notifications"])
    gigs.initialize(db)
    restored = gigs.state(db, "admin")
    assert next(t for t in restored["tasks"] if t["id"] == task["id"])["status"] == "done"
    assert restored["analytics"]["completed_gig_earnings_inr"] == 500


def test_concurrent_acceptance_assigns_only_once(tmp_path):
    db = tmp_path / "concurrent.sqlite"
    gigs.initialize(db)
    code, task = call(db, "POST", "/api/gigs/tasks", payload())
    assert code == 201
    second = register(db, "Second helper")
    make_eligible(db, second)
    workers = ["demo_worker_priya", second]
    def accept(worker_id):
        return call(db, "POST", f"/api/gigs/tasks/{task['id']}/accept", {"worker_id": worker_id})[0]
    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = list(pool.map(accept, workers))
    assert sorted(codes) == [200, 409]
    assert gigs.state(db, "admin")["analytics"]["active_gigs"] == 1


def test_responsive_assets_and_demo_identity_wording():
    root = Path(__file__).resolve().parents[1]
    css = (root / "web" / "gigs.css").read_text(encoding="utf-8")
    html = (root / "web" / "gigs.html").read_text(encoding="utf-8")
    assert "@media(max-width:720px)" in css
    assert "Demo identity status is synthetic" in html
    assert "role switch is not security" in html.lower()
