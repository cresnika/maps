import hashlib
import json
import subprocess
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
TILE_CACHE_DIR = DATA_DIR / ".tile_cache"

OVERPASS_SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

MAX_RETRIES = 5
REQUEST_DELAY = 6
OVERPASS_TIMEOUT = 120
TILE_SIZE = 2.0

SCRIPT_START = time.time()


# ============================================================
# LOGGING
# ============================================================

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

REGIONS = [
    # {
    #     "name": "Vorarlberg",
    #     "south": 46.840862,
    #     "west": 9.530749,
    #     "north": 47.596101,
    #     "east": 10.237173,
    # }
    {
        "name": "Österreich",
        "south": 46.369542083899,
        "west": 9.525223464166924,
        "north": 49.0237861867675,
        "east": 17.165528039959487,
    },
    {
        "name": "Italien",
        "south": 36.634347031948394,
        "west": 6.622642225252252,
        "north": 47.09731041300716,
        "east": 18.55654119051602,
    },
    {
        "name": "Schweiz",
        "south": 45.81623534018711,
        "west": 5.950011033798339,
        "north": 47.80980842423389,
        "east": 10.496977600927035,
    },
    {
        "name": "Deutschland",
        "south": 47.26371645002933,
        "west": 5.860528922469316,
        "north": 55.06055867850519,
        "east": 15.050592435538157,
    },
    {
        "name": "Frankreich",
        "south": 41.303,
        "west": -5.142,
        "north": 51.124,
        "east": 9.560,
    },
    {
        "name": "Korsika",
        "south": 41.333,
        "west": 8.533,
        "north": 43.027,
        "east": 9.560,
    },
    {
        "name": "Portugal",
        "south": 36.838,
        "west": -9.526,
        "north": 42.154,
        "east": -6.190,
    },
    {
        "name": "Spanien",
        "south": 27.638,
        "west": -18.161,
        "north": 43.792,
        "east": 4.327,
    },
    {
        "name": "Slowenien",
        "south": 45.421,
        "west": 13.375,
        "north": 46.877,
        "east": 16.610,
    },
    {
        "name": "Kroatien",
        "south": 42.392,
        "west": 13.489,
        "north": 46.555,
        "east": 19.448,
    },
    {
        "name": "Balearen",
        "south": 38.640,
        "west": 1.150,
        "north": 40.100,
        "east": 4.330,
    },
    {
        "name": "Ungarn",
        "south": 45.737,
        "west": 16.113,
        "north": 48.585,
        "east": 22.897,
    },
    {
        "name": "Kroatien",
        "south": 42.392,
        "west": 13.489,
        "north": 46.555,
        "east": 19.448,
    },
    {
        "name": "Polen",
        "south": 49.002,
        "west": 14.123,
        "north": 54.836,
        "east": 24.146,
    },
    {
        "name": "Tschechien",
        "south": 48.551,
        "west": 12.091,
        "north": 51.055,
        "east": 18.859,
    },
    {
        "name": "Slowakei",
        "south": 47.732,
        "west": 16.833,
        "north": 49.613,
        "east": 22.565,
    },    
]


def get_combined_region_bounds(regions):
    """
    Ermittelt die gemeinsame Bounding-Box aller Regionen.
    Dadurch werden überlappende Regionen nicht mehrfach abgefragt.
    """

    south = min(region["south"] for region in regions)
    west = min(region["west"] for region in regions)
    north = max(region["north"] for region in regions)
    east = max(region["east"] for region in regions)

    return south, west, north, east


# ============================================================
# POI-KATEGORIEN
# ============================================================

