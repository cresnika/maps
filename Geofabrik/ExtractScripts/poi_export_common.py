import json
import time
from pathlib import Path

import osmium
import osmium.geom

DOWNLOADPATH = Path("../Downloads")
EXTRACTPATH = Path("../../data")

ROAD_TYPES = {
    "motorway",
    "trunk",
    "primary",
    "secondary",
    "tertiary",
    "unclassified",
    "residential",
    "service",
}

AVAILABLE_POI_TYPES = [
    {
        "name": "Gebirgspässe",
        "type": "mountain_pass",
        "output": "mountain_passes.json",
        "tag_key": "mountain_pass",
        "tag_values": ["yes"],
    },
    {
        "name": "Tankstellen",
        "type": "fuel",
        "output": "fuel.json",
        "tag_key": "amenity",
        "tag_values": ["fuel"],
    },
    {
        "name": "Hotels",
        "type": "hotels",
        "output": "hotels.json",
        "tag_key": "tourism",
        "tag_values": ["hotel"],
    },
    {
        "name": "Pensionen",
        "type": "guesthouse",
        "output": "guesthouses.json",
        "tag_key": "tourism",
        "tag_values": [
            "guest_house",
            "hostel",
            "motel",
            "bed_and_breakfast",
            "apartment",
            "chalet",
        ],
    },
    {
        "name": "Essen & Trinken",
        "type": "food",
        "output": "food.json",
        "tag_key": "amenity",
        "tag_values": [
            "restaurant",
            "cafe",
            "fast_food",
            "bar",
            "pub",
            "biergarten",
        ],
    },
    {
        "name": "Campingplätze",
        "type": "campsite",
        "output": "campsites.json",
        "tag_key": "tourism",
        "tag_values": ["camp_site"],
    },
    {
        "name": "Aussichtspunkte",
        "type": "viewpoint",
        "output": "viewpoints.json",
        "tag_key": "tourism",
        "tag_values": ["viewpoint"],
    },
    {
        "name": "Motorradhändler",
        "type": "motorcycle_shop",
        "output": "motorcycle_shops.json",
        "tag_key": "shop",
        "tag_values": ["motorcycle"],
    },
    {
        "name": "Ladestationen",
        "type": "charging_station",
        "output": "charging_stations.json",
        "tag_key": "amenity",
        "tag_values": ["charging_station"],
    },
]

POI_TYPES = [
    {
        "name": "Gebirgspässe",
        "type": "mountain_pass",
        "output": "mountain_passes.json",
        "tag_key": "mountain_pass",
        "tag_values": ["yes"],
    },
    {
        "name": "Tankstellen",
        "type": "fuel",
        "output": "fuel.json",
        "tag_key": "amenity",
        "tag_values": ["fuel"],
    },
    {
        "name": "Hotels",
        "type": "hotels",
        "output": "hotels.json",
        "tag_key": "tourism",
        "tag_values": ["hotel"],
    },
    {
        "name": "Pensionen",
        "type": "guesthouse",
        "output": "guesthouses.json",
        "tag_key": "tourism",
        "tag_values": [
            "guest_house",
            "hostel",
            "motel",
            "bed_and_breakfast",
            "apartment",
            "chalet",
        ],
    },
    {
        "name": "Essen & Trinken",
        "type": "food",
        "output": "food.json",
        "tag_key": "amenity",
        "tag_values": [
            "restaurant",
            "cafe",
            "fast_food",
            "bar",
            "pub",
            "biergarten",
        ],
    },
    {
        "name": "Campingplätze",
        "type": "campsite",
        "output": "campsites.json",
        "tag_key": "tourism",
        "tag_values": ["camp_site"],
    },
]

processed_nodes = 0
last_progress = 0
road_nodes = set()

class RoadNodeCollector(osmium.SimpleHandler):

    def way(self, w):

        highway = w.tags.get("highway")

        if highway not in ROAD_TYPES:
            return

        for node in w.nodes:
            road_nodes.add(node.ref)


