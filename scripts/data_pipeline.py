#!/usr/bin/env python

import pandas as pd
from datadog_api_client import Configuration
from dotenv import load_dotenv
from utils.json_helpers import load_json_from_file
from utils.query import get_dd_config, get_simple_aggregate, get_aggregate_avg
from generate_figures import generate_heatmap

class Data_Point:
    def __init__(self, err_type: str, value: int):
        self.err_type = err_type
        self.value = value
    
    def __repr__(self):
        return f"Data_Point(err={self.err_type}, value={self.value})"

    def __str__(self):
        return f"{self.err_type}: {self.value}"

def get_env_data(dd_config: Configuration, env: str, queries: dict) -> dict:
    env_data = { "24h": {}, "2week_avg": {}}

    for metric, query in queries.items():
        value_24h = get_simple_aggregate(dd_config, query, time_from="now-24h")
        value_2week_avg = get_aggregate_avg(dd_config, query, weeks_back=2, weekday=True, weekend=False)

        env_data["24h"][metric] = value_24h
        env_data["2week_avg"][metric] = value_2week_avg

    return env_data

def build_heatmap_dataset(env_data: dict, aggregate_period: str, error_types: list = ["504", "502", "oom"]) -> pd.DataFrame:
    temp_lists = [] 
    for env in env_data.keys():
        temp_list = []
        for err_type in error_types:
            temp_list.append(env_data[env][aggregate_period][err_type])
            
        temp_lists.append(temp_list)
    
    return pd.DataFrame(temp_lists)

def main():
    load_dotenv()
    json_config = load_json_from_file("config/queries.json")
    
    env_data = { }
    for env in json_config.keys():
        env_config, env_queries = json_config[env], json_config[env]["queries"]
        try:
            dd_config = get_dd_config(env_config)
            env_data = env_data | { env: get_env_data(dd_config, env, env_queries) }
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

