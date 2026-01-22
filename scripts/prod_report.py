#!/usr/bin/env python

import os
import json
from pprint import pprint
from dotenv import load_dotenv
from datadog_api_client import Configuration
from jinja2 import Template
from datetime import date

import utils.time_utils as time
from utils.json_helpers import load_json_from_file
import utils.query as q

def get_env_data(dd_config: Configuration, queries: dict, synthetics: dict, fm: dict, time_range: tuple[int, int]) -> dict:
    env_data = {}

    if queries is not None:
        for metric, query in queries.items():
            print(f"\tRunning query for {metric}")
            env_data[metric] = q.query_log_count_aggregate(dd_config=dd_config, query_string=query, time_range=time_range)
        print("Query data gathered")

    if synthetics is not None: 
        print("Checking synthetic tests...")

        for endpoint, synthetic_id in synthetics.items():
            print(f"Fetching synthetic test results for {endpoint}...")
            if get_synthetic_results(dd_config, synthetic_id, time_range):
                env_data[endpoint] = "No failures"
            else:
                env_data[endpoint] = "Failure detected!"
    else:
        print(f"No synthetics found, skipping synthetic checks...")
    
    if fm is not None:
        print("Checking for failed FM jobs...")
        fm_results = get_fm_results(dd_config, fm, time_range)
        env_data["fm_failures"] = fm_results

        if env_data["fm_failures"]["num_distinct_failures"] > 0:
            print("Found failed fm jobs:")
            
            for job_name, job_attributes in env_data["fm_failures"]["jobs"].items():
                print(f"\t {job_name}")
                if job_attributes.get("recent_success"):
                    print("\t\tBut succeeded on most recent attempt!")
                else:
                    print("\t\tMore recent success not found!!!")

    else:
        print(f"No FM queries found, skipping FM checks...")



    return env_data

def get_synthetic_results(dd_config: Configuration, test_id: str, time_range: tuple[int, int]):
    with open('output/synthetic_output.json', 'w') as f:
        synthetic_results = q.query_synthetic_test(dd_config, test_id, time_range)
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

def get_fm_results(dd_config: Configuration, queries: dict, time_range: tuple[int, int]):
    print(queries["get_all_failed"])
    data = q.query_logs(dd_config, queries["get_all_failed"], time_range, False)
    failed_jobs = {"jobs": dict(), "num_distinct_failures": 0, "num_total_failures": 0}
    print(data)

    # Strip search query for failed jobs
    for job in data:
        service = job["attributes"]["service"]
        

        try:
            name = job["attributes"]["attributes"]["fm_job"]["name"]        
        except:
            print("Log attributes not properly formatted: attributes.attributes.fm_job.name does not exist. Using tags.app instead...")
            for tag in job["attributes"]["tags"]:   
                tag_values = tag.split(":")
                if tag_values[0] == "fm_job_name":
                    name = tag_values[1]
                    break

        timestamp = job["attributes"]["timestamp"]

        if not failed_jobs.get("jobs").get(name, None):
            failed_jobs["jobs"][name] = {"count": 1, "service": service, "timestamp": timestamp}
        else:
            failed_jobs["jobs"][name]["count"] = failed_jobs["jobs"][name]["count"] + 1
            failed_jobs["jobs"][name]["timestamp"] = max(timestamp, failed_jobs["jobs"][name]["timestamp"])
    failed_jobs["num_distinct_failures"] = len(failed_jobs["jobs"].items()) 
    failed_jobs["num_total_failures"] = len(data)

    # Check if a newer run succeeded
    for job_name, job_attributes in failed_jobs["jobs"].items():
        print(job_name)
        success_query = queries["get_success"].format(service=job_attributes["service"])
        print(success_query)

        # Grab newest success and check against failure timestamp
        latest_successes = q.query_logs(dd_config, success_query, time_range=["now-24h", "now"], keep_tags=False)
        if len(latest_successes) > 0:
            latest_sucess = latest_successes[0]

            if latest_sucess["attributes"]["timestamp"] > job_attributes["timestamp"]:
                print("More recent success found...")
                job_attributes["recent_success"] = True

    return failed_jobs


def write_report(compiled_data: dict, num_hours: int) -> str:
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

def prod_report():
    json_config = load_json_from_file('config/queries.json')
    env_data = {}

    if date.today().weekday() == 0:
        num_hours = 48
    else:
        num_hours = 24
    print(f"Fetching data for last {num_hours} hours")

    time_range = time.normalize_time(f"now-{num_hours}h", "now") 
    for env in json_config.keys():
        env_config= json_config[env]
        env_queries = json_config[env].get("queries")
        env_synthetics = json_config[env].get("synthetic_tests")
        env_fm = json_config[env].get("filemover")

        dd_config = q.get_dd_config(env_config)
        print(f"Gathering report data for {env} environment")
        env_data[env] = get_env_data(dd_config, env_queries, env_synthetics, env_fm, time_range)
        print(f"Report data for {env} environment fetched successfully\n")
            
    pprint(env_data)
    out_path = write_report(env_data, num_hours)
    print(f"View report: \n{out_path}")


def main():
    load_dotenv()
    prod_report()
    


if __name__ == "__main__":
    main()