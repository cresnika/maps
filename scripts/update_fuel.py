from poi_common import run_poi_update

POI_CONFIG = {
    "name": "Tankstellen",
    "type": "fuel",
    "output": "fuel.json",
    "query": 'nwr["amenity"="fuel"]',
    "tile_size": 2.0,
}

if __name__ == "__main__":
    run_poi_update(POI_CONFIG)