class POIHandler(osmium.SimpleHandler):

    def __init__(
        self,
        poi_name,
        tag_key,
        tag_values,
        places,
        seen,
    ):
        super().__init__()

        self.poi_name = poi_name
        self.tag_key = tag_key
        self.tag_values = tag_values
        self.places = places
        self.seen = seen

    def progress(self):

        global processed_nodes
        global last_progress

        processed_nodes += 1

        if processed_nodes - last_progress >= 1_000_000:

            last_progress = processed_nodes

            print(
                f"\r     Bearbeitet: "
                f"{processed_nodes:,} Objekte, "
                f"Treffer bisher: {len(self.places):,}",
                end="",
                flush=True
            )            

    def matches(self, tags):

        value = tags.get(self.tag_key)

        return value in self.tag_values

    def add_place(
        self,
        osm_id,
        osm_type,
        lat,
        lon,
        tags,
    ):

        key = (
            osm_type,
            osm_id,
        )

        if key in self.seen:
            return

        self.seen.add(key)

        place = {
            "id": osm_id,
            "osm_type": osm_type,
            "name": tags.get("name", ""),
            "lat": lat,
            "lng": lon,
        }

        website = (
            tags.get("website")
            or tags.get("contact:website")
            or tags.get("url")
            or tags.get("contact:url")
        )

        if website:
            place["website"] = website
            
        if tags.get("phone"):
            place["phone"] = tags["phone"]

        if tags.get("email"):
            place["email"] = tags["email"]

        if tags.get("opening_hours"):
            place["opening_hours"] = tags["opening_hours"]

        if tags.get("wikidata"):
            place["wikidata"] = tags["wikidata"]
         
        self.places.append(place)

    def node(self, n):

        self.progress()

        if not self.matches(n.tags):
            return

        #
        # Mountain-Pass Spezialfall
        #
        if self.tag_key == "mountain_pass":

            if n.id not in road_nodes:
                return

        self.add_place(
            n.id,
            "node",
            n.location.lat,
            n.location.lon,
            n.tags,
        )

    def way(self, w):

        self.progress()

        if not self.matches(w.tags):
            return

        try:

            count = 0
            sum_lat = 0.0
            sum_lon = 0.0

            for node in w.nodes:

                sum_lat += node.lat
                sum_lon += node.lon
                count += 1

            if count == 0:
                return

            self.add_place(
                w.id,
                "way",
                sum_lat / count,
                sum_lon / count,
                w.tags,
            )

        except Exception:
            pass

    def relation(self, r):

        self.progress()

        if not self.matches(r.tags):
            return

        key = (
            "relation",
            r.id,
        )

        if key in self.seen:
            return

        self.seen.add(key)

        self.places.append({
            "id": r.id,
            "osm_type": "relation",
            "name": r.tags.get("name", ""),
            "lat": None,
            "lng": None,
        })
        
        
def format_duration(seconds):

    seconds = int(seconds)

    hours, remainder = divmod(
        seconds,
        3600
    )

    minutes, seconds = divmod(
        remainder,
        60
    )

    if hours:
        return (
            f"{hours}h "
            f"{minutes:02d}m "
            f"{seconds:02d}s"
        )

    if minutes:
        return (
            f"{minutes}m "
            f"{seconds:02d}s"
        )

    return f"{seconds}s"


def run_export(poi_config):

    files = sorted(DOWNLOADPATH.glob("*.osm.pbf"))

    print(f"Gefundene Dateien: {len(files)}")
    print()

    EXTRACTPATH.mkdir(
        parents=True,
        exist_ok=True,
    )

    overall_start = time.time()

    print()
    print("==================================================")
    print(f"     STARTE: {poi_config['name']}")
    print("==================================================")

    if poi_config["type"] == "mountain_pass":

        print("Sammle Straßenknoten...")

        road_nodes.clear()

        collector = RoadNodeCollector()

        for index, file in enumerate(files, start=1):

            print(
                f"     [{index}/{len(files)}] "
                f"{file.name}"
            )

            collector.apply_file(
                str(file),
                locations=False,
            )

        print(
            f"Straßenknoten gefunden: "
            f"{len(road_nodes):,}"
        )

        print()
        
    places = []
    seen = set()

    handler = POIHandler(
        poi_name=poi_config["name"],
        tag_key=poi_config["tag_key"],
        tag_values=poi_config["tag_values"],
        places=places,
        seen=seen,
    )

    poi_start = time.time()

    for index, file in enumerate(files, start=1):

        print(
            f"[{index}/{len(files)}] "
            f"Verarbeite: {file.name}"
        )

        processed_nodes = 0
        last_progress = 0

        start = time.time()

        handler.apply_file(
            str(file),
            locations=True,
        )

        elapsed = time.time() - start

        print()
        
        print(
            f"Laufzeit: "
            f"{format_duration(elapsed)}"
        )

        print(
            f"     Treffer gesamt: "
            f"{len(places):,}"
        )

        print()

    output_file = (
        EXTRACTPATH
        / poi_config["output"]
    )

    with open(
        output_file,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            {
                "version": 1,
                "type": poi_config["type"],
                "places": places,
            },
            f,
            ensure_ascii=False,
            indent=2
        )

    poi_elapsed = (
        time.time() - poi_start
    )

    print(
        f"{poi_config['name']} fertig"
    )

    print(
        f"POIs: {len(places):,}"
    )

    print(
        f"Datei: {output_file}"
    )

    print(
        f"Laufzeit: {poi_elapsed:.1f}s"
    )

    overall_elapsed = (time.time() - overall_start)

    print("==================================================")
    print("FERTIG")
    print("==================================================")

    print(
        f"Gesamtlaufzeit: "
        f"{format_duration(overall_elapsed)}"
    )