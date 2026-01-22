#!/usr/bin/env python

import json
import argparse
import heapq
import pandas as pd
import sys
import utils.time_utils as time
import utils.query as q
import generate_figures as fig
import numpy as np

from dataclasses import dataclass
from typing import Tuple
from utils.json_helpers import load_json_from_file
from datadog_api_client import Configuration
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime

DATASET_FILEPATH = "./output/heatmap_data.json"

def get_env_data(dd_config: Configuration, queries: dict, days_back: int) -> dict:
    business, weekend = time.get_filtered_date_ranges(days_back)
    env_data = { "one_day_aggregate": {}, "two_week_business_avg": {}, "two_week_weekend_avg" : {} }

    for metric, query in queries.items():
        print(f"Fetching 24h {metric} value...")
        value_24h = q.query_log_count_aggregate(dd_config, query, ("now-24h", "now"))
        print(f"24h value is {value_24h}")
        
        print(f"Fetching business day average for past {days_back} days")
        business_avg = get_aggregate_avg(dd_config, query, business)
        print(f"Business day average is {business_avg}")
        
        print(f"Fetching weekend average for past {days_back} days")
        weekend_avg = get_aggregate_avg(dd_config, query, weekend)
        print(f"Weekend average is {weekend_avg}")

        env_data["one_day_aggregate"][metric] = value_24h
        env_data["two_week_business_avg"][metric] = business_avg
        env_data["two_week_weekend_avg"][metric] = weekend_avg

    return env_data

def build_heatmap_dataset(env_data: dict, aggregate_period: str, error_types: list = ["504", "502", "oom"]) -> pd.DataFrame:
    temp_lists = [] 
    for env in env_data.keys():
        temp_list = []
        for err_type in error_types:
            temp_list.append(env_data[env][aggregate_period][err_type])
            
        temp_lists.append(temp_list)
    
    return np.array(temp_lists)

def get_filtered_aggregates(dd_config, query_string, date_range):
    """
    Return two aggregate counts of the query string, weekday and weekend
    
    :param num_weeks: Number of weeks to gather logs for
    :param is_weekday: Description
    """
    aggregate = 0
    for from_time, to_time in date_range:
        aggregate += q.query_log_count_aggregate(dd_config, query_string, time_range=(from_time, to_time))

    return aggregate

def get_aggregate_avg(dd_config: Configuration, query_string: str, date_range: Tuple[str, str]):
    aggregate = get_filtered_aggregates(dd_config, query_string, date_range)

    return aggregate // len(date_range)

def build_heatmap(data):
    ALPHA = 1 # Pseudo-count value

    print("Building heatmap dataset")
    dataset_24h = build_heatmap_dataset(data, "one_day_aggregate")
    print(dataset_24h)
    dataset_2week_avg = build_heatmap_dataset(data, "two_week_business_avg")
    print(dataset_2week_avg)

    baseline_deviation = np.log10(dataset_24h + ALPHA)
    comparative_deviation = np.log10((dataset_24h + ALPHA) / (dataset_2week_avg + ALPHA))

    print("Generating heatmap...")
    baseline_heatmap = fig.generate_heatmap_baseline(dataset_24h, dataset_2week_avg, baseline_deviation)
    comparative_heatmap = fig.generate_heatmap_comparative(dataset_24h, dataset_2week_avg, comparative_deviation)
    print("Heatmap generated, writing to file...")
    baseline_heatmap.write_html("output/baseline_heatmap.html", include_plotlyjs=True)
    comparative_heatmap.write_html("output/comparative_heatmap.html", include_plotlyjs=True)

def build_kpi_strip(data):
    print("Building indicators")
    dataset_24h = build_heatmap_dataset(data, "one_day_aggregate")
    dataset_2week_avg = build_heatmap_dataset(data, "two_week_business_avg")
    percent_change = (dataset_24h - dataset_2week_avg) / dataset_2week_avg * 100
    test_indicator = fig.generate_indicator(dataset_24h[0, 0], percent_change[0, 0])
    test_indicator.write_html("output/test_indicator.html", include_plotlyjs=True)

def build_figures(data):
    build_heatmap(data)
    build_kpi_strip(data)    


def fetch_data():
    json_config = load_json_from_file("config/queries.json")
    
    env_data = { }
    for env in json_config.keys():
        env_config = json_config[env]
        env_queries = json_config[env].get("queries")
        env_synthetics = json_config[env].get("synthetic_tests")
        env_fm = json_config[env].get("filemover")

        print(f"Gathering report data for {env} environment")
        if env_queries:
            dd_config = q.get_dd_config(env_config)
            env_data = env_data | { env: get_env_data(dd_config, env_queries, days_back=14) }

    print("Gathered data:")
    for key, val in env_data.items():
        print(key, val)
    
    with open(DATASET_FILEPATH, "w") as f:
        json.dump(env_data, f)
    
    return env_data

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--saved", action="store_true", help="Use saved dataset instead of fetching fresh data")
    args = parser.parse_args()

    if args.saved:
        with open(DATASET_FILEPATH, "r") as f:
            env_data = json.load(f)
    else:
        env_data = fetch_data()
    
    return env_data

def main():
    load_dotenv()
    env_data = parse_args()
    build_figures(env_data)
    

if __name__ == "__main__":
    main()

