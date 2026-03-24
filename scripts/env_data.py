import sys
import json

import utils.query as q
import utils.time_utils 

from dataclasses import dataclass
from datadog_api_client import Configuration

class Result:
    name: str
    query: str
    type: str
    raw: int | list[dict]
    aggregate: int
    yellow_threshold: int
    red_threshold: int
    alert_level: int

    def __init__(self, name: str, query: str, result_type: str, raw: int | list[dict], aggregate: int, yellow_threshold: int, red_threshold: int):
        self.name = name
        self.query = query
        self.type = result_type
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

class AggregateResult(Result):
    def __init__(self, name: str, query: str, aggregate: int, yellow_threshold: int, red_threshold: int):
        super().__init__(name, query, "aggregate", aggregate, aggregate, yellow_threshold, red_threshold)


class LogResult(Result):
    raw: list[dict]

    def __init__(self, name: str, query: str, raw: list[dict], yellow_threshold: int, red_threshold: int):
        super().__init__(name, query, "log", raw, len(raw), yellow_threshold, red_threshold)


class EventResult(Result):
    raw: list[dict]
    
    def __init__(self, name: str, query: str, raw: list[dict], yellow_threshold: int, red_threshold: int):
        super().__init__(name, query, "event", raw, len(raw), yellow_threshold, red_threshold)

class SyntheticResult(Result):
    raw: list[dict]

    def __init__(self, name: str, synth_id: str, raw: list[dict], yellow_threshold: int, red_threshold: int):
        aggregate_failures = 0 

        for test in raw:
            if not test["result"]["passed"]:
                aggregate_failures += 1

        self.failure_count = aggregate_failures
        super().__init__(name, synth_id, "synthetic", raw, aggregate_failures, yellow_threshold, red_threshold)

class EnvData:
    env: str
    dd_config: Configuration
    _errs: dict[str, AggregateResult]
    log_results: dict[str, LogResult]
    event_results: dict[str, EventResult]
    synthetic_results: dict[str, SyntheticResult]
    
    def __init__(
        self, 
        json_config: dict,
        start: str,
        end: str,
        ) -> EnvData:

        self.env = json_config["name"]
        self.timerange = utils.time_utils.normalize_time(start, end)
        self._errs = {}
        self.log_results = {}
        self.event_results = {}
        self.synthetic_results = {}

        try:
            self.dd_config = q.get_dd_config(json_config["API_KEY"], json_config["APP_KEY"])
        except Exception as e:
            print(f"Failed to create EnvData for {self.env} due to missing API or APP key")
            sys.exit(1)

    def add_result(self, result: Result):
        if isinstance(result, AggregateResult):
            self._errs[result.name] = result
        elif isinstance(result, LogResult):
            self.log_results[result.name] = result
        elif isinstance(result, EventResult):
            self.event_results[result.name] = result
        elif isinstance(result, SyntheticResult):
            self.synthetic_results[result.name] = result
    
    def get_all_results(self) -> dict[str, Result]:
        all_results = {}
        all_results.update(self._errs)
        all_results.update(self.log_results)
        all_results.update(self.event_results)
        all_results.update(self.synthetic_results)
        return all_results

    def __getitem__(self, key: str) -> AggregateResult:
        return self._errs[key]
    
    def __repr__(self) -> str:
        lines = [f"EnvData(env={self.env!r})"]

        if self._errs:
            lines.append(" Errors:")
            for key in sorted(self._errs):
                result = self._errs[key]
                lines.append(f"  {key}: {result!r}")

        if self.event_results:
            lines.append(" Event Results:")
            for key in sorted(self.event_results):
                event = self.event_results[key]
                lines.append(f"{key}: {event.aggregate}")

        if self.synthetic_results:
            lines.append(" SyntheticResults:")
            for key in sorted(self.synthetic_results):
                synth = self.synthetic_results[key]
                lines.append(
                    f"  {key}: SyntheticResult("
                    f"name={synth.name!r}, "
                    f"synth_id={synth.query!r}, "
                    f"failure={synth.failure_count}"
                    f")"
                )

        return "\n".join(lines)
        
    def errors(self):
        return self._errs.keys()


class EnvDataFactory:
    @staticmethod
    def _build_aggregate_result(env_data: EnvData, query_name: str, query: str, yellow_threshold: int, red_threshold: int) -> AggregateResult:
        raw = q.query_log_count_aggregate(env_data.dd_config, query, env_data.timerange)
        return AggregateResult(query_name, query, raw, yellow_threshold, red_threshold)
   
    @staticmethod
    def _build_log_result(env_data: EnvData, query_name: str, query: str, yellow_threshold: int, red_threshold: int) -> LogResult:
        raw = q.query_logs(env_data.dd_config, query, env_data.timerange)
        return LogResult(query_name, query, raw, yellow_threshold, red_threshold)
    
    @staticmethod
    def _build_event_result(env_data: EnvData, query_name: str, query: str, yellow_threshold: int, red_threshold: int) -> EventResult:
        raw = q.query_events(env_data.dd_config, query, env_data.timerange)
        return EventResult(query_name, query, raw, yellow_threshold, red_threshold)   
    
    @staticmethod
    def _build_synthetic_result(env_data: EnvData, query_name: str, synth_id: str, yellow_threshold: int, red_threshold: int) -> SyntheticResult:
        raw = q.query_synthetic_test(env_data.dd_config, synth_id, env_data.timerange)
        return SyntheticResult(query_name, synth_id, raw, yellow_threshold, red_threshold)
    
    result_factory_map = {
        "aggregate": _build_aggregate_result,
        "log": _build_log_result,
        "synthetic": _build_synthetic_result,
        "event": _build_event_result
    }

    def _envdata_factory(
        json_config: dict,
        start: str,
        end: str
    ):
        env_data = EnvData(json_config, start, end)

        queries: dict = json_config.get("queries")
        for query_name, query_config in queries.items():
            query_config: dict                    
            query_type = query_config.get("type") 
            query = query_config.get("query")
            red_threshold = query_config.get("red_threshold")
            yellow_threshold = query_config.get("yellow_threshold", red_threshold)
            
            result_class = EnvDataFactory.result_factory_map.get(query_type)
            if not result_class:
                print(f"Unknown query type {query_type} in config for {env_data.env}")
                continue
            print(f"Processing {query_type} query {query} for env {env_data.env}")

            new_result = result_class(env_data, query_name, query, yellow_threshold, red_threshold)
            env_data.add_result(new_result)

        return env_data
    
    def _build_result(
        env_data: EnvData,
        query_name: str,
        query_config: dict
    ) -> Result:
        query_type = query_config.get("type") 
        query = query_config.get("query")
        red_threshold = query_config.get("red_threshold")
        yellow_threshold = query_config.get("yellow_threshold", red_threshold)
        
        result_class = EnvDataFactory.result_factory_map.get(query_type)
        if not result_class:
            print(f"Unknown query type {query_type} in config for {env_data.env}")
            return None
        print(f"Processing {query_type} query {query} for env {env_data.env}")

        return result_class(env_data, query_name, query, yellow_threshold, red_threshold)
    

    @classmethod
    def from_json_file(
        cls,
        path: str,
        start: str,
        end: str,
    ) -> list[EnvData]:
        with open(path) as f:
            json_config: dict = json.load(f)
        
        env_data_series: list = []
        if type(json_config) is list:
            for env in json_config:
                env_data_series.append(EnvDataFactory._envdata_factory(env, start, end))
        else:
            env_data_series.append(EnvDataFactory._envdata_factory(json_config, start, end))

        return env_data_series