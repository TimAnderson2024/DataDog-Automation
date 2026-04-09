import logging
import os
import boto3

from jinja2 import Environment

from datetime import date
from string import Template
from env_data import EnvData, EnvData, EnvDataFactory, Result
from app_config import AppConfig
from slack_messenger import SlackMessenger
from external_helpers import get_aws_secrets_helper, send_slack_message

logger = logging.getLogger(__name__)

JINJA_TEMPLATE = """
    {%- for env in data %}
    *[[ env.env ]]*
    {%- if env._errs is defined and env._errs %}
    {%- for err_type, result in env._errs.items() %}
    - *[[ err_type ]]*: [[ result.aggregate ]]
    {%- endfor %}
    {%- endif %}
    {%- if env.event_results is defined and env.event_results %}
    {%- for event, result in env.event_results.items() %}
    - *[[ event ]]*: [[ result.aggregate ]]
    {%- endfor %}
    {%- endif %}
    {%- if env.synthetic_results is defined and env.synthetic_results %}
    {%- for test, result in env.synthetic_results.items() %}
    - Synthetic test on `[[ result.name ]]`: [[ result.failure_count ]] failures in last 24hr
    {%- endfor %}
    {%- endif %}
    {%- if env.filtered_fm_jobs is defined and env.filtered_fm_jobs %}
    *Filemover failures in last 24hr:*
    {%- for failed_job, count in env.filtered_fm_jobs.items() %}
    - `[[ failed_job ]]:` [[ count ]]
    {%- endfor %}
    {%- endif %}
    {% endfor %}
    """

QUERIES = [
  {
    "name": "ULP",
    "API_KEY": "DD_ULP_API_KEY",
    "APP_KEY": "DD_ULP_APP_KEY",
    "queries": {
      "504": {
        "type": "aggregate",
        "query": "env:ulp-prod status:error @http.status_code:504 service:elb",
        "yellow_threshold": 35,
        "red_threshold": 55
      },
      "502": {
        "type": "aggregate",
        "query": "env:ulp-prod status:error @http.status_code:502 service:elb",
        "yellow_threshold": 1,
        "red_threshold": 5
      },
      "503": {
        "type": "aggregate",
        "query": "env:ulp-prod status:error @http.status_code:503 service:elb",
        "red_threshold": 1,
        "manual_threshold": 1
      },
      "oom": {
        "type": "event",
        "query": "env:ulp-prod status:error (OutOfMemoryError OR \"out of memory\" OR OOM)",
        "red_threshold": 1
      },
      "failed_fm_jobs": {
        "type": "log",
        "query": "kube_namespace:(stgwe* OR *ktrs) run_job.sh result for \"job failed\" env:ulp-prod",
        "manual_threshold": 2, 
        "yellow_threshold": 1,
        "red_threshold": 2
      },
      "core.allocore.com": {
        "type": "synthetic",
        "query": "bsi-2qz-vvt",
        "red_threshold": 1
      }
    }
  },
  {
    "name": "CLS",
    "API_KEY": "DD_ULP_API_KEY",
    "APP_KEY": "DD_ULP_APP_KEY",
    "queries": {
      "504": {
        "type": "aggregate",
        "query": "env:cls-prod status:error @http.status_code:504 service:elb",
        "manual_threshold": 1, 
        "yellow_threshold": 2,
        "red_threshold": 5
      },
      "502": {
        "type": "aggregate",
        "query": "env:cls-prod status:error @http.status_code:502 service:elb",
        "yellow_threshold": 2,
        "red_threshold": 5
      },
      "503": {
        "type": "aggregate",
        "query": "env:cls-prod status:error @http.status_code:503 service:elb",
        "red_threshold": 1,
        "manual_threshold": 1
      },
      "oom": {
        "type": "event",
        "query": "env:cls-prod status:error (OutOfMemoryError OR \"out of memory\" OR OOM)",
        "yellow_threshold": 1,
        "red_threshold": 2
      },
      "failed_fm_jobs": {
        "type": "log",
        "query": "kube_namespace:(stgwe* OR *ktrs) run_job.sh result for \"job failed\" env:cls-prod",
        "manual_threshold": 2,
        "yellow_threshold": 1,
        "red_threshold": 2
      }
    }
  },
  {
    "name": "LOS",
    "API_KEY": "DD_LOS_API_KEY",
    "APP_KEY": "DD_LOS_APP_KEY",
    "queries": {
      "504": {
        "type": "aggregate",
        "query": "env:prod status:error @http.status_code:504",
        "manual_threshold": 7, 
        "yellow_threshold": 1,
        "red_threshold": 6
      },
      "502": {
        "type": "aggregate",
        "query": "env:prod status:error @http.status_code:502",
        "yellow_threshold": 2,
        "red_threshold": 8
      },
      "503": {
        "type": "aggregate",
        "query": "env:prod status:error @http.status_code:503",
        "red_threshold": 1,
        "manual_threshold": 1
      },
      "oom": {
        "type": "event",
        "query": "env:prod status:error (OutOfMemoryError OR \"out of memory\" OR OOM)",
        "yellow_threshold": 1,
        "red_threshold": 2
      },
      "failed_fm_jobs": {
        "type": "log",
        "query": "kube_namespace:(stgwe* OR *ktrs) run_job.sh result for \"job failed\" env:los-prod",
        "manual_threshold": 1, 
        "yellow_threshold": 1,
        "red_threshold": 2
      }
    }
  },
  {
    "name": "URIF",
    "API_KEY": "DD_CORE_API_KEY",
    "APP_KEY": "DD_CORE_APP_KEY",
    "queries": {
      "504": {
        "type": "aggregate",
        "query": "env:(urif-prod OR urif-prod-main) status:error @http.status_code:504",
        "red_threshold": 1
      },
      "502": {
        "type": "aggregate",
        "query": "env:(urif-prod OR urif-prod-main) status:error @http.status_code:502",
        "red_threshold": 1
      },
      "503": {
        "type": "aggregate",
        "query": "env:(urif-prod OR urif-prod-main) status:error @http.status_code:503",
        "red_threshold": 1,
        "manual_threshold": 1
      },
      "oom": {
        "type": "event",
        "query": "env:(urif-prod OR urif-prod-main) status:error (OutOfMemoryError OR \"out of memory\" OR OOM)",
        "red_threshold": 1
      },
      "urifinvest": {
        "type": "synthetic",
        "query": "jrd-tg4-3gt",
        "red_threshold": 1
      }
    }
  },
  {
    "name": "USALending",
    "API_KEY": "DD_CORE_API_KEY",
    "APP_KEY": "DD_CORE_APP_KEY",
    "queries": {
      "504": {
        "type": "aggregate",
        "query": "env:(usalending-prod OR usalending-prod-main) status:error @http.status_code:504",
        "red_threshold": 1
      },
      "502": {
        "type": "aggregate",
        "query": "env:(usalending-prod OR usalending-prod-main) status:error @http.status_code:502",
        "red_threshold": 1
      },
      "503": {
        "type": "aggregate",
        "query": "env:(usalending-prod OR usalending-prod-main) status:error @http.status_code:503",
        "red_threshold": 1,
        "manual_threshold": 1
      },
      "oom": {
        "type": "event",
        "query": "env:(usalending-prod OR usalending-prod-main) status:error (OutOfMemoryError OR \"out of memory\" OR OOM)",
        "red_threshold": 1
      },
      "usalending": {
        "type": "synthetic",
        "query": "fnp-uqa-mx7",
        "red_threshold": 1
      }
    }
  },
  {
    "name": "ACE",
    "API_KEY": "DD_ACE_API_KEY",
    "APP_KEY": "DD_ACE_APP_KEY",
    "queries": {
      "504": {
        "type": "aggregate",
        "query": "env:ace-prod status:error @http.status_code:504",
        "red_threshold": 1
      },
      "502": {
        "type": "aggregate",
        "query": "env:ace-prod status:error @http.status_code:502",
        "red_threshold": 1
      },
      "503": {
        "type": "aggregate",
        "query": "env:ace-prod status:error @http.status_code:503",
        "red_threshold": 1,
        "manual_threshold": 1
      },
      "oom": {
        "type": "event",
        "query": "env:ace-prod status:error (OutOfMemoryError OR \"out of memory\" OR OOM)",
        "red_threshold": 1
      }
    }
  }
]

