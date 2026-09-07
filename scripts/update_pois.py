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

DATA_DIR = Path("data")

OVERPASS_SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

MAX_RETRIES = 5
REQUEST_DELAY = 6
OVERPASS_TIMEOUT = 120


# ============================================================
# REGIONEN
# ============================================================
#
# Statt einer riesigen Bounding-Box ueber halb Europa definieren
# wir mehrere kleinere, sich grob an Laendergrenzen orientierende
# Regionen. Ueberschneidungen sind unproblematisch, Duplikate
# werden beim Zusammenfuehren anhand der OSM-ID entfernt.
#
# ============================================================

REGIONS = [
    {
        "name": "Österreich",
        "south": 46.369542083899, "west": 9.525223464166924, "north": 49.0237861867675, "east": 17.165528039959487,
    },
    # {
    #     "name": "DACH + Alpen",
    #     "south": 45.6, "west": 4.0, "north": 49.9, "east": 17.2,
    # },
    # {
    #     "name": "Frankreich",
    #     "south": 41.3, "west": -5.2, "north": 51.1, "east": 9.6,
    # },
    # {
    #     "name": "Italien (inkl. Sardinien & Sizilien)",
    #     "south": 35.4, "west": 6.6, "north": 47.1, "east": 18.6,
    # },
    # {
    #     "name": "Kroatien & Slowenien",
    #     "south": 42.3, "west": 13.3, "north": 46.9, "east": 19.5,
    # },
    # {
    #     "name": "Spanien (Festland + Balearen)",
    #     "south": 36.0, "west": -9.5, "north": 43.8, "east": 4.4,
    # },
]


# ============================================================
# POI-KATEGORIEN
# ============================================================
#
# Hotels, Restaurants und Tankstellen sind bewusst NICHT mehr
# hier drin - die Datenmenge ueber 4 Regionen hinweg wuerde die
# Laufzeit sprengen (siehe Chat). Diese Kategorien werden
# stattdessen live im Client abgefragt (Viewport + Mindestzoom).
# Tankstellen sind hier gerade nur zum Testen aktiv.
#
# tile_size:
#   Kantenlaenge der Grid-Kacheln in Grad PRO REGION. None =
#   die ganze Region in einem Request.
#
# ============================================================

POI_TYPES = [

    # {
    #     "name": "Mountain Passes",
    #     "type": "mountain_pass",
    #     "output": "mountain_passes.json",
    #     "query": None,
    #     "road_filter": (
    #         '^(motorway|trunk|primary|secondary|tertiary|'
    #         'unclassified|residential|service)$'
    #     ),
    #     "tile_size": None,
    # },
    {
        "name": "Tankstellen",
        "type": "fuel",
        "output": "fuel.json",
        "query": 'nwr["amenity"="fuel"]',
        "tile_size": 2.0,
    },
#    {
#        "name": "Campingplaetze",
#        "type": "campsite",
#        "output": "campsites.json",
#        "query": 'nwr["tourism"="camp_site"]',
#        "tile_size": 3.0,
#    },

#    {
#        "name": "Aussichtspunkte",
#        "type": "viewpoint",
#        "output": "viewpoints.json",
#        "query": 'nwr["tourism"="viewpoint"]',
#        "tile_size": 3.0,
#    },

#    {
#        "name": "Motorradhaendler",
#        "type": "motorcycle_shop",
#        "output": "motorcycle_shops.json",
#        "query": 'nwr["shop"="motorcycle"]',
#        "tile_size": 5.0,
#    },

#    {
#        "name": "Ladestationen",
#        "type": "charging_station",
#        "output": "charging_stations.json",
#        "query": 'nwr["amenity"="charging_station"]',
#        "tile_size": 4.0,
#    }
]


# ============================================================
# START
# ============================================================

print()
print("========================================")
print("OSM POI DATABASE UPDATE")
print("========================================")
print()
print(f"Regionen: {len(REGIONS)}")
for region in REGIONS:
    print(f"  - {region['name']}")
print(f"Kategorien: {len(POI_TYPES)}")
print()


# ============================================================
# TILING
# ============================================================

def generate_tiles(south, west, north, east, tile_size):
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
    Speziallogik nur fuer Mountain Passes: prueft Way-
    Mitgliedschaft statt einfach nur nach einem Tag zu filtern.
    Deshalb eine eigene Funktion statt der generischen
    build_query() - die Overpass-QL sieht strukturell komplett
    anders aus (Sets, bn/w-Filter) als ein normaler Tag-Filter.
    """
    return f"""
[out:json][timeout:{OVERPASS_TIMEOUT}];
node["mountain_pass"="yes"]({south},{west},{north},{east})->.passes;
way["highway"~"{road_filter}"](bn.passes)->.roads;
node.passes(w.roads)->.result;
.result out body;
"""


def build_query(osm_query, south, west, north, east):
    # nwr = node/way/relation. Viele POIs (z.B. Tankstellen,
    # Campingplaetze) werden in OSM als Flaeche statt als
    # einzelner Punkt erfasst - "node" allein wuerde die
    # verpassen. "out center" liefert fuer Flaechen einen
    # Mittelpunkt statt der vollen Geometrie (bleibt leicht).
    return f"""
[out:json][timeout:{OVERPASS_TIMEOUT}];
{osm_query}
    ({south},{west},{north},{east});
