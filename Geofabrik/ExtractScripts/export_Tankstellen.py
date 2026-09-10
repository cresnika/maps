from poi_export_common import run_export

POI_CONFIG = {
    "name": "Tankstellen",
    "type": "fuel",
    "output": "fuel.json",
    "tag_key": "amenity",
    "tag_values": [
        "fuel",
    ],
}

run_export(POI_CONFIG)