POI_TYPES = [
    # {
    #     "name": "Mountain Passes",
    #     "type": "mountain_pass",
    #     "output": "mountain_passes.json",
    #     "query": None,
    #     "road_filter": (
    #         "^(motorway|trunk|primary|secondary|tertiary|"
    #         "unclassified|residential|service)$"
    #     ),
    #     "tile_size": TILE_SIZE,
    # },
    # {
    #     "name": "Tankstellen",
    #     "type": "fuel",
    #     "output": "fuel.json",
    #     "query": 'nwr["amenity"="fuel"]',
    #     "tile_size": TILE_SIZE,
    # },
    {
        "name": "Hotels",
        "type": "hotels",
        "output": "hotels.json",
        "query": 'nwr["tourism"="hotel"]',
        "tile_size": TILE_SIZE,
    },
    {
        "name": "Pensionen",
        "type": "guesthouse",
        "output": "guesthouses.json",
        "query": 'nwr["tourism"~"^(guest_house|hostel|motel|bed_and_breakfast|apartment|chalet)$"]',
        "tile_size": TILE_SIZE,
    },

    # {
    #     "name": "Campingplaetze",
    #     "type": "campsite",
    #     "output": "campsites.json",
    #     "query": 'nwr["tourism"="camp_site"]',
    #     "tile_size": TILE_SIZE,
    # },

    # {
    #     "name": "Aussichtspunkte",
    #     "type": "viewpoint",
    #     "output": "viewpoints.json",
    #     "query": 'nwr["tourism"="viewpoint"]',
    #     "tile_size": TILE_SIZE,
    # },

    # {
    #     "name": "Motorradhaendler",
    #     "type": "motorcycle_shop",
    #     "output": "motorcycle_shops.json",
    #     "query": 'nwr["shop"="motorcycle"]',
    #     "tile_size": TILE_SIZE,
    # },

    # {
    #     "name": "Ladestationen",
    #     "type": "charging_station",
    #     "output": "charging_stations.json",
    #     "query": 'nwr["amenity"="charging_station"]',
    #     "tile_size": TILE_SIZE,
    # },
]


# ============================================================
# GIT
# ============================================================

