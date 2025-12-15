import os
from datadog_api_client import ApiClient, Configuration
from datadog_api_client.v2.api.logs_api import LogsApi
from datadog_api_client.v2.model.logs_aggregate_request import LogsAggregateRequest
from datadog_api_client.v2.model.logs_query_filter import LogsQueryFilter
from datadog_api_client.v2.model.logs_compute import LogsCompute
from datadog_api_client.v2.model.logs_aggregation_function import LogsAggregationFunction

def get_dd_config(api_key: str, app_key: str, dd_url: str):
    ddconfig = Configuration()
    ddconfig.server_variables["site"] = dd_url
    ddconfig.api_key["apiKeyAuth"] = api_key
    ddconfig.api_key["appKeyAuth"] = app_key

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