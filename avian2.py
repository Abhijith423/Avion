import csv
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import requests

TIMEOUT = 20
HEADERS = {"User-Agent": "AvianNova-Day2/1.0 (local-dev)"}

SPECIES_10: List[Dict[str, Any]] = [
    {
        "species_id": "kiwi_brown_ni",
        "common_name": "North Island Brown Kiwi",
        "scientific_name": "Apteryx mantelli",
        "lat": -38.68,
        "lon": 176.07,
        "iucn_weight": 0.85,
        "predator_pressure": 0.92,
        "habitat_fragmentation": 0.80,
        "telemetry_anomaly": 0.78,
        "action_window": "Nightly (18:00-04:00)",
        "primary_action": "Dispatch stoat-trap checks, dog-roaming patrols, and chick-lift checks in high-risk bush pockets.",
    },
    {
        "species_id": "penguin_african",
        "common_name": "African Penguin",
        "scientific_name": "Spheniscus demersus",
        "lat": -33.01,
        "lon": 17.95,
        "iucn_weight": 0.95,
        "predator_pressure": 0.75,
        "habitat_fragmentation": 0.85,
        "telemetry_anomaly": 0.84,
        "action_window": "Dawn / Dusk Colony Window",
        "primary_action": "Flag extended foraging-trip tracks and coordinate colony prey/fishery-buffer alerts.",
    },
    {
        "species_id": "penguin_emperor",
        "common_name": "Emperor Penguin",
        "scientific_name": "Aptenodytes forsteri",
        "lat": -70.00,
        "lon": 24.00,
        "iucn_weight": 0.88,
        "predator_pressure": 0.55,
        "habitat_fragmentation": 0.90,
        "telemetry_anomaly": 0.76,
        "action_window": "Pre-Fledging Watch (Sep-Nov)",
        "primary_action": "Monitor Antarctic fast-ice stability and alert coastal stations ahead of chick fledging.",
    },
    {
        "species_id": "penguin_galapagos",
        "common_name": "Galapagos Penguin",
        "scientific_name": "Spheniscus mendiculus",
        "lat": -0.45,
        "lon": -91.05,
        "iucn_weight": 0.92,
        "predator_pressure": 0.78,
        "habitat_fragmentation": 0.82,
        "telemetry_anomaly": 0.81,
        "action_window": "Weekly Upwelling Watch",
        "primary_action": "Track sea-surface/thermal spikes and prepare supplemental feeding & colony checks.",
    },
    {
        "species_id": "kakapo",
        "common_name": "Kakapo",
        "scientific_name": "Strigops habroptilus",
        "lat": -45.60,
        "lon": 167.40,
        "iucn_weight": 0.96,
        "predator_pressure": 0.82,
        "habitat_fragmentation": 0.94,
        "telemetry_anomaly": 0.70,
        "action_window": "Nightly Nest & Transmitter Check",
        "primary_action": "Review individual transmitter inactivity/weight alerts and coordinate sanctuary biosecurity.",
    },
    {
        "species_id": "great_indian_bustard",
        "common_name": "Great Indian Bustard",
        "scientific_name": "Ardeotis nigriceps",
        "lat": 26.90,
        "lon": 70.90,
        "iucn_weight": 0.98,
        "predator_pressure": 0.74,
        "habitat_fragmentation": 0.93,
        "telemetry_anomaly": 0.86,
        "action_window": "Dawn / Dusk Flight Corridor Alert",
        "primary_action": "Flag GPS movement near overhead power lines and prioritize undergrounding/bird-flight diverters.",
    },
    {
        "species_id": "amur_leopard",
        "common_name": "Amur Leopard",
        "scientific_name": "Panthera pardus orientalis",
        "lat": 43.10,
        "lon": 131.50,
        "iucn_weight": 0.94,
        "predator_pressure": 0.88,
        "habitat_fragmentation": 0.86,
        "telemetry_anomaly": 0.72,
        "action_window": "Nightly Snare & Edge Patrol",
        "primary_action": "Escalate camera-trap and range-edge detections near snare corridors to anti-poaching patrols.",
    },
    {
        "species_id": "sumatran_orangutan",
        "common_name": "Sumatran Orangutan",
        "scientific_name": "Pongo abelii",
        "lat": 3.50,
        "lon": 97.60,
        "iucn_weight": 0.96,
        "predator_pressure": 0.76,
        "habitat_fragmentation": 0.92,
        "telemetry_anomaly": 0.79,
        "action_window": "Daytime Forest-Edge Alert",
        "primary_action": "Alert rapid-response and community mitigation teams when fringe movement/clearing rises.",
    },
    {
        "species_id": "eastern_gorilla",
        "common_name": "Eastern Gorilla",
        "scientific_name": "Gorilla beringei",
        "lat": -1.45,
        "lon": 29.55,
        "iucn_weight": 0.93,
        "predator_pressure": 0.80,
        "habitat_fragmentation": 0.88,
        "telemetry_anomaly": 0.74,
        "action_window": "Daily Territory & Health Check",
        "primary_action": "Dispatch ranger snare sweeps and veterinary checks when group movement or health signals shift.",
    },
    {
        "species_id": "philippine_eagle",
        "common_name": "Philippine Eagle",
        "scientific_name": "Pithecophaga jeeryi",
        "lat": 7.15,
        "lon": 125.30,
        "iucn_weight": 0.95,
        "predator_pressure": 0.84,
        "habitat_fragmentation": 0.91,
        "telemetry_anomaly": 0.77,
        "action_window": "Daytime Nest-Buffer Patrol",
        "primary_action": "Trigger forest-guard patrols around nesting territories on clearing or acoustic intrusion alerts.",
    },
]


