import logging
import sys
import json

import query as q
import time_utils

from datadog_api_client import Configuration

logger = logging.getLogger(__name__)

class Result:
    name: str
    query: str
    type: str
    raw: int | list[dict]
    aggregate: int
    yellow_threshold: int
    red_threshold: int
    alert_level: int
    manual_review: bool

    def __init__(
        self,
        name: str,
        query: str,
        type: str,
        raw: int | list[dict],
        aggregate: int,
        yellow_threshold: int,
        red_threshold: int,
        manual_threshold: int,
    ):
        self.name = name
        self.query = query
        self.type = type
        self.raw = raw
        self.aggregate = aggregate
        self.yellow_threshold = yellow_threshold
        self.red_threshold = red_threshold

        if self.aggregate >= self.red_threshold:
            self.alert_level = 2
        elif self.aggregate >= self.yellow_threshold:
            self.alert_level = 1
        else:
            self.alert_level = 0

        if self.aggregate >= manual_threshold:
            self.manual_review = True
        else:
            self.manual_review = False


class EnvData:
    env: str
    dd_config: Configuration
    _errs: dict[str, Result]
    log_results: dict[str, Result]
    event_results: dict[str, Result]
    synthetic_results: dict[str, Result]
    alert_level = int
    manual_review = bool
    no_errors = bool

    def __init__(
        self,
        json_config: dict,
        start: str,
        end: str,
    ):

        self.env = json_config["name"]
        self.timerange = time_utils.normalize_time(start, end)
        self._errs = {}
        self.log_results = {}
        self.event_results = {}
        self.synthetic_results = {}
        self.alert_level = 0
        self.manual_review = False
        self.no_errors = True

        try:
            self.dd_config = q.get_dd_config(
                json_config["API_KEY"], json_config["APP_KEY"]
            )
        except Exception as e:
            print(
                f"Failed to create EnvData for {self.env} due to missing API or APP key: {e}"
            )
            sys.exit(1)

    def add_result(self, result: Result):
        if result.aggregate > 0:
            self.no_errors = False

        if result.alert_level > self.alert_level:
            self.alert_level = result.alert_level

        if result.manual_review == True:
            self.manual_review = True

        if result.type == "aggregate":
            self._errs[result.name] = result
        elif result.type == "log":
            self.log_results[result.name] = result
        elif result.type == "event":
            self.event_results[result.name] = result
        elif result.type == "synthetic":
            self.synthetic_results[result.name] = result

    def get_all_results(self) -> dict[str, Result]:
        all_results = {}
        all_results.update(self._errs)
        all_results.update(self.log_results)
        all_results.update(self.event_results)
        all_results.update(self.synthetic_results)
        return all_results

    def get_manual_review_results(self) -> dict[str, Result]:
        all_results = self.get_all_results()
        manual_results = {
            name: result for name, result in all_results.items() if result.manual_review
        }
        return manual_results

    def errors(self):
        return self._errs.keys()


class EnvDataFactory:
    query_map = {
        "aggregate": q.query_log_count_aggregate,
        "log": q.query_logs,
        "synthetic": q.query_synthetic_test,
        "event": q.query_events,
    }

    def _envdata_factory(env_config: dict, queries: dict, start: str, end: str):
        env_data = EnvData(env_config, start, end)

        logger.info(f"Sending queries for environment: {env_config['name']}")
        for query_name, query_config in queries.items():
            query_config: dict
            query_type = query_config.get("type")
            query = query_config.get("query")
            red_threshold = query_config.get("red_threshold")
            yellow_threshold = query_config.get("yellow_threshold", red_threshold)
            manual_threshold = query_config.get("manual_threshold", 1)

            fetch_query = EnvDataFactory.query_map.get(query_type)
            
            logger.info(f"Running query '{query_name}' of type '{query_type}'")
            raw_result = fetch_query(env_data.dd_config, query, env_data.timerange)
            
            aggregate = raw_result
            if query_type in ["log", "event"]:
                aggregate = len(raw_result)
            elif query_type == "synthetic":
                aggregate = 0
                for test in raw_result:
                    if not test["result"]["passed"]:
                        aggregate += 1
            
            new_result = Result(
                name=query_name,
                query=query,
                type=query_type,
                raw=raw_result,
                aggregate=aggregate,
                yellow_threshold=yellow_threshold,
                red_threshold=red_threshold,
                manual_threshold=manual_threshold,
            )
            env_data.add_result(new_result)

        return env_data

    @classmethod
    def from_static(
        cls,
        json_queries: dict,
        start: str,
        end: str,
    ) -> list[EnvData]:
        env_data_series: list = []
        if type(json_queries) is list:
            for env in json_queries:
                env_data_series.append(EnvDataFactory._envdata_factory(env, env["queries"], start, end))
        else:
            env_data_series.append(
                EnvDataFactory._envdata_factory(env, env["queries"], start, end)
            )

        return env_data_series
