from src import dashboard


def test_demo_input_rules_are_explicitly_rule_based(monkeypatch):
    monkeypatch.setattr(dashboard, "_baseline", lambda person, field, limit=180: {"hr": 72, "spo2": 96, "sbp": 125}.get(field))
    assert dashboard._classify_demo_input("E1", {"hr": 101})[0] == "Yellow"
    assert dashboard._classify_demo_input("E1", {"spo2": 87})[0] == "Red"
    assert dashboard._classify_demo_input("E1", {"spo2": 96}) is None


def test_submitted_demo_input_is_persisted_and_creates_reviewable_alert(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard, "DB_FILE", tmp_path / "dashboard.sqlite")
    monkeypatch.setattr(dashboard, "_baseline", lambda person, field, limit=180: 96 if field == "spo2" else 72)
    old_active = dashboard.STATE["active"]
    old_triggered = dashboard.STATE["triggered"]
    old_paused = dashboard.STATE["paused"]
    dashboard.STATE["active"] = {}
    dashboard.STATE["triggered"] = set()
    dashboard.STATE["paused"] = False
    try:
        indicator = dashboard._record_reading("E1", {"spo2": 87}, simulated=True)
        con = dashboard._db()
        reading = con.execute("SELECT person_id,values_json,simulated FROM demo_readings").fetchone()
        incident = con.execute("SELECT tier,source_label FROM demo_incidents").fetchone()
        con.close()
        assert indicator[0] == "Red"
        assert reading[0] == "E1" and '"spo2": 87' in reading[1] and reading[2] == 1
        assert incident == ("Red", "Rule-based demo input")
        assert len(dashboard.STATE["active"]) == 1
        assert dashboard.STATE["paused"] is True
    finally:
        dashboard.STATE["active"] = old_active
        dashboard.STATE["triggered"] = old_triggered
        dashboard.STATE["paused"] = old_paused