def git_run(args, check=True):
    result = subprocess.run(
        ["git", *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.stdout.strip():
        debug(f"Git stdout: {result.stdout.strip()}")
    if result.stderr.strip():
        debug(f"Git stderr: {result.stderr.strip()}")
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode,
            result.args,
            output=result.stdout,
            stderr=result.stderr,
        )
    return result
    
def commit_and_push(path, commit_message):
    """
    Commit + Push für eine einzelne Datei.
    """

    debug(f"Git: add {path}")

    git_run(["add", str(path)])

    result = git_run(
        ["diff", "--cached", "--quiet"],
        check=False,
    )

    if result.returncode == 0:
        debug("Git: Keine Änderungen vorhanden.")
        return False

    debug(f"Git: Commit '{commit_message}'")

    git_run(
        [
            "commit",
            "-m",
            commit_message,
        ]
    )

    debug("Git: Push wird gestartet...")

    git_run(["push"])

    debug("Git: Push erfolgreich.")

    return True


def commit_file(output_file, poi_name):
    debug("")
    debug("========================================")
    debug(f"GIT COMMIT: {output_file}")
    debug("========================================")

    commit_and_push(
        output_file,
        f"Update {poi_name} data",
    )


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

            tiles.append(
                (
                    lat,
                    lon,
                    lat_end,
                    lon_end,
                )
            )

            lon = lon_end

        lat = lat_end

    return tiles


# ============================================================
# TILE CACHE
# ============================================================

def get_cache_key(poi_type, poi_config):
    """
    Erzeugt einen eindeutigen Cache-Key.

    Wenn sich Query, Regionen oder Tile-Größe ändern,
    wird automatisch ein neuer Cache verwendet.
    """

    cache_definition = {
        "poi_type": poi_type,
        "query": poi_config.get("query"),
        "road_filter": poi_config.get("road_filter"),
        "tile_size": poi_config.get("tile_size"),
        "regions": REGIONS,
    }

    raw = json.dumps(
        cache_definition,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(raw).hexdigest()[:16]


def get_poi_cache_dir(poi_type, poi_config):
    cache_key = get_cache_key(
        poi_type,
        poi_config,
    )

    cache_dir = (
        TILE_CACHE_DIR
        / poi_type
        / cache_key
    )

    cache_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    return cache_dir


def get_tile_cache_file(
    cache_dir,
    tile_index,
    tile,
):
    south, west, north, east = tile

    tile_key = (
        f"{south:.6f}_"
        f"{west:.6f}_"
        f"{north:.6f}_"
        f"{east:.6f}"
    )

    safe_key = (
        tile_key
        .replace("-", "m")
        .replace(".", "_")
    )

    return cache_dir / (
        f"tile_{tile_index:04d}_{safe_key}.json"
    )


def load_cached_tile(cache_file):
    if not cache_file.exists():
        return None

    try:
        with cache_file.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        if not isinstance(data, list):
            debug(
                f"      !! Ungültiger Tile-Cache: "
                f"{cache_file}"
            )
            return None

        return data

    except Exception as e:
        debug(
            f"      !! Tile-Cache konnte nicht "
            f"gelesen werden: {e}"
        )
        return None


def save_tile_cache(cache_file, elements):
    temp_file = cache_file.with_suffix(
        ".tmp"
    )

    with temp_file.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            elements,
            file,
            ensure_ascii=False,
            separators=(",", ":"),
        )

    temp_file.replace(cache_file)


# ============================================================
# OVERPASS QUERY BUILDER
# ============================================================

def build_mountain_pass_query(
    south,
    west,
    north,
    east,
    road_filter,
):
    """
    Speziallogik für Mountain Passes.
    """

    return f"""
[out:json][timeout:{OVERPASS_TIMEOUT}];
node["mountain_pass"="yes"]({south},{west},{north},{east})->.passes;
way["highway"~"{road_filter}"](bn.passes)->.roads;
node.passes(w.roads)->.result;
.result out body;
"""


def build_query(
    osm_query,
    south,
    west,
    north,
    east,
):
    return f"""
[out:json][timeout:{OVERPASS_TIMEOUT}];
{osm_query}
    ({south},{west},{north},{east});
out center;
"""


# ============================================================
# OVERPASS REQUEST
# ============================================================

def query_overpass_tile(
    poi_type,
    poi_config,
    south,
    west,
    north,
    east,
):
    debug(
        "      Overpass Request vorbereitet: "
        f"{south:.3f},{west:.3f} -> "
        f"{north:.3f},{east:.3f}"
    )

    if poi_type == "mountain_pass":
        query = build_mountain_pass_query(
            south,
            west,
            north,
            east,
            road_filter=poi_config["road_filter"],
        )
    else:
        query = build_query(
            poi_config["query"],
            south,
            west,
            north,
            east,
        )

    data = urllib.parse.urlencode(
        {"data": query}
    ).encode("utf-8")

    debug(
        f"      Query-Größe: "
        f"{len(data) / 1024:.1f} KB"
    )

    last_error = None

    for attempt in range(MAX_RETRIES):
        server = OVERPASS_SERVERS[
            attempt % len(OVERPASS_SERVERS)
        ]

        debug(
            f"      -> Starte Request "
            f"(Versuch {attempt + 1}/{MAX_RETRIES})"
        )

        debug(
            f"      -> Server: {server}"
        )

        debug(
            f"      -> Timeout: "
            f"{OVERPASS_TIMEOUT}s"
        )

        request = urllib.request.Request(
            server,
            data=data,
            headers={
                "User-Agent":
                    "motorcycle-route-planner/1.0"
            },
        )

        start_time = time.time()

        try:
            debug(
                "      -> Warte auf "
                "Overpass-Antwort..."
            )

            with urllib.request.urlopen(
                request,
                timeout=OVERPASS_TIMEOUT + 60,
            ) as response:

                debug(
                    f"      -> HTTP "
                    f"{response.status} "
                    f"{response.reason}"
                )

                debug(
                    "      -> Antwort wird gelesen..."
                )

                raw = response.read()

            elapsed = time.time() - start_time

            debug(
                "      -> Download abgeschlossen: "
                f"{len(raw) / 1024 / 1024:.2f} MB "
                f"in {elapsed:.1f}s"
            )

            debug(
                "      -> JSON wird geparst..."
            )

            osm_data = json.loads(
                raw.decode("utf-8")
            )

            elements = osm_data.get(
                "elements",
                [],
            )

            debug(
                f"      -> {len(elements):,} Objekte "
                f"in {elapsed:.1f}s"
            )

            debug(
                "      -> Request erfolgreich "
                f"(Gesamtlaufzeit: {elapsed_time()})"
            )

            debug(
                f"      -> Warte {REQUEST_DELAY}s "
                "vor nächstem Request..."
            )

            time.sleep(REQUEST_DELAY)

            return elements

        except urllib.error.HTTPError as e:
            elapsed = time.time() - start_time

            last_error = e

            debug(
                f"      !! HTTP Fehler nach "
                f"{elapsed:.1f}s: "
                f"{e.code}: {e.reason}"
            )

            if e.code == 429:
                wait_time = 30 * (attempt + 1)

                debug(
                    "      !! Rate Limit!"
                )

                debug(
                    f"      -> Warte {wait_time}s "
                    "vor erneutem Versuch..."
                )

                time.sleep(wait_time)
                continue

            if e.code in (
                502,
                503,
                504,
            ):
                wait_time = 20 * (
                    attempt + 1
                )

                debug(
                    "      !! Server nicht verfügbar!"
                )

                debug(
                    f"      -> Warte {wait_time}s "
                    "vor erneutem Versuch..."
                )

                time.sleep(wait_time)
                continue

            raise

        except (
            urllib.error.URLError,
            TimeoutError,
        ) as e:

            elapsed = time.time() - start_time

            last_error = e

            debug(
                "      !! Netzwerkfehler nach "
                f"{elapsed:.1f}s: {e}"
            )

            if attempt < MAX_RETRIES - 1:
                wait_time = 20 * (
                    attempt + 1
                )

                debug(
                    f"      -> Warte {wait_time}s "
                    "vor erneutem Versuch..."
                )

                time.sleep(wait_time)

                continue

            break

        except Exception as e:
            elapsed = time.time() - start_time

            last_error = e

            debug(
                "      !! Unerwarteter Fehler nach "
                f"{elapsed:.1f}s"
            )

            debug(
                f"      !! {type(e).__name__}: {e}"
            )

            if attempt < MAX_RETRIES - 1:
                wait_time = 20 * (
                    attempt + 1
                )

                debug(
                    f"      -> Warte {wait_time}s "
                    "vor erneutem Versuch..."
                )

                time.sleep(wait_time)

                continue

            break

    raise RuntimeError(
        f"Tile konnte nach {MAX_RETRIES} "
        f"Versuchen nicht geladen werden: "
        f"{last_error}"
    )


# ============================================================
# GESAMTREGION + TILES
# ============================================================

def query_overpass_all_regions(
    poi_type,
    poi_config,
):
    all_elements = []
    failed_tiles = []

    south, west, north, east = (
        get_combined_region_bounds(
            REGIONS
        )
    )

    debug("")
    debug("========================================")
    debug("GESAMTREGION")
    debug("========================================")

    debug(
        "Gesamt-Bounding-Box: "
        f"{south:.4f},{west:.4f} -> "
        f"{north:.4f},{east:.4f}"
    )

    tile_size = poi_config.get(
        "tile_size"
    )

    tiles = generate_tiles(
        south,
        west,
        north,
        east,
        tile_size,
    )

    debug(
        f"Tile-Größe: {tile_size}°"
    )

    debug(
        f"Gesamtzahl Tiles: {len(tiles)}"
    )

    cache_dir = get_poi_cache_dir(
        poi_type,
        poi_config,
    )

    debug(
        f"Tile-Cache: {cache_dir}"
    )

    debug("")

    total_tiles = len(tiles)
    cached_tiles = 0
    requested_tiles = 0

    for index, tile in enumerate(
        tiles,
        start=1,
    ):
        (
            t_south,
            t_west,
            t_north,
            t_east,
        ) = tile

        tile_start = time.time()

        percent = (
            index / total_tiles * 100
        )

        cache_file = get_tile_cache_file(
            cache_dir,
            index,
            tile,
        )

        debug("========================================")
        debug(
            f"TILE {index}/{total_tiles} "
            f"({percent:.1f}%)"
        )
        debug("========================================")

        debug(
            "BBOX: "
            f"{t_south:.4f},{t_west:.4f} -> "
            f"{t_north:.4f},{t_east:.4f}"
        )

        # ----------------------------------------------------
        # CACHE PRÜFEN
        # ----------------------------------------------------

        cached_elements = load_cached_tile(
            cache_file
        )

        if cached_elements is not None:
            cached_tiles += 1

            all_elements.extend(
                cached_elements
            )

            tile_elapsed = (
                time.time() - tile_start
            )

            debug(
                f"Tile {index}/{total_tiles} "
                "bereits vorhanden -> SKIP"
            )

            debug(
                f"  Cache-Objekte: "
                f"{len(cached_elements):,}"
            )

            debug(
                f"  Gesamtobjekte: "
                f"{len(all_elements):,}"
            )

            debug(
                f"  Cache-Laufzeit: "
                f"{tile_elapsed:.1f}s"
            )

            continue

        # ----------------------------------------------------
        # TILE ABFRAGEN
        # ----------------------------------------------------

        requested_tiles += 1

        try:
            elements = query_overpass_tile(
                poi_type,
                poi_config,
                t_south,
                t_west,
                t_north,
                t_east,
            )

        except Exception as e:
            failed_tiles.append(
                {
                    "index": index,
                    "tile": tile,
                    "error": str(e),
                }
            )

            debug("")
            debug(
                f"!! TILE {index}/{total_tiles} "
                "ENDGÜLTIG FEHLGESCHLAGEN"
            )

            debug(
                f"!! Fehler: {e}"
            )

            debug(
                "!! Tile wird NICHT als erfolgreich "
                "gespeichert."
            )

            debug(
                "!! Es wird beim nächsten Lauf "
                "erneut versucht."
            )

            continue

        # ----------------------------------------------------
        # ERFOLGREICHES TILE SPEICHERN
        # ----------------------------------------------------

        save_tile_cache(
            cache_file,
            elements,
        )

        debug(
            f"      Tile-Cache gespeichert: "
            f"{cache_file}"
        )

        all_elements.extend(elements)

        tile_elapsed = (
            time.time() - tile_start
        )

        debug(
            f"Tile {index}/{total_tiles} "
            "abgeschlossen"
        )

        debug(
            f"  Objekte dieses Tiles: "
            f"{len(elements):,}"
        )

        debug(
            f"  Objekte insgesamt: "
            f"{len(all_elements):,}"
        )

        debug(
            f"  Tile-Laufzeit: "
            f"{tile_elapsed:.1f}s"
        )

        debug(
            f"  Gesamtfortschritt: "
            f"{percent:.1f}%"
        )

        # ----------------------------------------------------
        # TILE-CACHE PERSISTENT INS REPOSITORY PUSHEN
        # ----------------------------------------------------

        try:
            debug(
                "      Git: Erfolgreiches Tile "
                "wird persistent gespeichert..."
            )

            commit_and_push(
                cache_file,
                (
                    f"Checkpoint "
                    f"{poi_config['name']} "
                    f"Tile {index}/{total_tiles}"
                ),
            )

        except Exception as e:
            debug(
                "      !! Git-Push des Tile-"
                f"Checkpoints fehlgeschlagen: {e}"
            )

            raise

    debug("")
    debug("========================================")
    debug("GESAMTREGION ABGESCHLOSSEN")
    debug("========================================")

    debug(
        f"Tiles insgesamt: {total_tiles}"
    )

    debug(
        f"Tiles aus Cache: {cached_tiles}"
    )

    debug(
        f"Tiles neu abgefragt: {requested_tiles}"
    )

    debug(
        f"Tiles fehlgeschlagen: "
        f"{len(failed_tiles)}"
    )

    debug(
        f"Rohobjekte erfolgreich: "
        f"{len(all_elements):,}"
    )

    if failed_tiles:
        debug("")
        debug(
            "Fehlgeschlagene Tiles:"
        )

        for failed in failed_tiles:
            index = failed["index"]
            tile = failed["tile"]

            debug(
                f"  Tile {index}: "
                f"{tile[0]:.4f},{tile[1]:.4f} -> "
                f"{tile[2]:.4f},{tile[3]:.4f}"
            )

    return all_elements, failed_tiles


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

    for index, element in enumerate(
        elements,
        start=1,
    ):
        if (
            index % 5000 == 0
            or index == total
        ):
            if total:
                debug(
                    "  Aufbereitung: "
                    f"{index:,}/{total:,} "
                    f"({index / total * 100:.1f}%)"
                )

        element_type = element.get(
            "type"
        )

        if element_type not in (
            "node",
            "way",
            "relation",
        ):
            continue

        osm_id = element.get("id")

        if osm_id is None:
            continue

        dedup_key = (
            element_type,
            osm_id,
        )

        if dedup_key in seen_keys:
            continue

        seen_keys.add(dedup_key)

        tags = element.get(
            "tags",
            {},
        )

        if element_type == "node":
            lat = element.get("lat")
            lon = element.get("lon")
        else:
            center = element.get(
                "center",
                {},
            )

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
            place["name_de"] = (
                tags["name:de"]
            )

        if tags.get("name:en"):
            place["name_en"] = (
                tags["name:en"]
            )

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
            place["wikidata"] = (
                tags["wikidata"]
            )

        if tags.get("website"):
            place["website"] = (
                tags["website"]
            )

        if tags.get("phone"):
            place["phone"] = (
                tags["phone"]
            )

        if tags.get("opening_hours"):
            place["opening_hours"] = (
                tags["opening_hours"]
            )

        address_fields = {
            "street": "addr:street",
            "housenumber": "addr:housenumber",
            "postcode": "addr:postcode",
            "city": "addr:city",
            "country": "addr:country",
        }

        address = {}

        for (
            output_name,
            osm_tag,
        ) in address_fields.items():

            if tags.get(osm_tag):
                address[output_name] = (
                    tags[osm_tag]
                )

        if address:
            place["address"] = address

        places.append(place)

    debug(
        "Sortiere Ergebnisse..."
    )

    places.sort(
        key=lambda p: p.get(
            "name",
            "",
        ).lower()
    )

    elapsed = (
        time.time() - convert_start
    )

    debug(
        "Datenaufbereitung abgeschlossen: "
        f"{len(places):,} eindeutige POIs "
        f"in {elapsed:.1f}s"
    )

    debug(
        "Entfernte Duplikate: "
        f"{len(elements) - len(seen_keys):,}"
    )

    return places


# ============================================================
# JSON SCHREIBEN
# ============================================================

def write_json(
    poi_config,
    places,
    failed_tiles,
):
    output_file = (
        DATA_DIR
        / poi_config["output"]
    )

    output = {
        "version": 1,
        "type": poi_config["type"],
        "generatedAt": (
            datetime.now(
                timezone.utc
            ).isoformat()
        ),
        "source": "OpenStreetMap",
        "complete": not bool(
            failed_tiles
        ),
        "failedTiles": len(
            failed_tiles
        ),
        "regions": [
            {
                "name": r["name"],
                "south": r["south"],
                "west": r["west"],
                "north": r["north"],
                "east": r["east"],
            }
            for r in REGIONS
        ],
        "places": places,
    }

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp_file = output_file.with_suffix(
        ".tmp"
    )

    with temp_file.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            output,
            file,
            ensure_ascii=False,
            separators=(",", ":"),
        )

    temp_file.replace(output_file)

    return output_file


