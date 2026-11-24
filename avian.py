import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import requests

TIMEOUT = 20
HEADERS = {"User-Agent": "AvianNova-Day1/1.0 (local-dev)"}

SPECIES_TARGETS: List[Dict[str, Any]] = [
    {
        "species_id": "kiwi_brown_ni",
        "common_name": "North Island Brown Kiwi",
        "scientific_name": "Apteryx mantelli",
        "lat": -38.68,
        "lon": 176.07,
        "action_window": "Nightly (18:00-04:00)",
        "primary_action": "Dispatch stoat-trap checks, dog-roaming patrols, and chick-lift checks in high-risk bush pockets.",
    },
    {
        "species_id": "penguin_african",
        "common_name": "African Penguin",
        "scientific_name": "Spheniscus demersus",
        "lat": -33.01,
        "lon": 17.95,
        "action_window": "Dawn / Dusk Colony Window",
        "primary_action": "Monitor foraging-trip anomalies and coordinate colony prey/fishery-buffer alerts.",
    },
    {
        "species_id": "penguin_emperor",
        "common_name": "Emperor Penguin",
        "scientific_name": "Aptenodytes forsteri",
        "lat": -70.00,
        "lon": 24.00,
        "action_window": "Pre-Fledging Watch (Sep-Nov)",
        "primary_action": "Track extreme cold/wind/ice-breakup anomalies and alert coastal monitoring stations.",
    },
]


def get_gbif_taxon_key(scientific_name: str) -> Optional[int]:
    url = "https://api.gbif.org/v1/species/match"
    resp = requests.get(url, params={"name": scientific_name}, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    key = data.get("usageKey")
    return int(key) if key is not None else None


def get_gbif_yearly_counts(taxon_key: int, years: List[int]) -> Dict[int, int]:
    url = "https://api.gbif.org/v1/occurrence/search"
    counts: Dict[int, int] = {}
    for yr in years:
        resp = requests.get(
            url,
            params={"taxonKey": taxon_key, "year": yr, "limit": 0},
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        counts[yr] = int(resp.json().get("count", 0))
    return counts


def get_weather_anomaly(lat: float, lon: float) -> Dict[str, Any]:
    url = "https://api.open-meteo.com/v1/forecast"
    resp = requests.get(
        url,
        params={
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
            "past_days": 30,
            "forecast_days": 7,
            "timezone": "UTC",
        },
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    daily = resp.json().get("daily", {})
    max_temps = [t for t in daily.get("temperature_2m_max", []) if t is not None]
    rain_vals = [r for r in daily.get("precipitation_sum", []) if r is not None]

    avg_max_temp = round(sum(max_temps) / len(max_temps), 2) if max_temps else 0.0
    total_rain_37d = round(sum(rain_vals), 2) if rain_vals else 0.0
    return {
        "avg_daily_max_temp_c_37d": avg_max_temp,
        "total_precip_mm_37d": total_rain_37d,
    }


def compute_risk_and_drivers(
    species: Dict[str, Any],
    yearly_counts: Dict[int, int],
    weather: Dict[str, Any],
) -> Tuple[float, str, List[Dict[str, Any]]]:
    c_2022 = yearly_counts.get(2022, 0)
    c_2023 = yearly_counts.get(2023, 0)
    c_2024 = yearly_counts.get(2024, 0)
    c_2025 = yearly_counts.get(2025, 0)

    baseline_avg = (c_2022 + c_2023 + c_2024) / 3.0
    if baseline_avg > 0:
        recent_change_pct = ((c_2025 - baseline_avg) / baseline_avg) * 100.0
    else:
        recent_change_pct = -100.0 if c_2025 == 0 else 0.0

    sighting_drop_risk = max(0.0, min(0.45, (-recent_change_pct / 100.0) * 0.45))
    low_record_density_risk = 0.25 if c_2025 < 50 else (0.12 if c_2025 < 250 else 0.04)

    temp_c = weather["avg_daily_max_temp_c_37d"]
    rain_mm = weather["total_precip_mm_37d"]
    weather_note = f"37d avg max temp {temp_c}C, rain {rain_mm}mm"

    if species["species_id"].startswith("penguin") and temp_c > 12.0:
        weather_stress_risk = 0.22
        weather_note = f"Warm thermal window ({temp_c}C avg max) for cold/coastal habitat"
    elif rain_mm > 220.0:
        weather_stress_risk = 0.16
        weather_note = f"High 37d rainfall ({rain_mm}mm) increasing burrow/chilling stress"
    else:
        weather_stress_risk = 0.08

    risk_score = round(min(0.99, max(0.05, sighting_drop_risk + low_record_density_risk + weather_stress_risk)), 2)

    if risk_score >= 0.60:
        cohort = "HIGH-RISK"
    elif risk_score >= 0.30:
        cohort = "MID-RISK"
    else:
        cohort = "STABLE"

    drivers = [
        {
            "factor": "Recent Occurrence Trend (2025 vs 2022-24 avg)",
            "impact": round(sighting_drop_risk, 2),
            "detail": f"2025 records: {c_2025} vs 3-yr avg {round(baseline_avg, 1)} ({round(recent_change_pct, 1)}%)",
        },
        {
            "factor": "Observation / Population Sparsity",
            "impact": round(low_record_density_risk, 2),
            "detail": f"{c_2025} public GBIF records logged in 2025",
        },
        {
            "factor": "Environmental & Weather Stress",
            "impact": round(weather_stress_risk, 2),
            "detail": weather_note,
        },
    ]
    drivers.sort(key=lambda x: x["impact"], reverse=True)
    return risk_score, cohort, drivers[:3]


def analyze_species(species: Dict[str, Any]) -> Dict[str, Any]:
    taxon_key = get_gbif_taxon_key(species["scientific_name"])
    yearly_counts = get_gbif_yearly_counts(taxon_key, [2022, 2023, 2024, 2025]) if taxon_key else {}
    weather = get_weather_anomaly(species["lat"], species["lon"])
    risk_score, cohort, top_3_drivers = compute_risk_and_drivers(species, yearly_counts, weather)

    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "species_id": species["species_id"],
        "common_name": species["common_name"],
        "scientific_name": species["scientific_name"],
        "gbif_taxon_key": taxon_key,
        "risk_score": risk_score,
        "cohort": cohort,
        "top_3_drivers": top_3_drivers,
        "recommended_action": {
            "window": species["action_window"],
            "action": species["primary_action"],
        },
        "raw_signals": {
            "gbif_yearly_counts": yearly_counts,
            "open_meteo_37d": weather,
        },
    }


def main() -> None:
    results = [analyze_species(sp) for sp in SPECIES_TARGETS]
    output_path = "day1_species_risk_report.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    for item in results:
        print(f"\n=== {item['common_name']} ({item['scientific_name']}) ===")
        print(f"Risk Score: {item['risk_score']} | Cohort: {item['cohort']}")
        for idx, drv in enumerate(item["top_3_drivers"], start=1):
            print(f"  Driver {idx} [+{drv['impact']}]: {drv['factor']} -> {drv['detail']}")
        print(f"Action [{item['recommended_action']['window']}]: {item['recommended_action']['action']}")

    print(f"\nSaved JSON output to {output_path}")


if __name__ == "__main__":
    main()