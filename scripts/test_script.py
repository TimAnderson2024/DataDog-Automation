#!/usr/bin/env python

import os
from dotenv import load_dotenv

from utils import json_helpers
from utils.query import get_dd_config, get_average, get_aggregate_count

def main():
    load_dotenv()
    
    los_config = json_helpers.get_json_config('config/queries.json')["los"]
    los_queries = los_config["queries"]
    dd_config = get_dd_config(los_config) 
    
    for metric, query in los_queries.items():
        print(f"Fetching two week average for {metric}...")
        count = get_aggregate_count(dd_config, query, "now-14d")
        print(f"Two week total {metric} count: {count}")
        avg = get_average(dd_config, query, "now-14d")
        print(f"Two week {metric} average: {avg}")


if __name__ == "__main__":
    main()