def identify_unique_filemover_jobs(log_results: dict[str, Result]) -> set[str]:
    unique_jobs: dict[str, int] = {}

    for failed_job in log_results.raw:
        if failed_job['attributes'].get('service'):
          job_name = failed_job['attributes']['service']
        else:
          job_name = failed_job['attributes']['attributes']['fm_job']['name']
        unique_jobs[job_name] = unique_jobs.get(job_name, 0) + 1

    return unique_jobs

def build_report(config: AppConfig, all_env_data: list[EnvData]) -> str:
    jinja_env = Environment(variable_start_string='[[', variable_end_string=']]', keep_trailing_newline=True)
    template = jinja_env.from_string(JINJA_TEMPLATE)
    
    output = template.render(
        date=date.today(),
        data=all_env_data
    )

    output_path = f"Business Day Infra Report {date.today()}.md"

    with open(output_path, 'w') as out_f:
        out_f.write(output)
    
    return str(output_path)

def upload_report_to_s3(config: AppConfig, report_path: str) -> None:
    s3_client = boto3.client('s3')
    
    # Extract the filename from the report path
    report_filename = os.path.basename(report_path)
    
    # Construct the S3 key
    s3_key = f"reports/{report_filename}"
    
    # Upload the file
    s3_client.upload_file(report_path, config.s3_bucket, s3_key)
    
    logger.info(f"Report uploaded to S3: s3://{config.s3_bucket}/{s3_key}")

def run_job(config: AppConfig) -> None:
    all_env_data = EnvDataFactory.from_static(QUERIES, config.time_from, config.time_to)

    logger.info("Identifying unique filemover failures...")
    for env in all_env_data:
        if env.log_results.get('failed_fm_jobs') and len(env.log_results['failed_fm_jobs'].raw) > 0:
            env.filtered_fm_jobs = identify_unique_filemover_jobs(env.log_results.get('failed_fm_jobs', {}))
            logger.info(
              "Unique filemover failures identified in %s: count=%d details=%s",
              env.env,
              len(env.filtered_fm_jobs),
              env.filtered_fm_jobs
            )
        else:
            logger.info("No filemover failures found in %s", env.env)

    logger.info("Building report...")
    report_path = build_report(config, all_env_data)
    logger.info(f"Report built successfully at {report_path}. Attempting to upload to S3...")
    # upload_report_to_s3(config, report_path)

    logger.info("Sending Slack message...")
    messenger = SlackMessenger(all_env_data)
    messenger.build_message()
    secret_name = os.getenv("SECRET_NAME")
    region_name = os.getenv("AWS_REGION")
    secrets = get_aws_secrets_helper([secret_name], region_name)
    slack_api_key = secrets["daily-monitoring-us-east-2"].get("SLACK_API_KEY")

    send_slack_message(messenger.message_blocks, config.output_channel_id, slack_api_key)
    logger.info("Slack message sent successfully.")
    logger.info("Job execution completed, shutting down...")