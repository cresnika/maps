from poi_export_common import run_export

POI_CONFIG = {
        "name": "Gebirgspässe",
        "type": "mountain_pass",
        "output": "mountain_passes.json",
        "tag_key": "mountain_pass",
        "tag_values": ["yes"],
}

run_export(POI_CONFIG)