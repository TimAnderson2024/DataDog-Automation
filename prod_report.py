import os
from dotenv import load_dotenv
from datadog_api_client import ApiClient, Configuration
from datadog_api_client.v2.api.logs_api import LogsApi
from datadog_api_client.v2.model.logs_aggregate_request import LogsAggregateRequest
from datadog_api_client.v2.model.logs_query_filter import LogsQueryFilter
from datadog_api_client.v2.model.logs_compute import LogsCompute
from datadog_api_client.v2.model.logs_aggregation_function import LogsAggregationFunction

load_dotenv()

GET_DASH_URL = "https://api.datadoghq.com/api/v1/dashboard/"
QUERIES = {
    "los_504" : "env:prod status:error @http.status_code:504",
    "los_502" : "env:prod status:error @http.status_code:502"
}
configuration = Configuration()
configuration.api_key["apiKeyAuth"] = os.getenv("DD_API_KEY")
configuration.api_key["appKeyAuth"] = os.getenv("DD_APP_KEY")
configuration.server_variables["site"] = os.getenv("DD_SITE", "datadoghq.com")


def get_aggregate(query_string):
    with ApiClient(configuration) as api_client:
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

def get_all_errors():
    for metric, query_string in QUERIES.items():
        count = get_aggregate(query_string)
        print(f"Total {metric} errors: {count}")

def main():
    get_all_errors()

if __name__ == "__main__":
    main()