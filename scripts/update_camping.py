from poi_common import run_poi_update

POI_CONFIG = {
    "name": "Campingplaetze",
    "type": "campsite",
    "output": "campsites.json",
    "query": 'nwr["tourism"="camp_site"]',
    "tile_size": 2.0,
}

if __name__ == "__main__":
    run_poi_update(POI_CONFIG)
