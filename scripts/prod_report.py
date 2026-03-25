#!/usr/bin/env python

import json
import os
from dataclasses import dataclass
from slack_messenger import SlackMessenger
from dotenv import load_dotenv
from jinja2 import Template
from datetime import date
from pathlib import Path
from env_data import EnvDataFactory, LogResult


CONFIG_PATH = Path("config/config.json")

@dataclass
class AppConfig:
    time_from: str
    time_to: str
    query_path: Path
    output_path: Path
    template_path: Path
    output_channel_id: str

def load_config(path: str = "config.json") -> AppConfig:
    with open(path, "r") as f:
        data = json.load(f)

    return AppConfig(
        time_from=data["TIME_FROM"],
        time_to=data["TIME_TO"],
        query_path=Path(data["QUERY_PATH"]),
        output_path=Path(data["OUTPUT_PATH"]),  
        template_path=Path(data["TEMPLATE_PATH"]),
        output_channel_id=data["OUTPUT_CHANNEL_ID"]
    )

def report_builder(config: AppConfig) -> str:
    data = EnvDataFactory.from_json_file(config.query_path, config.time_from, config.time_to)

    for env in data:
        print(json.dumps(env, default=str, indent=2))
    
    with open(config.template_path) as f:
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

    output_path = f"{config.output_path} Business Day Infra Report {date.today()}.md"

    with open(output_path, 'w') as out_f:
        out_f.write(output)
    
    print(output_path)
    return str(output_path), data

def identify_unique_filemover_jobs(log_results: dict[str, LogResult]) -> set[str]:
    unique_jobs: dict[str, int] = {}

    for failed_job in log_results.raw:
        print(failed_job['attributes']['attributes']['fm_job']['name'])
        job_name = failed_job['attributes']['attributes']['fm_job']['name']
        unique_jobs[job_name] = unique_jobs.get(job_name, 0) + 1

    return unique_jobs

def main():
    load_dotenv()
    config = load_config(CONFIG_PATH)

    # report_builder(config)

    all_env_data = EnvDataFactory.from_json_file(config.query_path, config.time_from, config.time_to)
    
    for env in all_env_data:
        if env.log_results.get('failed_fm_jobs'):
            env.filtered_fm_jobs = identify_unique_filemover_jobs(env.log_results.get('failed_fm_jobs', {}))

    messenger = SlackMessenger(all_env_data, token=os.getenv("SLACK_API_KEY"), channel_id=config.output_channel_id)
    messenger.build_message()
    messenger.send_message()

if __name__ == "__main__":
    main()