def get_gbif_taxon_key(scientific_name: str) -> Optional[int]:
    try:
        resp = requests.get(
            "https://api.gbif.org/v1/species/match",
            params={"name": scientific_name},
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        key = resp.json().get("usageKey")
        return int(key) if key is not None else None
    except requests.RequestException:
        return None


def get_gbif_yearly_counts(taxon_key: Optional[int], years: List[int]) -> Dict[int, int]:
    if not taxon_key:
        return {yr: 0 for yr in years}
    counts: Dict[int, int] = {}
    for yr in years:
        try:
            resp = requests.get(
                "https://api.gbif.org/v1/occurrence/search",
                params={"taxonKey": taxon_key, "year": yr, "limit": 0},
                headers=HEADERS,
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            counts[yr] = int(resp.json().get("count", 0))
        except requests.RequestException:
            counts[yr] = 0
    return counts


def get_weather_metrics(lat: float, lon: float) -> Dict[str, float]:
    try:
        resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "daily": "temperature_2m_max,precipitation_sum",
                "past_days": 30,
                "forecast_days": 7,
                "timezone": "UTC",
            },
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        daily = resp.json().get("daily", {})
        temps = [t for t in daily.get("temperature_2m_max", []) if t is not None]
        rains = [r for r in daily.get("precipitation_sum", []) if r is not None]
        avg_temp = round(sum(temps) / len(temps), 2) if temps else 15.0
        total_rain = round(sum(rains), 2) if rains else 50.0
        return {"avg_max_temp_c": avg_temp, "total_rain_mm_37d": total_rain}
    except requests.RequestException:
        return {"avg_max_temp_c": 15.0, "total_rain_mm_37d": 50.0}


def score_species_row(sp: Dict[str, Any], counts: Dict[int, int], weather: Dict[str, float]) -> Dict[str, Any]:
    c_2022 = counts.get(2022, 0)
    c_2023 = counts.get(2023, 0)
    c_2024 = counts.get(2024, 0)
    c_2025 = counts.get(2025, 0)
    avg_3yr = (c_2022 + c_2023 + c_2024) / 3.0

    if avg_3yr > 0:
        trend_drop_pct = ((c_2025 - avg_3yr) / avg_3yr) * 100.0
    else:
        trend_drop_pct = -100.0 if c_2025 == 0 else 0.0

    predator_contrib = round(sp["predator_pressure"] * 0.30, 3)
    habitat_contrib = round(sp["habitat_fragmentation"] * 0.25, 3)
    telemetry_contrib = round(sp["telemetry_anomaly"] * 0.25, 3)

    if "penguin" in sp["species_id"] and weather["avg_max_temp_c"] > 10.0:
        weather_stress = 0.20
    elif weather["total_rain_mm_37d"] > 200.0:
        weather_stress = 0.16
    else:
        weather_stress = 0.10

    raw_score = (
        predator_contrib
        + habitat_contrib
        + telemetry_contrib
        + weather_stress
        + (sp["iucn_weight"] * 0.10)
    )
    risk_score = round(min(0.99, max(0.05, raw_score)), 2)

    if risk_score >= 0.60:
        cohort = "HIGH-RISK"
    elif risk_score >= 0.30:
        cohort = "MID-RISK"
    else:
        cohort = "STABLE"

    driver_candidates = [
        {"factor": "Predator / Threat Pressure", "impact": predator_contrib},
        {"factor": "Habitat Fragmentation & Loss", "impact": habitat_contrib},
        {"factor": "Bio-Telemetry / Movement Anomaly", "impact": telemetry_contrib},
        {"factor": "Environmental / Weather Stress", "impact": round(weather_stress, 3)},
    ]
    driver_candidates.sort(key=lambda x: x["impact"], reverse=True)
    top_3 = driver_candidates[:3]

    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "species_id": sp["species_id"],
        "common_name": sp["common_name"],
        "scientific_name": sp["scientific_name"],
        "risk_score": risk_score,
        "cohort": cohort,
        "gbif_2025": c_2025,
        "gbif_3yr_avg": round(avg_3yr, 1),
        "gbif_trend_pct": round(trend_drop_pct, 1),
        "avg_max_temp_c": weather["avg_max_temp_c"],
        "total_rain_mm_37d": weather["total_rain_mm_37d"],
        "predator_pressure": sp["predator_pressure"],
        "habitat_fragmentation": sp["habitat_fragmentation"],
        "telemetry_anomaly": sp["telemetry_anomaly"],
        "iucn_weight": sp["iucn_weight"],
        "driver_1": top_3[0]["factor"],
        "driver_2": top_3[1]["factor"],
        "driver_3": top_3[2]["factor"],
        "action_window": sp["action_window"],
        "primary_action": sp["primary_action"],
        "top_3_json": json.dumps(top_3),
    }


