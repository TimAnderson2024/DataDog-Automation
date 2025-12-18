#!/usr/bin/env python

import os
from dotenv import load_dotenv
from datadog_api_client import ApiClient, Configuration
from datadog_api_client.v2.api.logs_api import LogsApi
from datadog_api_client.v2.model.logs_aggregate_request import LogsAggregateRequest
from datadog_api_client.v2.model.logs_query_filter import LogsQueryFilter
from datadog_api_client.v2.model.logs_compute import LogsCompute
from datadog_api_client.v2.model.logs_aggregation_function import LogsAggregationFunction
from datetime import datetime
from jinja2 import Template

from utils.json_helpers import load_json_from_file
from utils.query import get_dd_config, get_simple_aggregate

def get_env_data(dd_config: Configuration, queries: dict) -> dict:
    env_data = {}
    for metric, query in queries.items():
        env_data[metric] = get_simple_aggregate(dd_config, query, "now-24h")

    return env_data

def write_report(compiled_data: dict) -> str:
    with open('templates/report_template.md') as f:
        template = Template(f.read())

    output = template.render(
        date=datetime.today().date(),
        data=compiled_data
    )

    output_path = f"{os.getenv('OUTPUT_PATH')}Infra Report {datetime.today().date()}.md"
    with open(output_path, 'w') as out_f:
        out_f.write(output)
    
    return output_path

def create_report():
    json_config = load_json_from_file('config/queries.json')
    env_data = {}

    for env in json_config.keys():
        env_config, env_queries = json_config[env], json_config[env]["queries"]
        try:
            dd_config = get_dd_config(env_config)
            env_data = env_data | get_env_data(dd_config, env_queries)
        except KeyError:
            print(f"Skipping {env} due to missing API keys.")

    out_path = write_report(env_data)
    print(f"View report: \n{out_path}")


def main():
    load_dotenv()
    create_report()
    


if __name__ == "__main__":
    main()