out center;
"""


# ============================================================
# OVERPASS REQUEST (ein Tile)
# ============================================================

def query_overpass_tile(poi_type, poi_config, south, west, north, east):

    if poi_type == "mountain_pass":
        query = build_mountain_pass_query(
            south, west, north, east,
            road_filter=poi_config["road_filter"],
        )
    else:
        query = build_query(poi_config["query"], south, west, north, east)

    data = urllib.parse.urlencode({"data": query}).encode("utf-8")

    for attempt in range(MAX_RETRIES):

        server = OVERPASS_SERVERS[attempt % len(OVERPASS_SERVERS)]

        print(f"      Versuch {attempt + 1}/{MAX_RETRIES} @ {server}")

        request = urllib.request.Request(
            server,
            data=data,
            headers={"User-Agent": "motorcycle-route-planner/1.0"},
        )

        start_time = time.time()

        try:
            with urllib.request.urlopen(
                request, timeout=OVERPASS_TIMEOUT + 60
            ) as response:
                raw = response.read()

            elapsed = time.time() - start_time

            osm_data = json.loads(raw.decode("utf-8"))
            elements = osm_data.get("elements", [])

            print(f"      -> {len(elements)} Objekte in {elapsed:.1f}s")

            time.sleep(REQUEST_DELAY)

            return elements

        except urllib.error.HTTPError as e:
            print(f"      HTTP {e.code}: {e.reason}")

            if e.code == 429:
                wait_time = 30 * (attempt + 1)
                print(f"      Rate Limit. Warte {wait_time}s...")
                time.sleep(wait_time)
                continue

            if e.code in (502, 503, 504):
                wait_time = 20 * (attempt + 1)
                print(f"      Server nicht verfuegbar. Warte {wait_time}s...")
                time.sleep(wait_time)
                continue

            raise

        except (urllib.error.URLError, TimeoutError) as e:
            print(f"      Netzwerkfehler: {e}")

            if attempt < MAX_RETRIES - 1:
                wait_time = 20 * (attempt + 1)
                print(f"      Warte {wait_time}s...")
                time.sleep(wait_time)
                continue

            raise

        except Exception as e:
            print(f"      Unerwarteter Fehler: {type(e).__name__}: {e}")

            if attempt < MAX_RETRIES - 1:
                wait_time = 20 * (attempt + 1)
                print(f"      Warte {wait_time}s...")
                time.sleep(wait_time)
                continue

            raise

    raise RuntimeError(f"POI-Typ '{poi_type}' konnte nicht geladen werden.")


def query_overpass_region(poi_type, poi_config, region):
    tiles = generate_tiles(
        region["south"], region["west"], region["north"], region["east"],
        poi_config.get("tile_size"),
    )

    print(f"    {len(tiles)} Tile(s) in Region '{region['name']}'")

    all_elements = []

    for index, (t_south, t_west, t_north, t_east) in enumerate(tiles, start=1):
        print(
            f"    Tile {index}/{len(tiles)}: "
            f"{t_south:.2f},{t_west:.2f} -> {t_north:.2f},{t_east:.2f}"
        )
        elements = query_overpass_tile(
            poi_type, poi_config, t_south, t_west, t_north, t_east
        )
        all_elements.extend(elements)

    return all_elements


def query_overpass_all_regions(poi_type, poi_config):
    all_elements = []

    for region in REGIONS:
        print(f"  Region: {region['name']}")
        elements = query_overpass_region(poi_type, poi_config, region)
        all_elements.extend(elements)

    return all_elements


# ============================================================
# OSM DATEN AUFBEREITEN
# ============================================================

def convert_elements(elements):

    places = []
    seen_keys = set()

    for element in elements:

        element_type = element.get("type")

        if element_type not in ("node", "way", "relation"):
            continue

        osm_id = element.get("id")

        if osm_id is None:
            continue

        # IDs sind nur INNERHALB eines Elementtyps eindeutig -
        # ein Node 12345 und ein Way 12345 koennen beide
        # existieren. Daher (type, id) als Dedup-Schluessel.
        dedup_key = (element_type, osm_id)

        if dedup_key in seen_keys:
            continue

        seen_keys.add(dedup_key)

        tags = element.get("tags", {})

        if element_type == "node":
            lat = element.get("lat")
            lon = element.get("lon")
        else:
            # Way/Relation: "out center" liefert einen
            # Mittelpunkt statt lat/lon direkt am Element.
            center = element.get("center", {})
            lat = center.get("lat")
            lon = center.get("lon")

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
            "osm_type": element_type,
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
        "regions": [
            {
                "name": r["name"],
                "south": r["south"], "west": r["west"],
                "north": r["north"], "east": r["east"],
            }
            for r in REGIONS
        ],
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

    elements = query_overpass_all_regions(poi_config["type"], poi_config)

    places = convert_elements(elements)

    output_file = write_json(poi_config, places)

    total_places += len(places)

    print()
    print("----------------------------------------")
    print(f"{poi_config['name']} abgeschlossen")
    print(f"Objekte (nach Dedup): {len(places)}")
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
print()
print("Erzeugte Dateien:")
for poi_config in POI_TYPES:
    print(f"  - data/{poi_config['output']}")
print()
print("========================================")
