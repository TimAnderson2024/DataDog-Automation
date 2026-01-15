#!/usr/bin/env python

import pandas as pd
import utils.time_utils as time
import utils.query as q
from utils.json_helpers import load_json_from_file
from datadog_api_client import Configuration
from dotenv import load_dotenv
from generate_figures import generate_heatmap

class Data_Point:
    def __init__(self, err_type: str, value: int):
        self.err_type = err_type
        self.value = value
    
    def __repr__(self):
        return f"Data_Point(err={self.err_type}, value={self.value})"

    def __str__(self):
        return f"{self.err_type}: {self.value}"

def get_env_data(dd_config: Configuration, queries: dict) -> dict:
    env_data = { "one_day_aggregate": {}, "two_week_business_avg": {}, "two_week_weekend_avg" : {} }

    for metric, query in queries.items():
        value_24h = q.query_log_count_aggregate(dd_config, query, time_from="24", time_to="now")
        weekday_avg, weekend_avg = get_daily_aggregate_avg(dd_config, query, weeks_back=2)

        env_data["one_day_aggregate"][metric] = value_24h
        env_data["two_week_business_avg"][metric] = weekday_avg
        env_data["two_week_weekend_avg"][metric] = weekend_avg

    return env_data

def build_heatmap_dataset(env_data: dict, aggregate_period: str, error_types: list = ["504", "502", "oom"]) -> pd.DataFrame:
    temp_lists = [] 
    for env in env_data.keys():
        temp_list = []
        for err_type in error_types:
            temp_list.append(env_data[env][aggregate_period][err_type])
            
        temp_lists.append(temp_list)
    
    return pd.DataFrame(temp_lists)

def get_filtered_aggregates(dd_config, query_string, num_weeks):
    """
    Return two aggregate counts of the query string, weekday and weekend
    
    :param num_weeks: Number of weeks to gather logs for
    :param is_weekday: Description
    """
    weekday_ranges = time.get_filtered_date_ranges(weeks_back=num_weeks, weekday=True, weekend=False)
    weekend_ranges = time.get_filtered_date_ranges(weeks_back=num_weeks, weekday=False, weekend=True)

    weekday_aggregate = 0
    for from_time, to_time in weekday_ranges:
        weekday_aggregate += q.query_log_count_aggregate(dd_config, query_string, time_range=(from_time, to_time))
    
    weekend_aggregate = 0
    for from_time, to_time in weekend_ranges:
        weekend_aggregate += q.query_log_count_aggregate(dd_config, query_string, time_range=(from_time, to_time))

    return weekday_aggregate, weekend_aggregate

def get_daily_aggregate_avg(dd_config: Configuration, query_string: str, weeks_back: int):
    weekday_aggregate, weekend_aggregate = get_filtered_aggregates(dd_config, query_string=query_string, num_weeks=weeks_back)

    avg_weekday = weekday_aggregate // (weeks_back * 5)
    avg_weekend = weekend_aggregate // (weeks_back * 2)

    return avg_weekday, avg_weekend

def main():
    load_dotenv()
    json_config = load_json_from_file("config/queries.json")
    
    env_data = { }
    for env in json_config.keys():
        env_config = json_config[env]
        env_queries = json_config[env].get("queries")
        env_synthetics = json_config[env].get("synthetic_tests")
        env_fm = json_config[env].get("filemover")

        try:
            dd_config = q.get_dd_config(env_config)
            env_data = env_data | { env: get_env_data(dd_config, env_queries) }
        except KeyError:
            print(f"Skipping {env} due to missing API keys.")
    print(env_data)
    dataset_24h = build_heatmap_dataset(env_data, "24h")
    dataset_2week_avg = build_heatmap_dataset(env_data, "2week_avg")
    pct_diff = (dataset_24h - dataset_2week_avg) / dataset_2week_avg * 100

    heatmap = generate_heatmap(dataset_24h, dataset_2week_avg, pct_diff)
    heatmap.show()

if __name__ == "__main__":
    main()

