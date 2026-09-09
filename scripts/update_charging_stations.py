from poi_common import run_poi_update

POI_CONFIG = {
    "name": "Ladestationen",
    "type": "charging_station",
    "output": "charging_stations.json",
    "query": 'nwr["amenity"="charging_station"]',
    "tile_size": 2.0,
}

if __name__ == "__main__":
    run_poi_update(POI_CONFIG)