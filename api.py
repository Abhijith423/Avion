import json
import os
import sqlite3
from typing import Any, Dict, List
import requests
from fastapi import FastAPI, HTTPException

app = FastAPI(title="Avion Risk & Triage API", version="0.4.0")

DB_PATH = "avian_nova.db"
JSON_PATH = "day4_scored_interventions.json"
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "http://localhost:5678/webhook/avion-high-risk")


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"status": "ok", "service": "avion-api", "db_exists": os.path.exists(DB_PATH)}


@app.get("/assessments")
def get_assessments(cohort: str | None = None) -> List[Dict[str, Any]]:
    if os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        if cohort:
            rows = cur.execute(
                "SELECT * FROM live_risk_assessments WHERE cohort = ? ORDER BY id DESC",
                (cohort.upper(),),
            ).fetchall()
        else:
            rows = cur.execute("SELECT * FROM live_risk_assessments ORDER BY id DESC").fetchall()
        conn.close()

        results: List[Dict[str, Any]] = []
        for r in rows:
            item = dict(r)
            item["top_3_drivers"] = json.loads(item.pop("top_3_json") or "[]")
            item["live_summary"] = json.loads(item.pop("live_summary_json") or "{}")
            results.append(item)
        return results

    if os.path.exists(JSON_PATH):
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if cohort:
            return [d for d in data if d.get("cohort", "").upper() == cohort.upper()]
        return data

    return []


@app.post("/alerts/n8n")
def dispatch_high_risk_alerts(min_score: float = 0.60) -> Dict[str, Any]:
    assessments = get_assessments()
    high_risk = [a for a in assessments if float(a.get("risk_score", 0.0)) >= min_score]
    if not high_risk:
        return {"dispatched": 0, "message": "No assessments met threshold"}

    payload = {
        "source": "Avion",
        "min_score": min_score,
        "alert_count": len(high_risk),
        "alerts": high_risk,
    }
    try:
        resp = requests.post(N8N_WEBHOOK_URL, json=payload, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"n8n webhook request failed: {exc}") from exc

    return {
        "dispatched": len(high_risk),
        "webhook_url": N8N_WEBHOOK_URL,
        "n8n_status_code": resp.status_code,
    }