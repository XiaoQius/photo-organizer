"""GPS 坐标 → 城市名：基于内置城市坐标集的最近邻匹配（离线可用）。"""

import json
import math
from pathlib import Path

from app.config import CITY_MAX_DISTANCE_KM

_DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "cities.json"
_cities: list[dict] | None = None


def _load() -> list[dict]:
    global _cities
    if _cities is None:
        with open(_DATA_FILE, encoding="utf-8") as f:
            _cities = json.load(f)
    return _cities


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def nearest_city(lat: float, lon: float) -> str | None:
    """返回距离最近的城市名；超过 CITY_MAX_DISTANCE_KM 视为未知地点返回 None。"""
    best_name, best_dist = None, float("inf")
    for c in _load():
        d = _haversine_km(lat, lon, c["lat"], c["lon"])
        if d < best_dist:
            best_name, best_dist = c["name"], d
    return best_name if best_dist <= CITY_MAX_DISTANCE_KM else None
