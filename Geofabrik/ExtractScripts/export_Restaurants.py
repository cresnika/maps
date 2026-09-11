from poi_export_common import run_export

POI_CONFIG = {
        "name": "Restaurants",
        "type": "food",
        "output": "food.json",
        "tag_key": "amenity",
        "tag_values": [
            "restaurant",
            "cafe",
            "fast_food",
            "pub",
            "biergarten",
        ],
}

run_export(POI_CONFIG)