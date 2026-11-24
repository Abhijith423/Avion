import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import requests

TIMEOUT = 25
HEADERS = {"User-Agent": "AvianNova-LiveAPI/1.0 (local-research)"}
EBIRD_API_KEY = os.getenv("EBIRD_API_KEY", "8f4af171-0852-4271-8dc9-5d1c49ec8909")


def fetch_gbif_live(scientific_name: str, lat: float, lon: float) -> Dict[str, Any]:
    match_res = requests.get(
        "https://api.gbif.org/v1/species/match",
        params={"name": scientific_name},
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    match_res.raise_for_status()
    match_data = match_res.json()
    taxon_key = match_data.get("usageKey")

    recent_2025 = 0
    recent_2026 = 0
    sample_coords: List[Dict[str, Any]] = []

    if taxon_key:
        c25 = requests.get(
            "https://api.gbif.org/v1/occurrence/search",
            params={"taxonKey": taxon_key, "year": 2025, "hasCoordinate": "true", "limit": 5},
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        c25.raise_for_status()
        d25 = c25.json()
        recent_2025 = int(d25.get("count", 0))

        c26 = requests.get(
            "https://api.gbif.org/v1/occurrence/search",
            params={"taxonKey": taxon_key, "year": 2026, "hasCoordinate": "true", "limit": 5},
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        c26.raise_for_status()
        d26 = c26.json()
        recent_2026 = int(d26.get("count", 0))

        for rec in d26.get("results", []) or d25.get("results", []):
            sample_coords.append(
                {
                    "eventDate": rec.get("eventDate"),
                    "country": rec.get("country"),
                    "lat": rec.get("decimalLatitude"),
                    "lon": rec.get("decimalLongitude"),
                }
            )

    return {
        "taxon_key": taxon_key,
        "matched_scientific_name": match_data.get("scientificName"),
        "taxonomic_status": match_data.get("status"),
        "occurrences_2025": recent_2025,
        "occurrences_2026": recent_2026,
        "sample_records": sample_coords[:3],
    }


def fetch_inaturalist_live(scientific_name: str, lat: float, lon: float) -> Dict[str, Any]:
    res = requests.get(
        "https://api.inaturalist.org/v1/observations",
        params={
            "taxon_name": scientific_name,
            "lat": lat,
            "lng": lon,
            "radius": 250,
            "per_page": 5,
            "order_by": "observed_on",
            "order": "desc",
        },
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    res.raise_for_status()
    data = res.json()
    latest_obs = []
    for obs in data.get("results", [])[:3]:
        latest_obs.append(
            {
                "observed_on": obs.get("observed_on"),
                "quality_grade": obs.get("quality_grade"),
                "place_guess": obs.get("place_guess"),
            }
        )
    return {
        "total_results_within_250km": int(data.get("total_results", 0)),
        "latest_observations": latest_obs,
    }


def fetch_open_meteo_live(lat: float, lon: float) -> Dict[str, Any]:
    now_utc = datetime.now(timezone.utc).date()
    start_7d = (now_utc - timedelta(days=7)).isoformat()
    end_7d = now_utc.isoformat()

    weather_res = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,precipitation,wind_speed_10m",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
            "past_days": 7,
            "forecast_days": 3,
            "timezone": "UTC",
        },
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    weather_res.raise_for_status()
    w_json = weather_res.json()

    marine_data: Optional[Dict[str, Any]] = None
    try:
        m_res = requests.get(
            "https://marine-api.open-meteo.com/v1/marine",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "sea_surface_temperature,wave_height",
                "timezone": "UTC",
            },
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        m_res.raise_for_status()
        marine_data = m_res.json().get("current")
    except requests.RequestException:
        marine_data = None

    return {
        "window_utc": f"{start_7d} to {end_7d} (+3d forecast)",
        "current_weather": w_json.get("current"),
        "daily_max_temps_c": w_json.get("daily", {}).get("temperature_2m_max", []),
        "daily_precip_mm": w_json.get("daily", {}).get("precipitation_sum", []),
        "current_marine": marine_data,
    }


def fetch_ebird_live(lat: float, lon: float) -> Dict[str, Any]:
    if not EBIRD_API_KEY:
        return {"error": "Missing eBird API key"}
    res = requests.get(
        "https://api.ebird.org/v2/data/obs/geo/recent",
        params={"lat": round(lat, 2), "lng": round(lon, 2), "dist": 50, "back": 14},
        headers={"X-eBirdApiToken": EBIRD_API_KEY, **HEADERS},
        timeout=TIMEOUT,
    )
    res.raise_for_status()
    items = res.json()
    return {
        "recent_checklist_obs_50km_14d": len(items),
        "sample_species": [
            {"comName": x.get("comName"), "obsDt": x.get("obsDt"), "locName": x.get("locName")}
            for x in items[:3]
        ],
    }


def main() -> None:
    targets = [
        {"common_name": "North Island Brown Kiwi", "scientific_name": "Apteryx mantelli", "lat": -38.68, "lon": 176.07},
        {"common_name": "African Penguin", "scientific_name": "Spheniscus demersus", "lat": -33.01, "lon": 17.95},
    ]

    report: List[Dict[str, Any]] = []
    for t in targets:
        gbif = fetch_gbif_live(t["scientific_name"], t["lat"], t["lon"])
        inat = fetch_inaturalist_live(t["scientific_name"], t["lat"], t["lon"])
        meteo = fetch_open_meteo_live(t["lat"], t["lon"])
        ebird = fetch_ebird_live(t["lat"], t["lon"])

        entry = {
            "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
            "common_name": t["common_name"],
            "scientific_name": t["scientific_name"],
            "gbif_live": gbif,
            "inaturalist_live": inat,
            "open_meteo_live": meteo,
            "ebird_live": ebird,
        }
        report.append(entry)

        print(f"\n--- {t['common_name']} ({t['scientific_name']}) ---")
        print("GBIF 2025 / 2026:", gbif["occurrences_2025"], "/", gbif["occurrences_2026"])
        print("iNat (250km):", inat["total_results_within_250km"])
        print("Current Weather:", meteo["current_weather"])
        if meteo["current_marine"]:
            print("Current Marine:", meteo["current_marine"])
        print("eBird (50km, 14d):", ebird.get("recent_checklist_obs_50km_14d"))

    with open("day3_live_api_output.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print("\nSaved raw live API responses to day3_live_api_output.json")


if __name__ == "__main__":
    main()