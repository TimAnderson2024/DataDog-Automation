import os

from env_data import EnvDataFactory, Result
from app_config import AppConfig
from slack_messenger import SlackMessenger

def identify_unique_filemover_jobs(log_results: dict[str, Result]) -> set[str]:
    unique_jobs: dict[str, int] = {}

    for failed_job in log_results.raw:
        print(failed_job['attributes']['attributes']['fm_job']['name'])
        job_name = failed_job['attributes']['attributes']['fm_job']['name']
        unique_jobs[job_name] = unique_jobs.get(job_name, 0) + 1

    return unique_jobs

def run_job(config: AppConfig) -> None:
    all_env_data = EnvDataFactory.from_json_file(config.query_path, config.time_from, config.time_to)

    for env in all_env_data:
        if env.log_results.get('failed_fm_jobs'):
            env.filtered_fm_jobs = identify_unique_filemover_jobs(env.log_results.get('failed_fm_jobs', {}))

    messenger = SlackMessenger(all_env_data, token=os.getenv("SLACK_API_KEY"), channel_id=config.output_channel_id)
    messenger.build_message()
    messenger.send_message()