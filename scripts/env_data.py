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
        type: str,
        timerange: tuple[str, str],
        query_config: dict,
        dd_config: Configuration,
    ):

        self.name = name
        self.type = type
        self.timerange = timerange
        self.dd_config = dd_config

        self.query = query_config.get("query")
        self.red_threshold = query_config.get("red_threshold")
        self.yellow_threshold = query_config.get("yellow_threshold", self.red_threshold)
        self.manual_threshold = query_config.get("manual_threshold", 1)

    
    def set_alert_levels(self):
        if self.aggregate >= self.red_threshold:
            self.alert_level = 2
        elif self.aggregate >= self.yellow_threshold:
            self.alert_level = 1
        else:
            self.alert_level = 0

        if self.aggregate >= self.manual_threshold:
            self.manual_review = True
        else:
            self.manual_review = False

class AggregateResult(Result):
    sorted: list[dict[str, int]] # Sorted list of {Path, Count} dicts

    def __init__(
        self,
        name: str,
        type: str,
        timerange: tuple[str, str],
        query_config: dict,
        dd_config: Configuration,
    ):
        super().__init__(name, type, timerange, query_config, dd_config)

        self.raw, self.sorted = q.query_log_count_aggregate(dd_config, self.query, timerange)
        self.aggregate = sum(item['count'] for item in self.sorted)
        self.set_alert_levels()

class LogResult(Result):
    def __init__(
        self,
        name: str,
        type: str,
        timerange: tuple[str, str],
        query_config: dict,
        dd_config: Configuration,
    ):
        super().__init__(name, type, timerange, query_config, dd_config)

        self.raw = q.query_logs(dd_config, self.query, timerange)
        self.aggregate = len(self.raw)
        self.set_alert_levels()

class EventResult(Result):
    def __init__(
        self,
        name: str,
        type: str,
        timerange: tuple[str, str],
        query_config: dict,
        dd_config: Configuration,
    ):
        super().__init__(name, type, timerange, query_config, dd_config)

        self.raw = q.query_events(dd_config, self.query, timerange)
        self.aggregate = len(self.raw)
        self.set_alert_levels()

class SyntheticResult(Result):
    def __init__(
        self,
        name: str,
        type: str,
        timerange: tuple[str, str],
        query_config: dict,
        dd_config: Configuration,
    ):
        super().__init__(name, type, timerange, query_config, dd_config)

        self.raw = q.query_synthetic_test(dd_config, self.query, timerange)
        self.aggregate = 0
        for test in self.raw:
            if not test["result"]["passed"]:
                self.aggregate += 1

        self.set_alert_levels()

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
                json_config["API_KEY"], json_config["APP_KEY"], json_config.get("DD_URL", q.DATADOG_URL)
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
        "aggregate": AggregateResult,
        "log": LogResult,
        "synthetic": SyntheticResult,
        "event": EventResult,
    }

    @staticmethod
    def _envdata_factory(env_config: dict, queries: dict, start: str, end: str):
        env_data = EnvData(env_config, start, end)

        logger.info(f"Sending queries for environment: {env_config['name']}")
        for query_name, query_config in queries.items():
            query_config: dict
            query_type = query_config.get("type")
            
            logger.info(f"Running query '{query_name}' of type '{query_type}'")
            
            result_class = EnvDataFactory.query_map[query_type]
            new_result = result_class(
                name=query_name,
                type=query_type,
                timerange=env_data.timerange,
                query_config=query_config,
                dd_config=env_data.dd_config,
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
                logger.info(env.get("name"))
                env_data_series.append(EnvDataFactory._envdata_factory(env, env["queries"], start, end))
        else:
            env_data_series.append(
                EnvDataFactory._envdata_factory(env, env["queries"], start, end)
            )

        return env_data_series
