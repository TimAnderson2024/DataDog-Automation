#!/usr/bin/env python

import os
from dotenv import load_dotenv

from utils import json_helpers
from utils.time_utils import time_range_iso_hours_ago
from utils.query import *
from utils.json_helpers import write_json_to_file

TEST_QUERY = "avg:kubernetes.cpu.usage.total{pod_name:ulp-backend-5d8dc6cb8f-r5kvh},avg:kubernetes.cpu.limits{pod_name:ulp-backend-5d8dc6cb8f-r5kvh}"

def fig_test():
    los_config = json_helpers.load_json_from_file('config/queries.json')["los"]
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

def log_test():
    config = json_helpers.load_json_from_file('config/queries.json')["ulp"]
    dd_config = get_dd_config(config) 
    time_to = datetime.now()
    time_from = time_to - timedelta(weeks=1)
    time_to = time_to.isoformat()
    time_from = time_from.isoformat()

    query_logs(dd_config, "pod_name:ulp-backend-58c9bb59c7-6l2qm", time_from, time_to)


def main():
    load_dotenv()
    config = json_helpers.load_json_from_file('config/queries.json')["ulp"]
    dd_config = get_v1_dd_config(config)
    time_range = time_range_iso_hours_ago(1)

    metric_data = query_metric(dd_config, TEST_QUERY, time_range[0], time_range[1])
    print(len(metric_data))
    write_json_to_file(metric_data, "output/test_metric_data.json")

    avg_cpu_sum = 0
    core_sum = 0
    for data_point in metric_data[0]['pointlist']:
        print(int(data_point[1]) * 10e-9)
        avg_cpu_sum += int(data_point[1]) * 10e-10

    for data_point in metric_data[1]['pointlist']:
        core_sum += int(data_point[1])
    
    avg_cpu = (avg_cpu_sum / len(metric_data[0]['pointlist'])) 
    core_avg = core_sum / len(metric_data[1]['pointlist'])
    avg_utilization = (avg_cpu / core_avg) * 100
    print(f"Average CPU: {avg_cpu}, Average Cores: {core_avg}, Average Utilization: {avg_utilization}%")

if __name__ == "__main__":
    main()