import os
import json
from dotenv import load_dotenv
from datadog_api_client import ApiClient, Configuration
from datadog_api_client.v2.api.logs_api import LogsApi
from datadog_api_client.v2.model.logs_aggregate_request import LogsAggregateRequest
from datadog_api_client.v2.model.logs_query_filter import LogsQueryFilter
from datadog_api_client.v2.model.logs_compute import LogsCompute
from datadog_api_client.v2.model.logs_aggregation_function import LogsAggregationFunction



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
    ddconfig.server_variables["site"] = os.getenv("DD_SITE", "datadoghq.com")

    ddconfig.api_key["apiKeyAuth"] = api_key
    ddconfig.api_key["appKeyAuth"] = app_key

    return ddconfig

def run_queries():
    with open('queries.json') as f:
        queries_json = json.load(f)

    for env in queries_json["environments"]:
        api_key = os.getenv(env.get("API_KEY"))
        app_key = os.getenv(env.get("APP_KEY"))
        env_config = get_config(api_key=api_key, app_key=app_key)

        for metric, query_string in env["queries"].items():
            count = get_aggregate(env_config, query_string)
            print(f"Total {metric} errors: {count}")


def main():
    load_dotenv()
    run_queries

if __name__ == "__main__":
    main()