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

# Pause nach jeder erfolgreichen Abfrage (Sekunden)
REQUEST_DELAY = 6

# Overpass-internes Timeout (Sekunden) - muss kleiner sein als
# der urllib-Timeout weiter unten
OVERPASS_TIMEOUT = 120


# ============================================================
# POI-KATEGORIEN
# ============================================================
#
# Jede Kategorie bekommt eine eigene JSON-Datei.
#
# query:
#   OSM-Tags, nach denen gesucht wird (für "normale" Kategorien).
#
# output:
#   Name der erzeugten JSON-Datei.
#
# type:
#   Interner Typ für die spätere Verwendung in index.html.
#
# tile_size:
#   Kantenlänge der Grid-Kacheln in Grad, in die das
#   Gesamtgebiet für diese Kategorie aufgeteilt wird, bevor
#   Overpass abgefragt wird. Kleinere Kacheln = kleinere,
#   schnellere Einzelabfragen, aber mehr Requests insgesamt.
#   None = keine Kachelung, gesamtes Gebiet in einem Request.
#
# road_filter (nur mountain_pass):
#   Regex der highway-Typen, die als "Straße" zählen. Damit
#   fallen z.B. reine Wanderwege (highway=path/footway) raus.
#
# ============================================================

POI_TYPES = [

    {
        "name": "Mountain Passes",
        "type": "mountain_pass",
        "output": "mountain_passes.json",
        "query": None,
        "road_filter": (
            '^(motorway|trunk|primary|secondary|tertiary|'
            'unclassified|residential|service)$'
        ),
        # Diese Abfrage ist sehr leicht (keine Geometrie nötig),
        # daher reicht ein einziger Request für das Gesamtgebiet.
        "tile_size": None,
    },

    {
        "name": "Hotels",
        "type": "hotel",
        "output": "hotels.json",
        "query": 'node["tourism"="hotel"]',
        "tile_size": 2.0,
    },

    {
        "name": "Restaurants",
        "type": "restaurant",
        "output": "restaurants.json",
        "query": 'node["amenity"="restaurant"]',
        "tile_size": 2.0,
    },

    {
        "name": "Tankstellen",
        "type": "fuel",
        "output": "fuel.json",
        "query": 'node["amenity"="fuel"]',
        "tile_size": 2.0,
    },

    {
        "name": "Campingplätze",
        "type": "campsite",
        "output": "campsites.json",
        "query": 'node["tourism"="camp_site"]',
        "tile_size": 3.0,
    },

    {
        "name": "Aussichtspunkte",
        "type": "viewpoint",
        "output": "viewpoints.json",
        "query": 'node["tourism"="viewpoint"]',
        "tile_size": 3.0,
    },

    {
        "name": "Motorradhändler",
        "type": "motorcycle_shop",
        "output": "motorcycle_shops.json",
        "query": 'node["shop"="motorcycle"]',
        "tile_size": 3.0,
    },

    {
        "name": "Ladestationen",
        "type": "charging_station",
        "output": "charging_stations.json",
        "query": 'node["amenity"="charging_station"]',
        "tile_size": 3.0,
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

print(f"Gesamtgebiet: {SOUTH},{WEST} -> {NORTH},{EAST}")
print(f"Kategorien: {len(POI_TYPES)}")
print()


# ============================================================
# TILING
# ============================================================

def generate_tiles(south, west, north, east, tile_size):
    """
    Teilt das Gesamtgebiet in ein Grid aus kleineren
    Bounding-Boxes auf. Das hält einzelne Overpass-Antworten
    klein und vermeidet Timeouts / Server-Ablehnung bei
    dicht besiedelten POI-Kategorien.

    tile_size=None -> ein einziges "Tile" = das Gesamtgebiet.
    """
    if not tile_size:
        return [(south, west, north, east)]

    tiles = []

    lat = south
    while lat < north:
        lat_end = min(lat + tile_size, north)

        lon = west
        while lon < east:
            lon_end = min(lon + tile_size, east)

            tiles.append((lat, lon, lat_end, lon_end))

            lon = lon_end

        lat = lat_end

    return tiles


# ============================================================
# OVERPASS QUERY BUILDER
# ============================================================

def build_mountain_pass_query(south, west, north, east, road_filter):
    """
    Lädt mountain_pass=yes Knoten, behält aber nur jene, die
    tatsächlich Mitglied eines Straßen-Ways (highway=...) sind.

    Wichtig: Es wird NUR auf Way-Mitgliedschaft geprüft, nicht
    auf geometrische Distanz. Es werden auch keine
    Straßengeometrien zurückgegeben (kein "out geom"), wodurch
    die Antwort klein und die Abfrage schnell bleibt.
    """
    return f"""
[out:json][timeout:{OVERPASS_TIMEOUT}];
node["mountain_pass"="yes"]({south},{west},{north},{east})->.passes;
way["highway"~"{road_filter}"](bn.passes)->.roads;
node.passes(w.roads)->.result;
.result out body;
"""


def build_query(osm_query, south, west, north, east):
    return f"""
[out:json][timeout:{OVERPASS_TIMEOUT}];
{osm_query}
    ({south},{west},{north},{east});
out body;
"""


# ============================================================
# OVERPASS REQUEST (pro Tile)
# ============================================================

def query_overpass_tile(poi_type, poi_config, south, west, north, east):

    if poi_type == "mountain_pass":
        query = build_mountain_pass_query(
            south, west, north, east,
            road_filter=poi_config["road_filter"],
        )
    else:
        query = build_query(
            poi_config["query"],
            south, west, north, east,
        )

    data = urllib.parse.urlencode({"data": query}).encode("utf-8")

    for attempt in range(MAX_RETRIES):

        server = OVERPASS_SERVERS[attempt % len(OVERPASS_SERVERS)]

        print(
            f"    Versuch {attempt + 1}/{MAX_RETRIES} "
            f"@ {server}"
        )

        request = urllib.request.Request(
            server,
            data=data,
            headers={"User-Agent": "motorcycle-route-planner/1.0"},
        )

        try:
            # urllib-Timeout deutlich groesser als das
            # Overpass-interne Timeout wählen, damit Overpass
            # selbst zuerst sauber abbricht.
            with urllib.request.urlopen(
                request, timeout=OVERPASS_TIMEOUT + 60
            ) as response:
                raw = response.read()

            osm_data = json.loads(raw.decode("utf-8"))
            elements = osm_data.get("elements", [])

            print(f"    -> {len(elements)} Objekte")

            time.sleep(REQUEST_DELAY)

            return elements

        except urllib.error.HTTPError as e:
            print(f"    HTTP {e.code}: {e.reason}")

            if e.code == 429:
                wait_time = 30 * (attempt + 1)
                print(f"    Rate Limit. Warte {wait_time}s...")
                time.sleep(wait_time)
                continue

            if e.code in (502, 503, 504):
                wait_time = 20 * (attempt + 1)
                print(f"    Server nicht verfuegbar. Warte {wait_time}s...")
                time.sleep(wait_time)
                continue

            raise

        except (urllib.error.URLError, TimeoutError) as e:
            print(f"    Netzwerkfehler: {e}")

            if attempt < MAX_RETRIES - 1:
                wait_time = 20 * (attempt + 1)
                print(f"    Warte {wait_time}s...")
                time.sleep(wait_time)
                continue

            raise

        except Exception as e:
            print(f"    Unerwarteter Fehler: {type(e).__name__}: {e}")

            if attempt < MAX_RETRIES - 1:
                wait_time = 20 * (attempt + 1)
                print(f"    Warte {wait_time}s...")
                time.sleep(wait_time)
                continue

            raise

    raise RuntimeError(f"POI-Typ '{poi_type}' konnte nicht geladen werden.")


def query_overpass(poi_type, poi_config, south, west, north, east):
    """
    Fragt eine Kategorie über alle Tiles hinweg ab und führt
    die Ergebnisse zusammen.
    """
    tiles = generate_tiles(south, west, north, east, poi_config.get("tile_size"))

    print(f"  {len(tiles)} Tile(s) fuer diese Kategorie")

    all_elements = []

    for index, (t_south, t_west, t_north, t_east) in enumerate(tiles, start=1):
        print(
            f"  Tile {index}/{len(tiles)}: "
            f"{t_south:.2f},{t_west:.2f} -> {t_north:.2f},{t_east:.2f}"
        )

        elements = query_overpass_tile(
            poi_type, poi_config, t_south, t_west, t_north, t_east
        )

        all_elements.extend(elements)

    return all_elements


# ============================================================
# OSM DATEN AUFBEREITEN
# ============================================================

def convert_elements(elements):

    places = []
    seen_ids = set()

    for element in elements:

        if element.get("type") != "node":
            continue

        osm_id = element.get("id")

        if osm_id is None or osm_id in seen_ids:
            continue

        seen_ids.add(osm_id)

        tags = element.get("tags", {})

        lat = element.get("lat")
        lon = element.get("lon")

        if lat is None or lon is None:
            continue

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
            "lng": lon,
        }

        if tags.get("name:de"):
            place["name_de"] = tags["name:de"]

        if tags.get("name:en"):
            place["name_en"] = tags["name:en"]

        if tags.get("ele"):
            try:
                place["ele"] = float(
                    str(tags["ele"]).replace(",", ".").replace("m", "").strip()
                )
            except ValueError:
                pass

        if tags.get("wikidata"):
            place["wikidata"] = tags["wikidata"]

        if tags.get("website"):
            place["website"] = tags["website"]

        if tags.get("phone"):
            place["phone"] = tags["phone"]

        if tags.get("opening_hours"):
            place["opening_hours"] = tags["opening_hours"]

        address_fields = {
            "street": "addr:street",
            "housenumber": "addr:housenumber",
            "postcode": "addr:postcode",
            "city": "addr:city",
            "country": "addr:country",
        }

        address = {}

        for output_name, osm_tag in address_fields.items():
            if tags.get(osm_tag):
                address[output_name] = tags[osm_tag]

        if address:
            place["address"] = address

        places.append(place)

    places.sort(key=lambda p: p.get("name", "").lower())

    return places


# ============================================================
# JSON SCHREIBEN
# ============================================================

def write_json(poi_config, places):

    output_file = DATA_DIR / poi_config["output"]

    output = {
        "version": 1,
        "type": poi_config["type"],
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": "OpenStreetMap",
        "bounds": {
            "south": SOUTH,
            "west": WEST,
            "north": NORTH,
            "east": EAST,
        },
        "places": places,
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with output_file.open("w", encoding="utf-8") as file:
        json.dump(output, file, ensure_ascii=False, separators=(",", ":"))

    return output_file


# ============================================================
# HAUPTPROGRAMM
# ============================================================

total_places = 0

for poi_config in POI_TYPES:

    print()
    print()
    print("========================================")
    print(f"STARTE: {poi_config['name']}")
    print("========================================")

    elements = query_overpass(
        poi_config["type"],
        poi_config,
        SOUTH, WEST, NORTH, EAST,
    )

    places = convert_elements(elements)

    output_file = write_json(poi_config, places)

    total_places += len(places)

    print()
    print("----------------------------------------")
    print(f"{poi_config['name']} abgeschlossen")
    print(f"Objekte: {len(places)}")
    print(f"Datei: {output_file}")
    print("----------------------------------------")


# ============================================================
# FERTIG
# ============================================================

print()
print()
print("========================================")
print("OSM POI UPDATE ABGESCHLOSSEN")
print("========================================")
print(f"Kategorien: {len(POI_TYPES)}")
print(f"Gesamtzahl POIs: {total_places}")
print(f"Gebiet: {SOUTH},{WEST} -> {NORTH},{EAST}")
print()
print("Erzeugte Dateien:")

for poi_config in POI_TYPES:
    print(f"  - data/{poi_config['output']}")

print()
print("========================================")
