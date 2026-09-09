from poi_common import run_poi_update

POI_CONFIG = {
    "name": "Pensionen",
    "type": "guesthouse",
    "output": "guesthouses.json",
    "query": 'nwr["tourism"~"^(guest_house|hostel|motel|bed_and_breakfast|apartment|chalet)$"]',
    "tile_size": 2.0,
}

if __name__ == "__main__":
    run_poi_update(POI_CONFIG)