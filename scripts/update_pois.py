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

DATA_DIR = Path("data")

OVERPASS_SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

MAX_RETRIES = 5

# Pause nach erfolgreicher Abfrage
REQUEST_DELAY = 10


# ============================================================
# POI-KATEGORIEN
# ============================================================
#
# Jede Kategorie bekommt eine eigene JSON-Datei.
#
# query:
#   OSM-Tags, nach denen gesucht wird.
#
# output:
#   Name der erzeugten JSON-Datei.
#
# type:
#   Interner Typ für die spätere Verwendung in index.html.
#
# ============================================================

POI_TYPES = [

    {
        "name": "Mountain Passes",
        "type": "mountain_pass",
        "output": "mountain_passes.json",
        "query": 'node["mountain_pass"="yes"]'
    },

    {
        "name": "Hotels",
        "type": "hotel",
        "output": "hotels.json",
        "query": 'node["tourism"="hotel"]'
    },

    {
        "name": "Restaurants",
        "type": "restaurant",
        "output": "restaurants.json",
        "query": 'node["amenity"="restaurant"]'
    },

    {
        "name": "Tankstellen",
        "type": "fuel",
        "output": "fuel.json",
        "query": 'node["amenity"="fuel"]'
    },

    {
        "name": "Campingplätze",
        "type": "campsite",
        "output": "campsites.json",
        "query": 'node["tourism"="camp_site"]'
    },

    {
        "name": "Aussichtspunkte",
        "type": "viewpoint",
        "output": "viewpoints.json",
        "query": 'node["tourism"="viewpoint"]'
    },

    {
        "name": "Motorradhändler",
        "type": "motorcycle_shop",
        "output": "motorcycle_shops.json",
        "query": 'node["shop"="motorcycle"]'
    },

    {
        "name": "Ladestationen",
        "type": "charging_station",
        "output": "charging_stations.json",
        "query": 'node["amenity"="charging_station"]'
    },
]


# ============================================================
# START
# ============================================================

print()
print("========================================")
print("OSM POI DATABASE UPDATE")
print("========================================")
print()

print(
    f"Gesamtgebiet: "
    f"{SOUTH},{WEST} → {NORTH},{EAST}"
)

print(
    f"Kategorien: {len(POI_TYPES)}"
)

print()


# ============================================================
# OVERPASS QUERY
# ============================================================

def build_query(
    osm_query,
    south,
    west,
    north,
    east
):

    return f"""
[out:json][timeout:120];

{osm_query}
    ({south},{west},{north},{east});

out body;
"""


# ============================================================
# OVERPASS REQUEST
# ============================================================

