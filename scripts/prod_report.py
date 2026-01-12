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
import utils.query as query
from utils.query import get_dd_config, get_simple_aggregate, query_synthetic_test, query_synthetic_uptime

def get_env_data(dd_config: Configuration, queries: dict, synthetics: dict, num_hours: int) -> dict:
    env_data = {}

    if queries is not None:
        for metric, query in queries.items():
            print(f"\tRunning query for {metric}")
            env_data[metric] = get_simple_aggregate(dd_config, query, num_hours)
        print("Query data gathered \n")

    print("Checking synthetic tests...")
    if synthetics is not None: 
        for endpoint, synthetic_id in synthetics.items():
            print(f"Fetching synthetic test results for {endpoint}...")
            if get_synthetic_results(dd_config, synthetic_id, num_hours):
                env_data[endpoint] = "No failures"
            else:
                env_data[endpoint] = "Failure detected!"
    else:
        print(f"No synthetics found, skipping synetic checks...")

    return env_data


def get_synthetic_results(dd_config: Configuration, test_id: str, num_hours:int):
    time_from, time_to = time.time_range_iso_hours_ago(num_hours)

    with open('output/synthetic_output.json', 'w') as f:
        synthetic_results = query_synthetic_test(dd_config, test_id, time.iso_to_unix_milliseconds(time_from), time.iso_to_unix_milliseconds(time_to))
        json_synthetic = json.dumps(synthetic_results, indent=4)
        f.write(json_synthetic)

        failures = 0
        print("Checking synthetic test results...")
        for test_result in synthetic_results:
            if not test_result["result"]["passed"]:
                print(f"SYNTHETIC FAILURE DETECTED:\n{test_result}")
                failures += 1

        if failures == 0:
            print(f"No synthetic test failures detected")
            
        return failures == 0

def write_report(compiled_data: dict, num_hours: int) -> str:
    print(compiled_data)
    with open('templates/report_template.md') as f:
        template = Template(f.read())

    output = template.render(
        date=date.today(),
        data=compiled_data
    )

    if num_hours == 48:
        output_path = f"{os.getenv('OUTPUT_PATH')}Weekend Infra Report {date.today()}.md"
    else:
        output_path = f"{os.getenv('OUTPUT_PATH')}Business Day Infra Report {date.today()}.md"

    with open(output_path, 'w') as out_f:
        out_f.write(output)
    
    return output_path

def create_report():
    json_config = load_json_from_file('config/queries.json')
    env_data = {}

    if date.today().weekday() == 0:
        num_hours = 48
    else:
        num_hours = 24
    print(f"Fetching data for last {num_hours} hours")
  
    for env in json_config.keys():
        env_config= json_config[env]
        env_queries = json_config[env].get("queries")
        env_synthetics = json_config[env].get("synthetic_tests")

        try:
            dd_config = get_dd_config(env_config)
            print(f"Gathering report data for {env} environment")
            env_data[env] = get_env_data(dd_config, env_queries, env_synthetics, num_hours)
            print(f"Report data for {env} environment fetched successfully\n")
                
        except KeyError:
          print(f"Skipping {env} due to missing API keys.")

    out_path = write_report(env_data, num_hours)
    print(f"View report: \n{out_path}")


def main():
    load_dotenv()
    create_report()
    


if __name__ == "__main__":
    main()