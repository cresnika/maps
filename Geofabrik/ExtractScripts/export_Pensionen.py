from poi_export_common import run_export

POI_CONFIG = {
        "name": "Pensionen",
        "type": "guesthouse",
        "output": "guesthouses.json",
        "tag_key": "tourism",
        "tag_values": [
            "guest_house",
            "hostel",
            "motel",
            "bed_and_breakfast",
            "apartment",
            "chalet",
        ],
}

run_export(POI_CONFIG)