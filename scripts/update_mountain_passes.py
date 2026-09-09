from poi_common import run_poi_update

POI_CONFIG = {
    "name": "Mountain Passes",
    "type": "mountain_pass",
    "output": "mountain_passes.json",
    "query": None,
    "road_filter":
        "^(motorway|trunk|primary|secondary|tertiary|"
        "unclassified|residential|service)$",
    "tile_size": 2.0,
}

if __name__ == "__main__":
    run_poi_update(POI_CONFIG)