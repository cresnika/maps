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
        "query": 'node["mountain_pass"="yes"]',
        "road_filter": (
            '^(motorway|trunk|primary|secondary|tertiary|'
            'unclassified|residential|service)$'
        ),
        "road_distance_m": 50
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

def build_mountain_pass_query(
    south,
    west,
    north,
    east,
    road_filter,
    distance_m
):
    """
    Lädt alle mountain_pass=yes-Knoten und zusätzlich nur
    relevante highway-Wege im Umkreis der Pässe.

    Wichtig:
    Es gibt NICHT einen Request pro Pass. Die komplette Prüfung
    erfolgt in einer einzigen Overpass-Abfrage.
    """
    return f"""
[out:json][timeout:120];

node["mountain_pass"="yes"]({south},{west},{north},{east})->.passes;

(
  .passes;
  way(around.passes:{distance_m})
    ["highway"~"{road_filter}"];
);

out geom;
"""


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
    east,
    poi_config=None
):

    if poi_type == "mountain_pass":
        # Eine einzige Overpass-Abfrage für alle Pässe + nahe Straßen.
        # Keine Einzelanfragen pro Pass.
        query = build_mountain_pass_query(
            south,
            west,
            north,
            east,
            road_filter=(
                poi_config.get(
                    "road_filter",
                    '^(motorway|trunk|primary|secondary|tertiary|'
                    'unclassified|residential|service)$'
                )
                if poi_config
                else
                '^(motorway|trunk|primary|secondary|tertiary|'
                'unclassified|residential|service)$'
            ),
            distance_m=(
                poi_config.get("road_distance_m", 50)
                if poi_config
                else 50
            )
        )
    else:
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
# MOUNTAIN-PASS FILTER
# ============================================================

def point_to_segment_distance_m(
    point_lat,
    point_lon,
    lat1,
    lon1,
    lat2,
    lon2
):
    """
    Näherungsweise Punkt-zu-Segment-Distanz in Metern.

    Für die hier verwendete Distanz von maximal 50 m ist eine
    lokale equirectangular Projektion ausreichend genau.
    """
    import math

    earth_radius_m = 6371000.0
    lat0 = math.radians(point_lat)

    def project(lat, lon):
        x = (
            math.radians(lon)
            * earth_radius_m
            * math.cos(lat0)
        )
        y = (
            math.radians(lat)
            * earth_radius_m
        )
        return x, y

    px, py = project(point_lat, point_lon)
    ax, ay = project(lat1, lon1)
    bx, by = project(lat2, lon2)

    dx = bx - ax
    dy = by - ay

    segment_length_sq = dx * dx + dy * dy

    if segment_length_sq == 0:
        return ((px - ax) ** 2 + (py - ay) ** 2) ** 0.5

    t = (
        (px - ax) * dx +
        (py - ay) * dy
    ) / segment_length_sq

    t = max(0.0, min(1.0, t))

    closest_x = ax + t * dx
    closest_y = ay + t * dy

    return (
        (px - closest_x) ** 2 +
        (py - closest_y) ** 2
    ) ** 0.5


def filter_mountain_pass_elements(
    elements,
    max_distance_m=50
):
    """
    Behält nur mountain_pass=yes-Knoten, die tatsächlich
    maximal max_distance_m von einer relevanten Straße entfernt
    sind.

    Die Straßen werden aus derselben Overpass-Antwort verwendet.
    Dadurch entstehen keine zusätzlichen Requests.
    """
    passes = []
    roads = []

    for element in elements:
        element_type = element.get("type")

        if element_type == "node":
            tags = element.get("tags", {})

            if tags.get("mountain_pass") == "yes":
                passes.append(element)

        elif element_type == "way":
            tags = element.get("tags", {})
            geometry = element.get("geometry", [])

            if (
                tags.get("highway") and
                geometry
            ):
                roads.append(geometry)

    print(
        f"Mountain Passes gefunden: {len(passes)}"
    )

    print(
        f"Relevante Straßenabschnitte: {len(roads)}"
    )

    filtered = []

    for index, pass_node in enumerate(passes, start=1):
        pass_lat = pass_node.get("lat")
        pass_lon = pass_node.get("lon")

        if pass_lat is None or pass_lon is None:
            continue

        closest_distance = float("inf")

        for geometry in roads:
            previous = None

            for point in geometry:
                lat = point.get("lat")
                lon = point.get("lon")

                if lat is None or lon is None:
                    continue

                if previous is not None:
                    distance = point_to_segment_distance_m(
                        pass_lat,
                        pass_lon,
                        previous[0],
                        previous[1],
                        lat,
                        lon
                    )

                    if distance < closest_distance:
                        closest_distance = distance

                        if closest_distance <= max_distance_m:
                            break

                previous = (lat, lon)

            if closest_distance <= max_distance_m:
                break

        if closest_distance <= max_distance_m:
            filtered.append(pass_node)

    print(
        f"Mountain Passes an Straßen: "
        f"{len(filtered)}"
    )

    print(
        f"Verworfen wegen > {max_distance_m} m Abstand: "
        f"{len(passes) - len(filtered)}"
    )

    return filtered


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


    if poi_config["type"] == "mountain_pass":
        elements = filter_mountain_pass_elements(
            elements,
            max_distance_m=poi_config.get(
                "road_distance_m",
                50
            )
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
