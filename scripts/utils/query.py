import os
from datadog_api_client import ApiClient, Configuration
from datadog_api_client.v2.api.logs_api import LogsApi
from datadog_api_client.v2.model.logs_aggregate_request import LogsAggregateRequest
from datadog_api_client.v2.model.logs_query_filter import LogsQueryFilter
from datadog_api_client.v2.model.logs_compute import LogsCompute
from datadog_api_client.v2.model.logs_aggregation_function import LogsAggregationFunction

from utils import json_helpers

def get_dd_config(env_name):
    env_config = json_helpers.get_json_config('config/queries.json')["ulp"]
    print(env_config)
    
    ddconfig = Configuration()
    ddconfig.server_variables["site"] = env_config["DD_URL"]
    ddconfig.api_key["apiKeyAuth"] = os.getenv(env_config["API_KEY"])
    ddconfig.api_key["appKeyAuth"] = os.getenv(env_config["APP_KEY"])

    return ddconfig

def get_aggregate_count(dd_config: Configuration, query_string: str, time_from: str) -> int:
    with ApiClient(dd_config) as api_client:
        api_instance = LogsApi(api_client)
        response = api_instance.aggregate_logs(
            body=LogsAggregateRequest(
                filter=LogsQueryFilter(
                    query=query_string,
                    _from=time_from,
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
            return int(response.data.buckets[0].computes.get('c0', 0))
        return 0
    

def get_two_week_average(dd_config: Configuration, query_string: str) -> int:
    with ApiClient(dd_config) as api_client:
        api_instance = LogsApi(api_client)
        response = api_instance.aggregate_logs(
            body=LogsAggregateRequest(
                filter=LogsQueryFilter(
                    query=query_string,
                    _from="now-14d",
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
            total_count = int(response.data.buckets[0].computes.get('c0', 0))
            average = total_count // 14  # Integer division for daily average
            return average
        return 0