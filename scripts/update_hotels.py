from poi_common import run_poi_update

POI_CONFIG = {
    "name": "Hotels",
    "type": "hotels",
    "output": "hotels.json",
    "query": 'nwr["tourism"="hotel"]',
    "tile_size": 2.0,
}

if __name__ == "__main__":
    run_poi_update(POI_CONFIG)