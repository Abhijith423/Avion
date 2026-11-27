import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List
import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:3b"


def score_live_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    gbif = entry.get("gbif_live", {})
    inat = entry.get("inaturalist_live", {})
    meteo = entry.get("open_meteo_live", {})
    ebird = entry.get("ebird_live", {})

    occ_2025 = int(gbif.get("occurrences_2025", 0) or 0)
    occ_2026 = int(gbif.get("occurrences_2026", 0) or 0)
    inat_250km = int(inat.get("total_results_within_250km", 0) or 0)
    ebird_14d = int(ebird.get("recent_checklist_obs_50km_14d", 0) or 0)

    current_weather = meteo.get("current_weather") or {}
    current_marine = meteo.get("current_marine") or {}

    temp_c = float(current_weather.get("temperature_2m", 15.0) or 15.0)
    wind_speed = float(current_weather.get("wind_speed_10m", 0.0) or 0.0)
    sst_c = current_marine.get("sea_surface_temperature")
    wave_h = current_marine.get("wave_height")

    if occ_2025 > 0:
        expected_prorated_2026 = occ_2025 * 0.90
        shortfall_ratio = max(0.0, min(1.0, (expected_prorated_2026 - occ_2026) / expected_prorated_2026))
    else:
        shortfall_ratio = 0.5

    obs_activity_signal = round(shortfall_ratio * 0.35, 3)

    env_stress = 0.12
    env_reasons: List[str] = [f"temp {temp_c}C", f"wind {wind_speed}"]
    if sst_c is not None and float(sst_c) > 13.5:
        env_stress += 0.14
        env_reasons.append(f"SST {sst_c}C")
    if wave_h is not None and float(wave_h) > 1.5:
        env_stress += 0.10
        env_reasons.append(f"wave {wave_h}m")
    if temp_c > 25.0 or temp_c < -2.0:
        env_stress += 0.10
    env_stress = round(min(0.40, env_stress), 3)

    local_density_gap = round(0.24 if ebird_14d < 100 else 0.12, 3)
    community_signal = round(0.18 if inat_250km < 500 else 0.08, 3)

    risk_score = round(
        min(0.99, max(0.05, obs_activity_signal + env_stress + local_density_gap + community_signal)),
        2,
    )
    cohort = "HIGH-RISK" if risk_score >= 0.60 else ("MID-RISK" if risk_score >= 0.30 else "STABLE")

    drivers = [
        {
            "factor": "Environmental & Marine Stress",
            "impact": env_stress,
            "detail": ", ".join(env_reasons),
        },
        {
            "factor": "2026 vs 2025 Occurrence Pace",
            "impact": obs_activity_signal,
            "detail": f"2026: {occ_2026} vs 2025: {occ_2025}",
        },
        {
            "factor": "Recent Local Checklist Coverage (14d / 50km)",
            "impact": local_density_gap,
            "detail": f"eBird 14d obs: {ebird_14d}, iNat 250km: {inat_250km}",
        },
        {
            "factor": "Regional Community Observation Density",
            "impact": community_signal,
            "detail": f"iNaturalist 250km total: {inat_250km}",
        },
    ]
    drivers.sort(key=lambda d: d["impact"], reverse=True)
    top_3 = drivers[:3]

    return {
        "scored_at_utc": datetime.now(timezone.utc).isoformat(),
        "common_name": entry["common_name"],
        "scientific_name": entry["scientific_name"],
        "risk_score": risk_score,
        "cohort": cohort,
        "top_3_drivers": top_3,
        "live_summary": {
            "gbif_2025": occ_2025,
            "gbif_2026": occ_2026,
            "inat_250km": inat_250km,
            "ebird_14d_50km": ebird_14d,
            "temp_c": temp_c,
            "wind_speed_10m": wind_speed,
            "sea_surface_temperature": sst_c,
            "wave_height": wave_h,
        },
    }


def generate_ollama_intervention(scored: Dict[str, Any]) -> str:
    prompt = (
        f"Species: {scored['common_name']} ({scored['scientific_name']})\n"
        f"Risk Score: {scored['risk_score']} | Cohort: {scored['cohort']}\n"
        f"Top-3 Drivers: {json.dumps(scored['top_3_drivers'])}\n"
        f"Live Signals: {json.dumps(scored['live_summary'])}\n"
        "Write a concise 2-sentence conservation triage note with an immediate action window and field check."
    )
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=35,
        )
        resp.raise_for_status()
        text = (resp.json().get("response") or "").strip()
        if text:
            return text
    except requests.RequestException:
        pass

    top_factor = scored["top_3_drivers"][0]["factor"]
    return (
        f"[{scored['cohort']} | Score {scored['risk_score']}] Primary live driver is {top_factor}. "
        f"Schedule immediate field/colony verification during peak activity window using live GBIF/eBird/weather readings."
    )


def save_to_sqlite(items: List[Dict[str, Any]]) -> None:
    conn = sqlite3.connect("avian_nova.db")
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS live_risk_assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scored_at_utc TEXT,
            common_name TEXT,
            scientific_name TEXT,
            risk_score REAL,
            cohort TEXT,
            top_3_json TEXT,
            live_summary_json TEXT,
            intervention_note TEXT
        )
        """
    )
    for it in items:
        cur.execute(
            """
            INSERT INTO live_risk_assessments (
                scored_at_utc, common_name, scientific_name, risk_score, cohort,
                top_3_json, live_summary_json, intervention_note
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                it["scored_at_utc"],
                it["common_name"],
                it["scientific_name"],
                it["risk_score"],
                it["cohort"],
                json.dumps(it["top_3_drivers"]),
                json.dumps(it["live_summary"]),
                it["intervention_note"],
            ),
        )
    conn.commit()
    conn.close()


def main() -> None:
    with open("day3_live_api_output.json", "r", encoding="utf-8") as f:
        raw_entries = json.load(f)

    results: List[Dict[str, Any]] = []
    for entry in raw_entries:
        scored = score_live_entry(entry)
        scored["intervention_note"] = generate_ollama_intervention(scored)
        results.append(scored)

        print(f"\n=== {scored['common_name']} ({scored['scientific_name']}) ===")
        print(f"Risk Score: {scored['risk_score']} | Cohort: {scored['cohort']}")
        for idx, d in enumerate(scored["top_3_drivers"], start=1):
            print(f"  Top-{idx} [+{d['impact']}]: {d['factor']} ({d['detail']})")
        print(f"Triage Note: {scored['intervention_note']}")

    with open("day4_scored_interventions.json", "w", encoding="utf-8") as out:
        json.dump(results, out, indent=2)

    save_to_sqlite(results)
    print("\nSaved day4_scored_interventions.json and updated avian_nova.db")


if __name__ == "__main__":
    main()