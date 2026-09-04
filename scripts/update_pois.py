import json
import time
import urllib.error
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

OUTPUT_FILE = Path(
    "data/mountain_passes.json"
)

# Mehrere öffentliche Overpass-Server.
# Falls einer rate-limited oder überlastet ist,
# wird automatisch der nächste verwendet.

OVERPASS_SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

# Anzahl Wiederholungen pro Anfrage
MAX_RETRIES = 5

# Wartezeit zwischen erfolgreichen Requests
REQUEST_DELAY = 10


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

print()


# ============================================================
# OVERPASS QUERY
# ============================================================

def build_query(
    south,
    west,
    north,
    east
):

    return f"""
[out:json][timeout:120];

node["mountain_pass"="yes"]
    ({south},{west},{north},{east});

out body;
"""


# ============================================================
# OVERPASS REQUEST
# ============================================================

def query_overpass(
    region_name,
    south,
    west,
    north,
    east
):

    query = build_query(
        south,
        west,
        north,
        east
    )

    data = urllib.parse.urlencode({
        "data": query
    }).encode("utf-8")


    for attempt in range(
        MAX_RETRIES
    ):

        # Server bei jedem Versuch wechseln
        server = OVERPASS_SERVERS[
            attempt % len(
                OVERPASS_SERVERS
            )
        ]


        print()
        print("----------------------------------------")
        print(
            f"Region: {region_name}"
        )
        print(
            f"Versuch: "
            f"{attempt + 1}/{MAX_RETRIES}"
        )
        print(
            f"Server: {server}"
        )
        print("----------------------------------------")


        request = urllib.request.Request(
            server,
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


            print()
            print(
                f"Overpass liefert "
                f"{len(elements)} Objekte."
            )


            # Server nach erfolgreichem Request
            # kurz entlasten.
            print(
                f"Warte {REQUEST_DELAY} Sekunden..."
            )

            time.sleep(
                REQUEST_DELAY
            )


            return elements


        except urllib.error.HTTPError as e:

            print()
            print(
                f"HTTP {e.code}: {e.reason}"
            )


            # ------------------------------------------------
            # RATE LIMIT
            # ------------------------------------------------

            if e.code == 429:

                wait_time = (
                    30 * (attempt + 1)
                )

                print(
                    "Overpass meldet "
                    "Too Many Requests."
                )

                print(
                    f"Warte {wait_time} Sekunden "
                    "vor dem nächsten Versuch..."
                )

                time.sleep(
                    wait_time
                )

                continue


            # ------------------------------------------------
            # TEMPORÄRE SERVERFEHLER
            # ------------------------------------------------

            if e.code in (
                502,
                503,
                504
            ):

                wait_time = (
                    20 * (attempt + 1)
                )

                print(
                    "Overpass ist momentan "
                    "nicht verfügbar."
                )

                print(
                    f"Warte {wait_time} Sekunden..."
                )

                time.sleep(
                    wait_time
                )

                continue


            # Andere HTTP-Fehler sind echte Fehler
            raise


        except (
            urllib.error.URLError,
            TimeoutError
        ) as e:

            print()
            print(
                f"Netzwerkfehler: {e}"
            )


            if attempt < MAX_RETRIES - 1:

                wait_time = (
                    20 * (attempt + 1)
                )

                print(
                    f"Warte {wait_time} Sekunden..."
                )

                time.sleep(
                    wait_time
                )

                continue


            raise


        except Exception as e:

            print()
            print(
                f"Unerwarteter Fehler: "
                f"{type(e).__name__}: {e}"
            )


            if attempt < MAX_RETRIES - 1:

                wait_time = (
                    20 * (attempt + 1)
                )

                print(
                    f"Warte {wait_time} Sekunden..."
                )

                time.sleep(
                    wait_time
                )

                continue


            raise


    raise RuntimeError(
        f"Region '{region_name}' konnte "
        f"nach {MAX_RETRIES} Versuchen "
        f"nicht geladen werden."
    )


# ============================================================
# HAUPTABFRAGE
# ============================================================

print()
print("Starte Overpass-Abfrage...")
print()

elements = query_overpass(
    "Gesamtgebiet",
    SOUTH,
    WEST,
    NORTH,
    EAST
)


# ============================================================
# DATEN REDUZIEREN
# ============================================================

places = []

seen_ids = set()


for element in elements:

    if element.get("type") != "node":
        continue


    osm_id = element.get("id")

    if osm_id is None:
        continue


    # Sicherheit gegen eventuelle Duplikate
    if osm_id in seen_ids:
        continue

    seen_ids.add(
        osm_id
    )


    tags = element.get(
        "tags",
        {}
    )


    lat = element.get(
        "lat"
    )

    lon = element.get(
        "lon"
    )


    if lat is None or lon is None:
        continue


    # --------------------------------------------------------
    # NAME
    # --------------------------------------------------------

    name = (
        tags.get("name")
        or tags.get("name:de")
        or tags.get("name:en")
        or "Gebirgspass"
    )


    # --------------------------------------------------------
    # POI
    # --------------------------------------------------------

    place = {
        "id": osm_id,
        "name": name,
        "lat": lat,
        "lng": lon
    }


    # --------------------------------------------------------
    # HÖHE
    # --------------------------------------------------------

    if tags.get("ele"):

        try:

            place["ele"] = float(
                str(
                    tags["ele"]
                )
                .replace(
                    ",",
                    "."
                )
                .replace(
                    "m",
                    ""
                )
                .strip()
            )

        except ValueError:

            pass


    # --------------------------------------------------------
    # DEUTSCHER NAME
    # --------------------------------------------------------

    if tags.get(
        "name:de"
    ):

        place["name_de"] = (
            tags["name:de"]
        )


    # --------------------------------------------------------
    # WIKIDATA
    # --------------------------------------------------------

    if tags.get(
        "wikidata"
    ):

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
# AUSGABE
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
# DATEI SCHREIBEN
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
        separators=(
            ",",
            ":"
        )
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
