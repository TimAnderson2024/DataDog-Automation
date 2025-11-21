import os
import json
from dotenv import load_dotenv
from datadog_api_client import ApiClient, Configuration
from datadog_api_client.v2.api.logs_api import LogsApi
from datadog_api_client.v2.model.logs_aggregate_request import LogsAggregateRequest
from datadog_api_client.v2.model.logs_query_filter import LogsQueryFilter
from datadog_api_client.v2.model.logs_compute import LogsCompute
from datadog_api_client.v2.model.logs_aggregation_function import LogsAggregationFunction
from datetime import datetime
from jinja2 import Template

def get_aggregate(config: Configuration, query_string: str):
    with ApiClient(config) as api_client:
        api_instance = LogsApi(api_client)
        response = api_instance.aggregate_logs(
            body=LogsAggregateRequest(
                filter=LogsQueryFilter(
                    query=query_string,
                    _from="now-24h",
                    to="now"
                ),
                compute=[
                    LogsCompute(
                        aggregation=LogsAggregationFunction.COUNT
                    )
                ]
            )
        )
        
        if response.data.buckets and len(response.data.buckets) > 0:
            return response.data.buckets[0].computes.get('c0', 0)
        return 0

def get_config(api_key: str, app_key: str):
    ddconfig = Configuration()
    ddconfig.server_variables["site"] = os.getenv("DD_SITE")
    ddconfig.api_key["apiKeyAuth"] = api_key
    ddconfig.api_key["appKeyAuth"] = app_key

    return ddconfig

def run_queries():
    with open('queries.json') as f:
        queries_json = json.load(f)

    metrics_dict = {}
    for env in queries_json["environments"]:
        # Get the correct configuration for the environment
        api_key = os.getenv(env.get("API_KEY"))
        app_key = os.getenv(env.get("APP_KEY"))
        env_config = get_config(api_key=api_key, app_key=app_key)
        
        # Run each query and store results
        for metric, query_string in env["queries"].items():
            metrics_dict[metric] = int(get_aggregate(env_config, query_string))
    
    with open('report_template.md') as f:
        template = Template(f.read())

    output = template.render(
        date=datetime.today().date(),
        sba_ulp_504=metrics_dict.get("sba_ulp_504", "None"),
        sba_ulp_502=metrics_dict.get("sba_ulp_502", "None"),
        sba_ulp_oom=metrics_dict.get("sba_ulp_oom", "None"),
        cls_prod_504=metrics_dict.get("sba_cls_504", "None"),
        cls_prod_502=metrics_dict.get("sba_cls_502", "None"),
        cls_prod_oom=metrics_dict.get("sba_cls_oom", "None"),
        filemover_failed=metrics_dict.get("filemover_failed", "None"),
        los_504=metrics_dict.get("los_502", "None"),
        los_502=metrics_dict.get("los_504", "None"),
        osc_synthetic=metrics_dict.get("osc_synthetic", "No Failures"),
        osc_failed_backend="",
        osc_p95=""
    )
    output_path = f"{os.getenv('OUTPUT_FILE')} {datetime.today().date()}.md"
    print(output_path)
    with open(output_path, 'w') as out_f:
        out_f.write(output)


def main():
    load_dotenv()
    run_queries()

if __name__ == "__main__":
    main()