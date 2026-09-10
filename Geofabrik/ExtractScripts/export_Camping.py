from poi_export_common import run_export

POI_CONFIG = {
    "name": "Campingplätze",
    "type": "campsite",
    "output": "campsites.json",
    "tag_key": "tourism",
    "tag_values": ["camp_site"],
}

run_export(POI_CONFIG)