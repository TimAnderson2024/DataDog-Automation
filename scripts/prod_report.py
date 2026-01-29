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
from env_data import EnvDataFactory
import utils.query as q

QUERY_PATH = "config/queries.json"
TEST_PATH = "output/test_report.txt"

def report_builder():
    data = EnvDataFactory.from_json_file(QUERY_PATH, "now-24h", "now")
    
    for env in data:
        print(json.dumps(env, default=str, indent=2))
    
    with open('templates/report_2.md') as f:
        template = Template(f.read())

    for env in data:
        print(env)

    output = template.render(
        date=date.today(),
        data=data
    )

    output_path = f"{TEST_PATH} Business Day Infra Report {date.today()}.md"

    with open(output_path, 'w') as out_f:
        out_f.write(output)
    
    print(output_path)
    return output_path


def main():
    load_dotenv()
    report_builder()
    


if __name__ == "__main__":
    main()