def save_outputs(rows: List[Dict[str, Any]]) -> None:
    csv_path = "avian_features.csv"
    fieldnames = [k for k in rows[0].keys() if k != "top_3_json"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: v for k, v in r.items() if k != "top_3_json"})

    conn = sqlite3.connect("avian_nova.db")
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS species_risk_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp_utc TEXT,
            species_id TEXT,
            common_name TEXT,
            scientific_name TEXT,
            risk_score REAL,
            cohort TEXT,
            gbif_2025 INTEGER,
            gbif_3yr_avg REAL,
            gbif_trend_pct REAL,
            avg_max_temp_c REAL,
            total_rain_mm_37d REAL,
            predator_pressure REAL,
            habitat_fragmentation REAL,
            telemetry_anomaly REAL,
            iucn_weight REAL,
            driver_1 TEXT,
            driver_2 TEXT,
            driver_3 TEXT,
            action_window TEXT,
            primary_action TEXT,
            top_3_json TEXT
        )
        """
    )
    for r in rows:
        cur.execute(
            """
            INSERT INTO species_risk_snapshots (
                timestamp_utc, species_id, common_name, scientific_name, risk_score, cohort,
                gbif_2025, gbif_3yr_avg, gbif_trend_pct, avg_max_temp_c, total_rain_mm_37d,
                predator_pressure, habitat_fragmentation, telemetry_anomaly, iucn_weight,
                driver_1, driver_2, driver_3, action_window, primary_action, top_3_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                r["timestamp_utc"], r["species_id"], r["common_name"], r["scientific_name"],
                r["risk_score"], r["cohort"], r["gbif_2025"], r["gbif_3yr_avg"],
                r["gbif_trend_pct"], r["avg_max_temp_c"], r["total_rain_mm_37d"],
                r["predator_pressure"], r["habitat_fragmentation"], r["telemetry_anomaly"],
                r["iucn_weight"], r["driver_1"], r["driver_2"], r["driver_3"],
                r["action_window"], r["primary_action"], r["top_3_json"],
            ),
        )
    conn.commit()
    conn.close()


def main() -> None:
    rows: List[Dict[str, Any]] = []
    for sp in SPECIES_10:
        taxon_key = get_gbif_taxon_key(sp["scientific_name"])
        counts = get_gbif_yearly_counts(taxon_key, [2022, 2023, 2024, 2025])
        weather = get_weather_metrics(sp["lat"], sp["lon"])
        row = score_species_row(sp, counts, weather)
        rows.append(row)
        print(f"{row['common_name']:24s} | Score: {row['risk_score']:.2f} | {row['cohort']:9s} | Top-1: {row['driver_1']}")

    save_outputs(rows)
    print("\nSaved 10-species dataset to avian_features.csv and SQLite table in avian_nova.db")


if __name__ == "__main__":
    main()