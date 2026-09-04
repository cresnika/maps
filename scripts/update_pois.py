import json
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path


# ============================================================
# KONFIGURATION
# ============================================================

# Gesamter Datenbereich:
SOUTH = 43.0
WEST = 4.0
NORTH = 49.5
EAST = 17.0

# Mehrere kleinere Regionen.
#
# Jede Region wird separat von Overpass abgefragt.
# Dadurch vermeiden wir einen großen Timeout.
#
# Format:
# (Name, south, west, north, east)

REGIONS = [
    (
        "Westalpen",
        43.0,
        4.0,
        46.5,
        8.0
    ),
    (
        "Schweiz",
        45.0,
        6.0,
        48.0,
        10.5
    ),
    (
        "Nordalpen",
        46.5,
        8.0,
        49.5,
        13.0
    ),
    (
        "Ostalpen",
        46.0,
        11.5,
        49.5,
        17.0
    ),
    (
        "Südalpen_West",
        43.0,
        7.0,
        46.0,
        11.5
    ),
    (
        "Südalpen_Ost",
        44.0,
        11.0,
        46.5,
        17.0
    ),
    (
        "Südwest",
        43.0,
        4.0,
        46.0,
        7.0
    ),
    (
        "Südost",
        43.0,
        13.0,
        46.0,
        17.0
    )
]


# Overpass-Server
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Zieldatei
OUTPUT_FILE = Path(
    "data/mountain_passes.json"
)


# ============================================================
# START
# ============================================================

print()
print("========================================")
print("Mountain Pass POI Update")
print("========================================")
print()

print("### NEUES SCRIPT WIRD AUSGEFÜHRT ###")
print(
    f"OUTPUT_FILE = {OUTPUT_FILE}"
)
print(
    f"ABSOLUTER PFAD = {OUTPUT_FILE.resolve()}"
)
print()

print(
    f"Gesamtgebiet: "
    f"{SOUTH},{WEST} → {NORTH},{EAST}"
)

print(
    f"Regionen: {len(REGIONS)}"
)

print()


# ============================================================
# OVERPASS ABFRAGE
# ============================================================

def query_overpass(
    region_name,
    south,
    west,
    north,
    east
):

    print("----------------------------------------")
    print(
        f"Region: {region_name}"
    )
    print(
        f"Gebiet: "
        f"{south},{west} → {north},{east}"
    )
    print("----------------------------------------")

    query = f"""
[out:json][timeout:120];

node["mountain_pass"="yes"]
  ({south},{west},{north},{east});

out body;
"""

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

    try:

        with urllib.request.urlopen(
            request,
            timeout=180
        ) as response:

            raw = response.read()

        osm_data = json.loads(
            raw.decode("utf-8")
        )

        elements = osm_data.get(
            "elements",
            []
        )

        print(
            f"Overpass liefert "
            f"{len(elements)} Objekte."
        )

        return elements

    except urllib.error.HTTPError as error:

        print()
        print(
            f"FEHLER in Region "
            f"{region_name}"
        )

        print(
            f"HTTP {error.code}: "
            f"{error.reason}"
        )

        raise

    except urllib.error.URLError as error:

        print()
        print(
            f"NETZWERKFEHLER in Region "
            f"{region_name}"
        )

        print(error)

        raise


# ============================================================
# ALLE REGIONEN ABFRAGEN
# ============================================================

all_elements = []

for region in REGIONS:

    region_name = region[0]
    south = region[1]
    west = region[2]
    north = region[3]
    east = region[4]

    elements = query_overpass(
        region_name,
        south,
        west,
        north,
        east
    )

    all_elements.extend(
        elements
    )

    print()


# ============================================================
# DUPLIKATE ENTFERNEN
# ============================================================

print("----------------------------------------")
print("Entferne Duplikate...")
print("----------------------------------------")

unique_elements = {}

for element in all_elements:

    element_id = element.get("id")

    if element_id is None:
        continue

    unique_elements[
        element_id
    ] = element


print(
    f"Objekte insgesamt: "
    f"{len(all_elements)}"
)

print(
    f"Nach Duplikatbereinigung: "
    f"{len(unique_elements)}"
)

print()


# ============================================================
# DATEN REDUZIEREN
# ============================================================

places = []

for element in unique_elements.values():

    if element.get("type") != "node":
        continue

    tags = element.get(
        "tags",
        {}
    )

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

    # Höhe
    if tags.get("ele"):

        try:

            place["ele"] = float(
                str(
                    tags["ele"]
                )
                .replace(",", ".")
                .replace("m", "")
                .strip()
            )

        except ValueError:

            pass

    # Deutscher Name
    if tags.get("name:de"):

        place["name_de"] = (
            tags["name:de"]
        )

    # Wikidata
    if tags.get("wikidata"):

        place["wikidata"] = (
            tags["wikidata"]
        )

    places.append(
        place
    )


# ============================================================
# SORTIEREN
# ============================================================

places.sort(
    key=lambda p:
        p.get(
            "name",
            ""
        ).lower()
)


# ============================================================
# AUSGABEOBJEKT
# ============================================================

output = {

    "version": 1,

    "type": "mountain_pass",

    "generatedAt":
        datetime.now(
            timezone.utc
        ).isoformat(),

    "source":
        "OpenStreetMap",

    "bounds": {

        "south": SOUTH,

        "west": WEST,

        "north": NORTH,

        "east": EAST

    },

    "places":
        places
}


# ============================================================
# DATEI ERZEUGEN
# ============================================================

OUTPUT_FILE.parent.mkdir(
    parents=True,
    exist_ok=True
)


print()
print("DEBUG:")
print(
    f"OUTPUT_FILE = "
    f"{OUTPUT_FILE}"
)
print(
    f"ABSOLUTER PFAD = "
    f"{OUTPUT_FILE.resolve()}"
)
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


# ============================================================
# FERTIG
# ============================================================

print()
print("========================================")
print("POI-Update abgeschlossen")
print("========================================")

print(
    f"Typ: mountain_pass"
)

print(
    f"Gefundene Gebirgspässe: "
    f"{len(places)}"
)

print(
    f"Datei: {OUTPUT_FILE}"
)

print(
    f"Gebiet: "
    f"{SOUTH},{WEST} → {NORTH},{EAST}"
)

print("========================================")