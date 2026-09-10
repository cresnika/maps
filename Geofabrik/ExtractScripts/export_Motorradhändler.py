from poi_export_common import run_export

POI_CONFIG = {
        "name": "Motorradhändler",
        "type": "motorcycle_shop",
        "output": "motorcycle_shops.json",
        "tag_key": "shop",
        "tag_values": ["motorcycle"],
}

run_export(POI_CONFIG)