# ============================================================
# START
# ============================================================

print()
print("========================================")
print("OSM POI DATABASE UPDATE")
print("========================================")
print()

print(
    f"Regionen: {len(REGIONS)}"
)

for region in REGIONS:
    debug(
        f"  - {region['name']} "
        f"({region['south']:.3f},"
        f"{region['west']:.3f} -> "
        f"{region['north']:.3f},"
        f"{region['east']:.3f})"
    )

debug(
    f"Kategorien: {len(POI_TYPES)}"
)

debug(
    f"Tile-Größe: {TILE_SIZE}°"
)

debug("")


# ============================================================
# HAUPTPROGRAMM
# ============================================================

total_places = 0

for poi_config in POI_TYPES:

    print()
    print()
    print("========================================")
    print(
        f"STARTE: {poi_config['name']}"
    )
    print("========================================")

    poi_start = time.time()

    elements, failed_tiles = (
        query_overpass_all_regions(
            poi_config["type"],
            poi_config,
        )
    )

    places = convert_elements(
        elements
    )

    output_file = write_json(
        poi_config,
        places,
        failed_tiles,
    )

    debug(
        f"JSON geschrieben: {output_file}"
    )

    total_places += len(places)

    # --------------------------------------------------------
    # JSON COMMIT + PUSH
    # --------------------------------------------------------

    commit_file(
        output_file,
        poi_config["name"],
    )

    poi_elapsed = (
        time.time() - poi_start
    )

    print()
    print("----------------------------------------")
    print(
        f"{poi_config['name']} abgeschlossen"
    )
    print(
        f"POIs: {len(places):,}"
    )
    print(
        f"Datei: {output_file}"
    )
    print(
        f"Fehlgeschlagene Tiles: "
        f"{len(failed_tiles)}"
    )
    print(
        f"Status: "
        f"{'VOLLSTÄNDIG' if not failed_tiles else 'TEILWEISE'}"
    )
    print(
        f"Laufzeit: "
        f"{poi_elapsed / 60:.1f} Minuten"
    )
    print("----------------------------------------")


# ============================================================
# FERTIG
# ============================================================

total_elapsed = (
    time.time() - SCRIPT_START
)

debug("")
debug("")
debug("========================================")
debug("OSM POI UPDATE ABGESCHLOSSEN")
debug("========================================")
debug(
    f"Kategorien: {len(POI_TYPES)}"
)
debug(
    f"Gesamtzahl POIs: "
    f"{total_places:,}"
)
debug(
    f"Gesamtlaufzeit: "
    f"{total_elapsed / 60:.1f} Minuten"
)
debug("")
debug("Erzeugte Dateien:")

for poi_config in POI_TYPES:
    debug(
        f"  - data/{poi_config['output']}"
    )

debug("")
debug("========================================")
