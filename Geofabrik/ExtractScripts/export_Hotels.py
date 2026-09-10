from poi_export_common import run_export

POI_CONFIG = {
        "name": "Hotels",
        "type": "hotels",
        "output": "hotels.json",
        "tag_key": "tourism",
        "tag_values": ["hotel"],
}

run_export(POI_CONFIG)