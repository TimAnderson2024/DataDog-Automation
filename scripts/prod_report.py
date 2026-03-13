#!/usr/bin/env python

import json
from dotenv import load_dotenv
from jinja2 import Template
from datetime import date

from env_data import EnvDataFactory, LogResult

TIME_FROM = "now-48h"
TIME_TO = "now"
QUERY_PATH = "config/queries.json"
TEST_PATH = "output/test_report.txt"
TEMPLATE_PATH = "templates/report_template_v2.md"

def report_builder():
    data = EnvDataFactory.from_json_file(QUERY_PATH, TIME_FROM, TIME_TO)
    
    for env in data:
        print(json.dumps(env, default=str, indent=2))
    
    with open(TEMPLATE_PATH) as f:
        template = Template(f.read())

    for env in data:
        print(env)

        if env.log_results.get('failed_fm_jobs'):
            env.filtered_fm_jobs = identify_unique_filemover_jobs(env.log_results.get('failed_fm_jobs', {}))
            print(env.filtered_fm_jobs)

    output = template.render(
        date=date.today(),
        data=data
    )

    output_path = f"{TEST_PATH} Business Day Infra Report {date.today()}.md"

    with open(output_path, 'w') as out_f:
        out_f.write(output)
    
    print(output_path)
    return output_path

def identify_unique_filemover_jobs(log_results: dict[str, LogResult]) -> set[str]:
    unique_jobs: dict[str, int] = {}

    for failed_job in log_results.raw:
        print(failed_job['attributes']['attributes']['fm_job']['name'])
        job_name = failed_job['attributes']['attributes']['fm_job']['name']
        unique_jobs[job_name] = unique_jobs.get(job_name, 0) + 1

    return unique_jobs

def main():
    load_dotenv()
    report_builder()
    
if __name__ == "__main__":
    main()