def query_overpass(
    poi_type,
    osm_query,
    south,
    west,
    north,
    east
):

    query = build_query(
        osm_query,
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

        server = OVERPASS_SERVERS[
            attempt % len(
                OVERPASS_SERVERS
            )
        ]


        print()
        print("----------------------------------------")
        print(
            f"Typ: {poi_type}"
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


            print(
                f"Overpass liefert "
                f"{len(elements)} Objekte."
            )


            print(
                f"Warte "
                f"{REQUEST_DELAY} Sekunden..."
            )

            time.sleep(
                REQUEST_DELAY
            )


            return elements


        except urllib.error.HTTPError as e:

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
                    "Rate Limit erreicht."
                )

                print(
                    f"Warte "
                    f"{wait_time} Sekunden..."
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
                    "Overpass momentan "
                    "nicht verfügbar."
                )

                print(
                    f"Warte "
                    f"{wait_time} Sekunden..."
                )

                time.sleep(
                    wait_time
                )

                continue


            raise


        except (
            urllib.error.URLError,
            TimeoutError
        ) as e:

            print(
                f"Netzwerkfehler: {e}"
            )


            if attempt < MAX_RETRIES - 1:

                wait_time = (
                    20 * (attempt + 1)
                )

                print(
                    f"Warte "
                    f"{wait_time} Sekunden..."
                )

                time.sleep(
                    wait_time
                )

                continue


            raise


        except Exception as e:

            print(
                f"Unerwarteter Fehler: "
                f"{type(e).__name__}: {e}"
            )


            if attempt < MAX_RETRIES - 1:

                wait_time = (
                    20 * (attempt + 1)
                )

                print(
                    f"Warte "
                    f"{wait_time} Sekunden..."
                )

                time.sleep(
                    wait_time
                )

                continue


            raise


    raise RuntimeError(
        f"POI-Typ '{poi_type}' konnte "
        f"nicht geladen werden."
    )


# ============================================================
# OSM DATEN AUFBEREITEN
# ============================================================

def convert_elements(
    elements
):

    places = []

    seen_ids = set()


    for element in elements:

        if element.get("type") != "node":
            continue


        osm_id = element.get("id")

        if osm_id is None:
            continue


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


        # ----------------------------------------------------
        # NAME
        # ----------------------------------------------------

        name = (
            tags.get("name")
            or tags.get("name:de")
            or tags.get("name:en")
            or "Unbenannter POI"
        )


        place = {
            "id": osm_id,
            "name": name,
            "lat": lat,
            "lng": lon
        }


        # ----------------------------------------------------
        # DEUTSCHER NAME
        # ----------------------------------------------------

        if tags.get(
            "name:de"
        ):

            place["name_de"] = (
                tags["name:de"]
            )


        # ----------------------------------------------------
        # ENGLISCHER NAME
        # ----------------------------------------------------

        if tags.get(
            "name:en"
        ):

            place["name_en"] = (
                tags["name:en"]
            )


        # ----------------------------------------------------
        # HÖHE
        # ----------------------------------------------------

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


        # ----------------------------------------------------
        # WIKIDATA
        # ----------------------------------------------------

        if tags.get(
            "wikidata"
        ):

            place["wikidata"] = (
                tags["wikidata"]
            )


        # ----------------------------------------------------
        # WEBSITE
        # ----------------------------------------------------

        if tags.get(
            "website"
        ):

            place["website"] = (
                tags["website"]
            )


        # ----------------------------------------------------
        # TELEFON
        # ----------------------------------------------------

        if tags.get(
            "phone"
        ):

            place["phone"] = (
                tags["phone"]
            )


        # ----------------------------------------------------
        # ÖFFNUNGSZEITEN
        # ----------------------------------------------------

        if tags.get(
            "opening_hours"
        ):

            place["opening_hours"] = (
                tags["opening_hours"]
            )


        # ----------------------------------------------------
        # ADRESSE
        # ----------------------------------------------------

        address_fields = {

            "street": "addr:street",

            "housenumber":
                "addr:housenumber",

            "postcode":
                "addr:postcode",

            "city":
                "addr:city",

            "country":
                "addr:country"
        }


        address = {}


        for output_name, osm_tag in (
            address_fields.items()
        ):

            if tags.get(osm_tag):

                address[output_name] = (
                    tags[osm_tag]
                )


        if address:

            place["address"] = address


        places.append(
            place
        )


    # --------------------------------------------------------
    # SORTIEREN
    # --------------------------------------------------------

    places.sort(
        key=lambda p:
            p.get(
                "name",
                ""
            ).lower()
    )


    return places


# ============================================================
# JSON SCHREIBEN
# ============================================================

def write_json(
    poi_config,
    places
):

    output_file = (
        DATA_DIR
        / poi_config["output"]
    )


    output = {

        "version": 1,

        "type":
            poi_config["type"],

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


    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


    with output_file.open(
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


    return output_file


# ============================================================
# HAUPTPROGRAMM
# ============================================================

total_places = 0


for poi_config in POI_TYPES:

    print()
    print()
    print("========================================")
    print(
        f"STARTE: "
        f"{poi_config['name']}"
    )
    print("========================================")


    elements = query_overpass(

        poi_config["type"],

        poi_config["query"],

        SOUTH,
        WEST,
        NORTH,
        EAST
    )


    places = convert_elements(
        elements
    )


    output_file = write_json(
        poi_config,
        places
    )


    total_places += len(
        places
    )


    print()
    print("----------------------------------------")
    print(
        f"{poi_config['name']} abgeschlossen"
    )
    print(
        f"Objekte: {len(places)}"
    )
    print(
        f"Datei: {output_file}"
    )
    print("----------------------------------------")


# ============================================================
# FERTIG
# ============================================================

print()
print()
print("========================================")
print("OSM POI UPDATE ABGESCHLOSSEN")
print("========================================")

print(
    f"Kategorien: "
    f"{len(POI_TYPES)}"
)

print(
    f"Gesamtzahl POIs: "
    f"{total_places}"
)

print(
    f"Gebiet: "
    f"{SOUTH},{WEST} → {NORTH},{EAST}"
)

print()
print("Erzeugte Dateien:")

for poi_config in POI_TYPES:

    print(
        f"  - data/"
        f"{poi_config['output']}"
    )

print()
print("========================================")
