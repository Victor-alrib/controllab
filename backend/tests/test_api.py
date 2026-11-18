from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
CFG = {"plant": {"type": "second_order", "params": {"wn": 2, "zeta": 0.3}},
       "controller": {"type": "pid", "params": {"Kp": 2, "Ki": 1, "Kd": 0.3}},
       "settings": {"t_final": 10, "Ts": 0.01}}


def test_catalog():
    c = client.get("/api/catalog").json()
    types = {x["type"]: x["status"] for x in c["controllers"]}
    assert types["pid"] == "available" and types["lqr"] == "planned"
    assert {p["type"] for p in c["plants"]} >= {"first_order", "second_order"}


def test_simulate_analyze_csv_report():
    r = client.post("/api/simulate", json=CFG)
    assert r.status_code == 200
    body = r.json()
    assert len(body["signals"]["t"]) == len(body["signals"]["y"]) <= 6000 + 3
    assert body["metrics"]["IAE"] > 0
    a = client.post("/api/analyze", json=CFG).json()
    assert a["closed_loop"]["discrete_stable"]
    csv = client.post("/api/export/csv", json=CFG)
    assert csv.text.splitlines()[2] == "t,r,y,e,u,u_cmd,d_in,d_out"
    rep = client.post("/api/report", json={"runs": [{"label": "A", "config": CFG}]})
    assert rep.status_code == 200 and "data:image/png;base64" in rep.text


def test_unstable_run_is_json_safe():
    cfg = dict(CFG, controller={"type": "p", "params": {"Kp": 500}}, settings={"t_final": 200, "Ts": 0.5})
    r = client.post("/api/simulate", json=cfg)
    assert r.status_code == 200
    assert r.json()["metrics"]["stable_run"] is False


def test_validation_error_message():
    r = client.post("/api/simulate", json=dict(CFG, plant={"type": "first_order", "params": {"tau": -1}}))
    assert r.status_code == 422 and "τ" in r.json()["detail"]
