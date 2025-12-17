#!/usr/bin/env python

import os
from dotenv import load_dotenv

from utils import json_helpers
from utils.query import *

POD_NAME = "ulp-backend-7bfc5cfd9d-4mx55"
TIME_PERIOD_HOURS = 1
ATTRIBUTES_TO_KEEP = ["message", "timestamp", "status"]

def get_pod_logs(config: Configuration, env: str, pod_name: str, time_from: str, time_to: str):
    query_string = f"pod_name:{pod_name}"
    logs = query_logs(config, query_string, time_from, time_to)
    return logs

def remove_tags_from_logs(logs: list) -> list:
    for entry in logs:
        attributes = entry.get('attributes', {})
        if 'tags' in attributes:
            attributes = attributes.to_dict()
            del attributes['tags']
            entry['attributes'] = attributes

    return logs

def write_json_to_file(data: list, filepath: str):
    import json
    with open(filepath, 'w') as f:
        for entry in data:
            json.dump(entry.to_dict(), f, indent=4)


def build_pod_log_report(logs: list, filepath: str):
    with open(filepath, 'w') as f:
        cleaned_entry = {}
        for entry in logs: 
            for attribute in ATTRIBUTES_TO_KEEP:
                cleaned_entry[attribute] = entry['attributes'].get(attribute, None)
            f.write(f"{cleaned_entry['timestamp']} - {cleaned_entry['status']} - {cleaned_entry['message']}\n")



def main():
    load_dotenv()
    config = json_helpers.get_json_config('config/queries.json')["ulp"]
    dd_config = get_dd_config(config) 
    
    time_to = datetime.now()
    time_from = time_to - timedelta(hours=TIME_PERIOD_HOURS)
    time_to = time_to.isoformat()
    time_from = time_from.isoformat()
    
    print(f"Fetching logs for pod {POD_NAME} from {time_from} to {time_to}...")
    logs = get_pod_logs(dd_config, "ulp", POD_NAME, time_from, time_to)
    print(f"{len(logs)} log entries retrieved.")
    write_json_to_file(logs, "output/pod_logs.json")
    print(f"Wrote {len(logs)} log entries for {POD_NAME} to output/pod_logs.json")


    # logs = remove_tags_from_logs(logs)
    build_pod_log_report(logs, "output/pod_log_report.txt")


if __name__ == "__main__":
    main()