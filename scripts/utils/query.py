import os
import json
from datetime import datetime, timedelta
from datadog_api_client import ApiClient, Configuration

from datadog_api_client.v1 import Configuration as V1Configuration
from datadog_api_client.v1.api.metrics_api import MetricsApi as V1MetricsApi
from datadog_api_client.v1.api.synthetics_api import SyntheticsApi, SyntheticsFetchUptimesPayload

from datadog_api_client.v2.api.logs_api import LogsApi
from datadog_api_client.v2.model.logs_aggregate_request import LogsAggregateRequest
from datadog_api_client.v2.model.logs_query_filter import LogsQueryFilter
from datadog_api_client.v2.model.logs_compute import LogsCompute
from datadog_api_client.v2.model.logs_aggregation_function import LogsAggregationFunction
from datadog_api_client.v2.model.logs_list_request import LogsListRequest
from datadog_api_client.v2.model.logs_list_request_page import LogsListRequestPage
from datadog_api_client.v2.model.logs_sort import LogsSort

import utils.time_utils as time

def get_dd_config(env_config: dict) -> Configuration:
    ddconfig = Configuration()
    ddconfig.server_variables["site"] = env_config["DD_URL"]

    if not os.getenv(env_config["API_KEY"]) or not os.getenv(env_config["APP_KEY"]):
        raise KeyError("API_KEY and APP_KEY must be defined in the environment configuration.")
    
    ddconfig.api_key["apiKeyAuth"] = os.getenv(env_config["API_KEY"])
    ddconfig.api_key["appKeyAuth"] = os.getenv(env_config["APP_KEY"])

    return ddconfig

def get_v1_dd_config(env_config: dict) -> V1Configuration:
    v1_ddconfig = V1Configuration()
    v1_ddconfig.server_variables["site"] = env_config["DD_URL"]

    if not os.getenv(env_config["API_KEY"]) or not os.getenv(env_config["APP_KEY"]):
        raise KeyError("API_KEY and APP_KEY must be defined in the environment configuration.")
    
    v1_ddconfig.api_key["apiKeyAuth"] = os.getenv(env_config["API_KEY"])
    v1_ddconfig.api_key["appKeyAuth"] = os.getenv(env_config["APP_KEY"])

    return v1_ddconfig

def query_logs(dd_config: Configuration, query_string: str, time_range: tuple[int, int], keep_tags: bool) -> list[dict]:
    with ApiClient(dd_config) as api_client:
        api_instance = LogsApi(api_client)
        query_body = LogsListRequest(
                filter=LogsQueryFilter(
                    query=query_string,
                    _from=str(time_range[0]),
                    to=str(time_range[1] )
                ),
                sort=LogsSort.TIMESTAMP_DESCENDING,
                page=LogsListRequestPage(limit=1000)
            )

        all_logs = []
        logs_processed = 0
        while True:
            response = api_instance.list_logs(body=query_body)
            response_data = response.data
            response_metadata = response.meta.to_dict()
            
            # Strip tags
            if not keep_tags:
                for entry in response_data:
                    entry = entry.to_dict()
                    entry.get("attributes", {}).pop("tags", None)

            all_logs.extend(response_data)
            logs_processed += len(response_data)
            print(f"Processed {logs_processed} log entries...")
                    
            if not response_metadata.get('page', None):
                break
            query_body.page.cursor = response_metadata['page']['after']

    return all_logs

def query_metric(dd_config: V1Configuration, query_string: str, time_range: tuple[int, int]) -> list[dict]:
    with ApiClient(dd_config) as api_client:
        api_instance = V1MetricsApi(api_client)

        response = api_instance.query_metrics(
            _from=time_range[0],
            to=time_range[1],
            query=query_string
        )

        timeseries = []
        for series in response.series:
            timeseries.append(series.to_dict())
        
        return timeseries

def query_synthetic_test(dd_config: Configuration, test_id: str, time_range) -> dict:
    time_from, time_to = time_range[0], time_range[1]

    with ApiClient(dd_config) as api_client:
        api_instance = SyntheticsApi(api_client)

        # Paginate results using last_timestamp_fetched (API output cuts off at 150 results)
        synthetic_test_results = []
        print(f"Fetching synthetic results from {time.unix_to_iso(time_from)} to {time.unix_to_iso(time_to)}:")
        while time_to > time_from:
            query_response = api_instance.get_api_test_latest_results(public_id=test_id, from_ts=time_from, to_ts=time_to).to_dict()
            results = query_response["results"]

            print(f"\tFetched {len(results)} results from {time.unix_to_iso(results[-1]['check_time'])} to {time.unix_to_iso(results[0]['check_time'])}")
            time_to = query_response["last_timestamp_fetched"]
            synthetic_test_results += query_response["results"]

        print(f"Fetched {len(synthetic_test_results)} results from {time.unix_to_iso(synthetic_test_results[0]['check_time'])} to {time.unix_to_iso(synthetic_test_results[-1]['check_time'])}")
        return synthetic_test_results
    
def query_synthetic_uptime(dd_config: Configuration, test_id: str, time_from: str, time_to: str) -> dict:
    with ApiClient(dd_config) as api_client:
        api_instance = SyntheticsApi(api_client)

        query_body = SyntheticsFetchUptimesPayload(
            from_ts = time_from,
            public_ids = [test_id],
            to_ts = time_to
        )

        synthetic_test_coverage = api_instance.fetch_uptimes(query_body)[0].to_dict()
        return synthetic_test_coverage

def query_log_count_aggregate(dd_config: Configuration, query_string: str, time_range: tuple[int, int]) -> int:
    with ApiClient(dd_config) as api_client:
        api_instance = LogsApi(api_client)

        response = api_instance.aggregate_logs(
            body=LogsAggregateRequest(
                filter=LogsQueryFilter(
                    query=query_string,
                    _from=str(time_range[0]),
                    to=str(time_range[1]) 
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