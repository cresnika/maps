from poi_export_common import run_export

POI_CONFIG = {
        "name": "Aussichtspunkte",
        "type": "viewpoint",
        "output": "viewpoints.json",
        "tag_key": "tourism",
        "tag_values": ["viewpoint"],
}

run_export(POI_CONFIG)