import os
import json
from datetime import datetime, timedelta
from datadog_api_client import ApiClient, Configuration
from datadog_api_client.v2.api.logs_api import LogsApi
from datadog_api_client.v2.model.logs_aggregate_request import LogsAggregateRequest
from datadog_api_client.v2.model.logs_query_filter import LogsQueryFilter
from datadog_api_client.v2.model.logs_compute import LogsCompute
from datadog_api_client.v2.model.logs_aggregation_function import LogsAggregationFunction
from datadog_api_client.v2.model.logs_list_request import LogsListRequest
from datadog_api_client.v2.model.logs_list_request_page import LogsListRequestPage
from datadog_api_client.v2.model.logs_sort import LogsSort

from utils import json_helpers

def get_dd_config(env_config: dict) -> Configuration:
    ddconfig = Configuration()
    ddconfig.server_variables["site"] = env_config["DD_URL"]

    if not os.getenv(env_config["API_KEY"]) or not os.getenv(env_config["APP_KEY"]):
        raise KeyError("API_KEY and APP_KEY must be defined in the environment configuration.")
    
    ddconfig.api_key["apiKeyAuth"] = os.getenv(env_config["API_KEY"])
    ddconfig.api_key["appKeyAuth"] = os.getenv(env_config["APP_KEY"])

    return ddconfig

def query_logs(dd_config: Configuration, query_string: str, time_from: str, time_to: str) -> list[dict]:
    with ApiClient(dd_config) as api_client:
        api_instance = LogsApi(api_client)
        query_body = LogsListRequest(
                filter=LogsQueryFilter(
                    query=query_string,
                    _from=time_from,
                    to=time_to 
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

            all_logs.extend(response_data)
            logs_processed += len(response_data)
            print(f"Processed {logs_processed} log entries...")
                    
            if not response_metadata.get('page', None):
                break
            query_body.page.cursor = response_metadata['page']['after']
        
    return all_logs

def query_aggregate_count(dd_config: Configuration, query_string: str, time_from: str, time_to: str) -> int:
    with ApiClient(dd_config) as api_client:
        api_instance = LogsApi(api_client)

        response = api_instance.aggregate_logs(
            body=LogsAggregateRequest(
                filter=LogsQueryFilter(
                    query=query_string,
                    _from=time_from,
                    to=time_to 
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

def get_simple_aggregate(dd_config: Configuration, query_string: str, time_from: str) -> int:
    return query_aggregate_count(dd_config, query_string, time_from, "now")

def get_filtered_aggregate(dd_config: Configuration, query_string: str, weeks_back: int, weekday = True, weekend = False) -> int:
    weekday_ranges = get_date_ranges(weeks_back, weekday, weekend)
    total_count = 0

    for from_time, to_time in weekday_ranges:
        count = query_aggregate_count(dd_config, query_string, from_time, to_time)
        total_count += count
    
    return total_count

def get_aggregate_breakdown(dd_config: Configuration, query_string: str, weeks_back: int, weekday=True, weekend=False) -> dict:
    weekday_ranges = get_date_ranges(weeks_back, weekday, weekend)
    breakdown = {}

    for from_time, to_time in weekday_ranges:
        count = query_aggregate_count(dd_config, query_string, from_time, to_time)
        date_key = from_time.split('T')[0]
        breakdown[date_key] = count
    
    return breakdown

def get_aggregate_avg(dd_config: Configuration, query_string: str, weeks_back: int, weekday=True, weekend=False) -> int:
    total_count = get_filtered_aggregate(dd_config, query_string, weeks_back, weekday, weekend)
    num_days = get_num_days(weeks_back, weekday, weekend)

    if num_days == 0:
        return -1  # Avoid division by zero; return -1 to indicate no days found
    
    return total_count // num_days  # Integer division for daily average

def get_num_days(weeks_back: int, weekday: bool, weekend: bool) -> int:
    """
    Calculate the number of days in the last N weeks that are either weekdays or weekends.
    """
    today = datetime.now()
    num_days = 0
    
    # Go back 'weeks_back' weeks from today
    start_date = today - timedelta(weeks=weeks_back)
    
    # Iterate through each day from start_date to today
    current_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    
    while current_date.date() <= today.date():
        # Check if it's a weekday (Monday=0, Sunday=6) or weekend (Saturday=5, Sunday=6)
        if (weekday and current_date.weekday() < 5) or (weekend and current_date.weekday() > 4):
            num_days += 1
        current_date += timedelta(days=1)
    
    return num_days

def get_date_ranges(weeks_back: int, weekday: bool, weekend: bool ):
    """
    Generate list of (from, to) date tuples for weekdays only in the last N weeks.
    Returns dates in ISO format suitable for DataDog API.
    """
    today = datetime.now()
    date_ranges = []
    
    # Go back 'weeks_back' weeks from today
    start_date = today - timedelta(weeks=weeks_back)
    
    # Iterate through each day from start_date to today
    current_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    
    while current_date.date() <= today.date():
        # Check if it's a weekday (Monday=0, Sunday=6) or weekend (Saturday=5, Sunday=6)
        if (weekday and current_date.weekday() < 5) or (weekend and current_date.weekday() > 4):
            day_start = current_date
            day_end = current_date.replace(hour=23, minute=59, second=59, microsecond=999999)
            # Convert to ISO format for DataDog
            from_time = day_start.isoformat()
            to_time = day_end.isoformat()
            date_ranges.append((from_time, to_time))
        current_date += timedelta(days=1)
    return date_ranges

def get_weekday_average(dd_config: Configuration, query_string: str, time_from: str) -> int:
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
                        aggregation=LogsAggregationFunction.AVG
                    )
                ]
            )
        )

        print(response.data)
        
        if response.data.buckets and len(response.data.buckets) > 0:
            total_count = int(response.data.buckets[0].computes.get('c0', 0))
            average = total_count // 14  # Integer division for daily average
            return average
        return 0