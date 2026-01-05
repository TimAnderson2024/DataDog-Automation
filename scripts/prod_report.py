#!/usr/bin/env python

import os
import datetime
from dotenv import load_dotenv
from datadog_api_client import ApiClient, Configuration
from datadog_api_client.v2.api.logs_api import LogsApi
from datadog_api_client.v2.model.logs_aggregate_request import LogsAggregateRequest
from datadog_api_client.v2.model.logs_query_filter import LogsQueryFilter
from datadog_api_client.v2.model.logs_compute import LogsCompute
from datadog_api_client.v2.model.logs_aggregation_function import LogsAggregationFunction
from jinja2 import Template

from utils.json_helpers import load_json_from_file
from utils.query import get_dd_config, get_simple_aggregate

def get_env_data(dd_config: Configuration, queries: dict, timeframe: str) -> dict:
    env_data = {}

    for metric, query in queries.items():
        env_data[metric] = get_simple_aggregate(dd_config, query, timeframe)

    return env_data

def write_report(compiled_data: dict, timeframe: str) -> str:
    print(compiled_data)
    with open('templates/report_template.md') as f:
        template = Template(f.read())

    output = template.render(
        date=datetime.date.today(),
        data=compiled_data
    )

    if timeframe == "now-48h":
        output_path = f"{os.getenv('OUTPUT_PATH')}Weekend Infra Report {datetime.date.today()}.md"
    else:
        output_path = f"{os.getenv('OUTPUT_PATH')}Business Day Infra Report {datetime.date.today()}.md"

    with open(output_path, 'w') as out_f:
        out_f.write(output)
    
    return output_path

def create_report():
    json_config = load_json_from_file('config/queries.json')
    env_data = {}

    if datetime.date.today().weekday() == 0:
        timeframe = "now-48h"
    else:
        timeframe = "now-24h"
  
    for env in json_config.keys():
        env_config, env_queries = json_config[env], json_config[env]["queries"]
        try:
            dd_config = get_dd_config(env_config)
            env_data[env] = get_env_data(dd_config, env_queries, timeframe)
            print(f"Generating report data for {env}... {env_data}")
        except KeyError:
            print(f"Skipping {env} due to missing API keys.")

    out_path = write_report(env_data, timeframe)
    print(f"View report: \n{out_path}")


def main():
    load_dotenv()
    create_report()
    


if __name__ == "__main__":
    main()