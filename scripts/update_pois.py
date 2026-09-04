import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


# ============================================================
# KONFIGURATION
# ============================================================

SOUTH = 43.0
WEST = 4.0
NORTH = 49.5
EAST = 17.0

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

OUTPUT_FILE = Path("data/mountain_passes.json")


# ============================================================
# OVERPASS ABFRAGE
# ============================================================

query = f"""
[out:json][timeout:120];

node["mountain_pass"="yes"]
  ({SOUTH},{WEST},{NORTH},{EAST});

out body;
"""


print("Starte Overpass-Abfrage...")
print(
    f"Gebiet: {SOUTH},{WEST} → {NORTH},{EAST}"
)


# ============================================================
# REQUEST
# ============================================================

data = urllib.parse.urlencode({
    "data": query
}).encode("utf-8")

request = urllib.request.Request(
    OVERPASS_URL,
    data=data,
    headers={
        "User-Agent":
            "motorcycle-route-planner/1.0"
    }
)


with urllib.request.urlopen(
    request,
    timeout=180
) as response:

    raw = response.read()


osm_data = json.loads(
    raw.decode("utf-8")
)


# ============================================================
# DATEN REDUZIEREN
# ============================================================

places = []

for element in osm_data.get("elements", []):

    if element.get("type") != "node":
        continue

    tags = element.get("tags", {})

    lat = element.get("lat")
    lon = element.get("lon")

    if lat is None or lon is None:
        continue

    name = (
        tags.get("name")
        or tags.get("name:de")
        or tags.get("name:en")
        or "Gebirgspass"
    )

    place = {
        "id": element["id"],
        "name": name,
        "lat": lat,
        "lng": lon
    }

    if tags.get("ele"):
        try:
            place["ele"] = float(
                str(tags["ele"])
                .replace(",", ".")
                .replace("m", "")
                .strip()
            )
        except ValueError:
            pass

    if tags.get("name:de"):
        place["name_de"] = tags["name:de"]

    if tags.get("wikidata"):
        place["wikidata"] = tags["wikidata"]

    places.append(place)


# ============================================================
# SORTIEREN
# ============================================================

places.sort(
    key=lambda p:
        p.get("name", "").lower()
)


# ============================================================
# AUSGABE
# ============================================================

output = {
    "version": 1,

    "type": "mountain_pass",

    "generatedAt": datetime.now(
        timezone.utc
    ).isoformat(),

    "source": "OpenStreetMap",

    "bounds": {
        "south": SOUTH,
        "west": WEST,
        "north": NORTH,
        "east": EAST
    },

    "places": places
}


OUTPUT_FILE.parent.mkdir(
    parents=True,
    exist_ok=True
)


print()
print("DEBUG:")
print(f"OUTPUT_FILE = {OUTPUT_FILE}")
print(f"ABSOLUTER PFAD = {OUTPUT_FILE.resolve()}")
print()

with OUTPUT_FILE.open(
    "w",
    encoding="utf-8"
) as file:

    json.dump(
        output,
        file,
        ensure_ascii=False,
        separators=(",", ":")
    )


print()
print("========================================")
print("POI-Update abgeschlossen")
print("========================================")
print(
    f"Typ: mountain_pass"
)
print(
    f"Gefundene Gebirgspässe: {len(places)}"
)
print(
    f"Datei: {OUTPUT_FILE}"
)
print(
    f"Gebiet: {SOUTH},{WEST} → {NORTH},{EAST}"
)
print("========================================")