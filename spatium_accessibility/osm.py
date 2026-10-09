"""Bounded Overpass download. No user road data is uploaded."""
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ENDPOINT = "https://overpass-api.de/api/interpreter"
MAX_RESPONSE = 25 * 1024 * 1024
MAX_SPAN = 0.15


def validate_bbox(bbox):
    south, west, north, east = bbox
    if not (-90 <= south < north <= 90 and -180 <= west < east <= 180):
        raise ValueError("Geçersiz OSM çalışma alanı; tarih değiştirme çizgisini aşan alanlar desteklenmiyor.")
    if north - south > MAX_SPAN or east - west > MAX_SPAN:
        raise ValueError("OSM alanı çok büyük. Mesafeyi veya başlangıç noktası kapsamını azaltın (en fazla 0,15° × 0,15°).")


def parse_ways(payload):
    roads = []
    excluded = {"motorway", "motorway_link", "trunk", "trunk_link", "construction", "proposed"}
    for element in payload.get("elements", []):
        if element.get("type") != "way":
            continue
        tags = element.get("tags", {})
        if tags.get("highway") in excluded and tags.get("foot") not in {"yes", "designated"}:
            continue
        if tags.get("foot") in {"no", "private"}:
            continue
        if tags.get("access") in {"no", "private"} and tags.get("foot") not in {"yes", "designated", "permissive"}:
            continue
        coords = [(float(p["lon"]), float(p["lat"])) for p in element.get("geometry", [])]
        if len(coords) >= 2:
            # Development walking model rejects grade-separated ways rather than
            # inventing connections at planar crossings. This is visible in UI.
            if tags.get("bridge", "no") != "no" or tags.get("tunnel", "no") != "no" or tags.get("layer", "0") != "0":
                continue
            roads.append(coords)
    if not roads:
        raise ValueError("Bu alanda desteklenen yürünebilir OSM yolu bulunamadı.")
    return roads


def download(bbox, cancel=None):
    from .graph import check_cancel
    validate_bbox(bbox)
    query = '[out:json][timeout:45];way["highway"](%s);out geom;' % ",".join(str(float(v)) for v in bbox)
    request = Request(ENDPOINT, data=urlencode({"data": query}).encode(),
                      headers={"User-Agent": "SpatiumAccessibility/0.1 (QGIS development)",
                               "Content-Type": "application/x-www-form-urlencoded"})
    chunks, size = [], 0
    with urlopen(request, timeout=60) as response:  # nosec B310 - fixed HTTPS Overpass endpoint
        while True:
            check_cancel(cancel)
            chunk = response.read(65536)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_RESPONSE:
                raise ValueError("OSM yanıtı 25 MB sınırını aşıyor; alanı küçültün.")
            chunks.append(chunk)
    payload = json.loads(b"".join(chunks).decode("utf-8"))
    if payload.get("remark"):
        raise ValueError("OSM sorgusu tamamlanamadı: " + str(payload["remark"])[:300])
    return parse_ways(payload)
