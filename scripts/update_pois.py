import json
import time
import sys
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

SCRIPT_START = time.time()


def elapsed_time():
    seconds = int(time.time() - SCRIPT_START)
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours:
        return f"{hours}h {minutes:02d}m {seconds:02d}s"
    if minutes:
        return f"{minutes}m {seconds:02d}s"
    return f"{seconds}s"


def debug(message):
    print(f"[{elapsed_time()}] {message}", flush=True)


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
    {
        "name": "Italien",
         "south": 36.634347031948394, "west": 6.622642225252252, "north": 47.09731041300716, "east": 18.55654119051602,
    },
    {
        "name": "Schweiz",
         "south": 45.81623534018711, "west": 5.950011033798339, "north": 47.80980842423389, "east": 10.496977600927035,
    },
    {
        "name": "Deutschland",
        "south": 47.26371645002933, "west": 5.860528922469316, "north": 55.06055867850519, "east": 15.050592435538157,
    },
    {
        "name": "Frankreich",
        "south": 41.303, "west": -5.142, "north": 51.124, "east": 9.560, 
    },
    {
        "name": "Korsika",
        "south": 41.333, "west": 8.533, "north": 43.027, "east":9.560,
    },
    {
        "name": "Portugal",
        "south": 36.838, "west": -9.526, "north": 42.154, "east": -6.190,
    },
    {
        "name": "Spanien",
        "south": 27.638, "west": -18.161, "north": 43.792, "east": 4.327,
    },
    {
        "name": "Slowenien",
        "south": 45.421, "west": 13.375, "north": 46.877, "east": 16.610,
    },
    {
        "name": "Kroatien",
        "south": 42.392, "west": 13.489, "north": 46.555, "east": 19.448,
    },
    {
        "name": "Balearen",
        "south": 38.640, "west": 1.150, "north": 40.100, "east": 4.330,    
    }
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
    #     "tile_size": 3.0,
    # },
    {
        "name": "Tankstellen",
        "type": "fuel",
        "output": "fuel.json",
        "query": 'nwr[amenity=fuel]',
        "tile_size": 3.0,
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
    debug(
        f"  - {region['name']} "
        f"({region['south']:.3f},{region['west']:.3f} -> "
        f"{region['north']:.3f},{region['east']:.3f})"
    )

debug(f"Kategorien: {len(POI_TYPES)}")
debug("")

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
    debug(
        f"      Overpass Request vorbereitet: "
        f"{south:.3f},{west:.3f} -> {north:.3f},{east:.3f}"
    )
    if poi_type == "mountain_pass":
        query = build_mountain_pass_query(
            south, west, north, east,
            road_filter=poi_config["road_filter"],
        )
    else:
        query = build_query(
            poi_config["query"],
            south, west, north, east
        )

    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    debug(f"      Query-Größe: {len(data) / 1024:.1f} KB")
    for attempt in range(MAX_RETRIES):
        server = OVERPASS_SERVERS[attempt % len(OVERPASS_SERVERS)]
        debug(
            f"      -> Starte Request "
            f"(Versuch {attempt + 1}/{MAX_RETRIES})"
        )
        debug(f"      -> Server: {server}")
        debug(f"      -> Timeout: {OVERPASS_TIMEOUT}s")
        request = urllib.request.Request(
            server,
            data=data,
            headers={"User-Agent": "motorcycle-route-planner/1.0"},
        )

        start_time = time.time()
        try:
            debug("      -> Warte auf Overpass-Antwort...")
            with urllib.request.urlopen(
                request,
                timeout=OVERPASS_TIMEOUT + 60
            ) as response:
                debug(
                    f"      -> HTTP {response.status} "
                    f"{response.reason}"
                )
                debug("      -> Antwort wird gelesen...")
                raw = response.read()
            elapsed = time.time() - start_time
            debug(
                f"      -> Download abgeschlossen: "
                f"{len(raw) / 1024 / 1024:.2f} MB "
                f"in {elapsed:.1f}s"
            )
            debug("      -> JSON wird geparst...")
            osm_data = json.loads(raw.decode("utf-8"))
            elements = osm_data.get("elements", [])
            debug(
                f"      -> {len(elements):,} Objekte "
                f"in {elapsed:.1f}s"
            )
            debug(
                f"      -> Request erfolgreich "
                f"(Gesamtlaufzeit: {elapsed_time()})"
            )
            debug(
                f"      -> Warte {REQUEST_DELAY}s "
                f"vor nächstem Request..."
            )
            time.sleep(REQUEST_DELAY)
            return elements
        except urllib.error.HTTPError as e:
            elapsed = time.time() - start_time
            debug(
                f"      !! HTTP Fehler nach {elapsed:.1f}s: "
                f"{e.code}: {e.reason}"
            )
            if e.code == 429:
                wait_time = 30 * (attempt + 1)
                debug(
                    f"      !! Rate Limit!"
                )
                debug(
                    f"      -> Warte {wait_time}s "
                    f"vor erneutem Versuch..."
                )
                time.sleep(wait_time)
                continue
            if e.code in (502, 503, 504):
                wait_time = 20 * (attempt + 1)
                debug(
                    f"      !! Server nicht verfügbar!"
                )
                debug(
                    f"      -> Warte {wait_time}s "
                    f"vor erneutem Versuch..."
                )
                time.sleep(wait_time)
                continue
            raise
        except (urllib.error.URLError, TimeoutError) as e:
            elapsed = time.time() - start_time
            debug(
                f"      !! Netzwerkfehler nach "
                f"{elapsed:.1f}s: {e}"
            )
            if attempt < MAX_RETRIES - 1:
                wait_time = 20 * (attempt + 1)
                debug(
                    f"      -> Warte {wait_time}s "
                    f"vor erneutem Versuch..."
                )
                time.sleep(wait_time)
                continue
            raise
        except Exception as e:
            elapsed = time.time() - start_time
            debug(
                f"      !! Unerwarteter Fehler nach "
                f"{elapsed:.1f}s"
            )
            debug(
                f"      !! {type(e).__name__}: {e}"
            )
            if attempt < MAX_RETRIES - 1:
                wait_time = 20 * (attempt + 1)
                debug(
                    f"      -> Warte {wait_time}s "
                    f"vor erneutem Versuch..."
                )
                time.sleep(wait_time)
                continue
            raise
    raise RuntimeError(
        f"POI-Typ '{poi_type}' konnte nicht geladen werden."
    )


def query_overpass_region(poi_type, poi_config, region):
    region_start = time.time()
    tiles = generate_tiles(
        region["south"],
        region["west"],
        region["north"],
        region["east"],
        poi_config.get("tile_size"),
    )
    debug(
        f"    Region '{region['name']}': "
        f"{len(tiles)} Tile(s)"
    )
    all_elements = []
    for index, (t_south, t_west, t_north, t_east) in enumerate(
        tiles,
        start=1
    ):
        tile_start = time.time()
        debug(
            f"    ----------------------------------------"
        )
        debug(
            f"    Tile {index}/{len(tiles)} "
            f"({index / len(tiles) * 100:.1f}%)"
        )
        debug(
            f"    Bounding Box: "
            f"{t_south:.3f},{t_west:.3f} -> "
            f"{t_north:.3f},{t_east:.3f}"
        )
        elements = query_overpass_tile(
            poi_type,
            poi_config,
            t_south,
            t_west,
            t_north,
            t_east
        )
        all_elements.extend(elements)
        tile_elapsed = time.time() - tile_start
        debug(
            f"    Tile {index}/{len(tiles)} fertig: "
            f"{len(elements):,} Objekte "
            f"in {tile_elapsed:.1f}s"
        )
        debug(
            f"    Bisher in Region: "
            f"{len(all_elements):,} Objekte"
        )
    region_elapsed = time.time() - region_start
    debug(
        f"    Region '{region['name']}' fertig"
    )
    debug(
        f"    -> {len(all_elements):,} Objekte"
    )
    debug(
        f"    -> Laufzeit: {region_elapsed:.1f}s"
    )
    return all_elements

def query_overpass_all_regions(poi_type, poi_config):
    all_elements = []
    total_regions = len(REGIONS)
    debug(
        f"  Starte {total_regions} Regionen..."
    )
    for region_index, region in enumerate(
        REGIONS,
        start=1
    ):
        debug("")
        debug(
            f"  ========================================"
        )
        debug(
            f"  REGION {region_index}/{total_regions} "
            f"({region_index / total_regions * 100:.1f}%)"
        )
        debug(
            f"  {region['name']}"
        )
        debug(
            f"  ========================================"
        )
        elements = query_overpass_region(
            poi_type,
            poi_config,
            region
        )
        all_elements.extend(elements)
        debug(
            f"  Gesamtfortschritt: "
            f"{region_index}/{total_regions} Regionen"
        )
        debug(
            f"  Gesamtobjekte bisher: "
            f"{len(all_elements):,}"
        )
    debug("")
    debug(
        f"  Alle Regionen abgeschlossen: "
        f"{len(all_elements):,} Rohobjekte"
    )
    return all_elements

# ============================================================
# OSM DATEN AUFBEREITEN
# ============================================================

def convert_elements(elements):

    convert_start = time.time()

    debug(
        f"Starte Datenaufbereitung: "
        f"{len(elements):,} Rohobjekte"
    )

    places = []
    seen_keys = set()

    total = len(elements)

    for index, element in enumerate(elements, start=1):

        # Alle 5.000 Elemente Fortschritt ausgeben
        if index % 5000 == 0 or index == total:

            debug(
                f"  Aufbereitung: "
                f"{index:,}/{total:,} "
                f"({index / total * 100:.1f}%)"
            )

        element_type = element.get("type")

        if element_type not in ("node", "way", "relation"):
            continue

        osm_id = element.get("id")

        if osm_id is None:
            continue

        dedup_key = (element_type, osm_id)

        if dedup_key in seen_keys:
            continue

        seen_keys.add(dedup_key)

        tags = element.get("tags", {})

        if element_type == "node":
            lat = element.get("lat")
            lon = element.get("lon")
        else:
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
                    str(tags["ele"])
                    .replace(",", ".")
                    .replace("m", "")
                    .strip()
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

    debug("Sortiere Ergebnisse...")

    places.sort(
        key=lambda p: p.get("name", "").lower()
    )

    elapsed = time.time() - convert_start

    debug(
        f"Datenaufbereitung abgeschlossen: "
        f"{len(places):,} eindeutige POIs "
        f"in {elapsed:.1f}s"
    )

    debug(
        f"Entfernte Duplikate: "
        f"{len(elements) - len(seen_keys):,}"
    )

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

total_elapsed = time.time() - SCRIPT_START

debug("")
debug("")
debug("========================================")
debug("OSM POI UPDATE ABGESCHLOSSEN")
debug("========================================")
debug(f"Kategorien: {len(POI_TYPES)}")
debug(f"Gesamtzahl POIs: {total_places:,}")
debug(f"Gesamtlaufzeit: {total_elapsed / 60:.1f} Minuten")
debug("")
debug("Erzeugte Dateien:")

for poi_config in POI_TYPES:
    debug(f"  - data/{poi_config['output']}")

debug("")
debug("========================================")
