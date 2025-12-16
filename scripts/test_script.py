#!/usr/bin/env python

import os
from dotenv import load_dotenv

from utils import json_helpers
from utils.query import *

def main():
    load_dotenv()
    
    los_config = json_helpers.get_json_config('config/queries.json')["los"]
    los_queries = los_config["queries"]
    dd_config = get_dd_config(los_config) 
    
    for metric, query in los_queries.items():
        simple_24h_aggregate = get_simple_aggregate(dd_config, query, "now-24h")
        avg_aggregate = get_aggregate_avg(dd_config, query, 2, weekday=True, weekend=False)
        weekday_aggregate = get_filtered_aggregate(dd_config, query, 2, weekday=True, weekend=False)
        weekend_aggregate = get_filtered_aggregate(dd_config, query, 2, weekday=False, weekend=True)
        weekday_breakdown = get_aggregate_breakdown(dd_config, query, 2, weekday=True, weekend=False)
        weekend_breakdown = get_aggregate_breakdown(dd_config, query, 2, weekday=False, weekend=True)

        print(f"Metric: {metric}")
        print(f"  Simple 24h Aggregate: {simple_24h_aggregate}")   
        print(f"  2-week Average Aggregate: {avg_aggregate}")
        print(f"  Weekend 2-week Aggregate: {weekend_aggregate}")
        print(f"  Weekday 2-week Aggregate: {weekday_aggregate}")
        print(f"  Weekday Breakdown: {weekday_breakdown}")
        print(f"  Weekend Breakdown: {weekend_breakdown}")


if __name__ == "__main__":
    main()