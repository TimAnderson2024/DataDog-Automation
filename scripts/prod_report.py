#!/usr/bin/env python

import os
import datetime
import json
from dotenv import load_dotenv
from datadog_api_client import ApiClient, Configuration
from datadog_api_client.v2.api.logs_api import LogsApi
from datadog_api_client.v2.model.logs_aggregate_request import LogsAggregateRequest
from datadog_api_client.v2.model.logs_query_filter import LogsQueryFilter
from datadog_api_client.v2.model.logs_compute import LogsCompute
from datadog_api_client.v2.model.logs_aggregation_function import LogsAggregationFunction
from jinja2 import Template
from datetime import datetime, timezone, date

import utils.time_utils as time
from utils.json_helpers import load_json_from_file
from utils.query import get_dd_config, get_simple_aggregate, query_synthetic_test, query_synthetic_uptime

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
        date=date.today(),
        data=compiled_data
    )

    if timeframe == "now-48h":
        output_path = f"{os.getenv('OUTPUT_PATH')}Weekend Infra Report {date.today()}.md"
    else:
        output_path = f"{os.getenv('OUTPUT_PATH')}Business Day Infra Report {date.today()}.md"

    with open(output_path, 'w') as out_f:
        out_f.write(output)
    
    return output_path

def get_synthetics(dd_config: Configuration, test_id: str):
    time_from, time_to = time.time_range_iso_hours_ago(24)
    print(time_from, time_to)

    with open('output/synthetic_output.json', 'w') as f:
        synthetic_results = query_synthetic_test(dd_config, test_id, time.iso_to_unix_milliseconds(time_from), time.iso_to_unix_milliseconds(time_to))
        json_synthetic = json.dumps(synthetic_results, indent=4)
        # f.write(json_synthetic)

        # print("from_ts:", time_from, datetime.fromtimestamp(time_from, tz=timezone.utc))
        # print("to_ts:", time_to, datetime.fromtimestamp(time_to, tz=timezone.utc))
        # print("duration:", time_to - time_from)

        synthetic_uptime = query_synthetic_uptime(dd_config, test_id, time.iso_to_unix_seconds(time_from), time.iso_to_unix_seconds(time_to))
        json_uptime = json.dumps(synthetic_uptime, indent=4)
        f.write("UPTIME METRICS:\n")
        f.write(json_uptime)

def create_report():
    json_config = load_json_from_file('config/queries.json')
    env_data = {}

    if date.today().weekday() == 0:
        timeframe = "now-48h"
    else:
        timeframe = "now-24h"
  
    for env in json_config.keys():
        env_config, env_queries = json_config[env], json_config[env]["queries"]

        try:
            dd_config = get_dd_config(env_config)
            env_data[env] = get_env_data(dd_config, env_queries, timeframe)
            if env == "ulp":
                get_synthetics(dd_config, "bsi-2qz-vvt")
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