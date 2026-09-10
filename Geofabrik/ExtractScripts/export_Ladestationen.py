from poi_export_common import run_export

POI_CONFIG = {
        "name": "Ladestationen",
        "type": "charging_station",
        "output": "charging_stations.json",
        "tag_key": "amenity",
        "tag_values": ["charging_station"],
}

run_export(POI_CONFIG)