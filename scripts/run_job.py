from datetime import date
import os
import boto3

from jinja2 import Template

from env_data import EnvData, EnvData, EnvDataFactory, Result
from app_config import AppConfig
from slack_messenger import SlackMessenger

def identify_unique_filemover_jobs(log_results: dict[str, Result]) -> set[str]:
    unique_jobs: dict[str, int] = {}

    for failed_job in log_results.raw:
        print(failed_job['attributes']['attributes']['fm_job']['name'])
        job_name = failed_job['attributes']['attributes']['fm_job']['name']
        unique_jobs[job_name] = unique_jobs.get(job_name, 0) + 1

    return unique_jobs

def build_report(config: AppConfig, all_env_data: list[EnvData]) -> str:
    with open(config.template_path) as f:
        template = Template(f.read())

    output = template.render(
        date=date.today(),
        data=all_env_data
    )

    output_path = config.output_path / f"Business Day Infra Report {date.today()}.md"

    with open(output_path, 'w') as out_f:
        out_f.write(output)
    
    print(f"Report generated at: {output_path}")
    return str(output_path)

def upload_report_to_s3(config: AppConfig, report_path: str) -> None:
    s3_client = boto3.client('s3')
    
    # Extract the filename from the report path
    report_filename = os.path.basename(report_path)
    
    # Construct the S3 key
    s3_key = f"{config.s3_key_prefix}{report_filename}"
    
    # Upload the file
    s3_client.upload_file(report_path, config.s3_bucket, s3_key)
    
    print(f"Report uploaded to S3: s3://{config.s3_bucket}/{s3_key}")

def run_job(config: AppConfig) -> None:
    all_env_data = EnvDataFactory.from_json_file(config.query_path, config.time_from, config.time_to)

    for env in all_env_data:
        if env.log_results.get('failed_fm_jobs'):
            env.filtered_fm_jobs = identify_unique_filemover_jobs(env.log_results.get('failed_fm_jobs', {}))
    
    report_path = build_report(config, all_env_data)
    upload_report_to_s3(config, report_path)
    messenger = SlackMessenger(all_env_data, token=os.getenv("SLACK_API_KEY"), channel_id=config.output_channel_id)
    messenger.build_message()
    messenger.send_message()