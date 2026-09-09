from poi_common import run_poi_update

POI_CONFIG = {
    "name": "Motorradhändler",
    "type": "motorcycle_shop",
    "output": "motorcycle_shops.json",
    "query": 'nwr["shop"="motorcycle"]',
    "tile_size": 2.0,
}

if __name__ == "__main__":
    run_poi_update(POI_CONFIG)