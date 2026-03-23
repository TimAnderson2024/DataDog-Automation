import sys
import json

import utils.query as q
import utils.time_utils 

from dataclasses import dataclass
from datadog_api_client import Configuration

class LogResult:
    name: str
    query: str
    raw: list[dict]
    aggregate: int 
    threshold: int

    def __init__(self, env_data: EnvData, name: str, query: str, threshold: int):
        self.name = name
        self.query = query
        self.threshold = threshold
        self.raw = q.query_logs(env_data.dd_config, query, env_data.timerange)
        self.aggregate = len(self.raw)

class AggregateResult:
    name: str
    query: str
    aggregate: int
    threshold: int

    def __init__(self, env_data: EnvData, name: str, query: str, threshold: int):
        self.name = name
        self.query = query
        self.threshold = threshold
        self.aggregate = q.query_log_count_aggregate(env_data.dd_config, query, env_data.timerange)

    def __repr__(self) -> str:
        query_preview = (
            self.query if len(self.query) <= 60 else self.query[:57] + "..."
        )
        return (
            f"AggregateResult("
            f"name={self.name!r}, "
            f"query={query_preview!r}, "
            f"aggregate={self.aggregate}"
            f")"
        )
    
class SyntheticResult:
    name: str
    synth_id: str
    logs: list[dict]
    failure_count: int
    success_count: int
    has_failures: bool

    def __init__(self, env_data: EnvData, name: str, query: str, threshold: int):
        self.name = name
        self.synth_id = query
        self.threshold = threshold 
        self.logs = q.query_synthetic_test(env_data.dd_config, query, env_data.timerange)

        success, failure = 0, 0 
        for test in self.logs:
            if test["result"]["passed"]:
                success += 1
            else:
                failure += 1
        self.success_count, self.failure_count = success, failure
        
        self.has_failures = False
        if failure != 0:
            self.has_failures = True

@dataclass
class EventResult:
    name: str
    query: str
    event_list: list
    aggregate: int

    def __init__(self, env_data: EnvData, name: str, query: str, threshold: int) -> EventResult:
        self.name = name
        self.query = query
        self.event_list = q.query_events(env_data.dd_config, query, env_data.timerange)
        self.aggregate = len(self.event_list)
        self.threshold = threshold


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

    def add_result(self, result):
        if isinstance(result, AggregateResult):
            self._errs[result.name] = result
        elif isinstance(result, LogResult):
            self.log_results[result.name] = result
        elif isinstance(result, EventResult):
            self.event_results[result.name] = result
        elif isinstance(result, SyntheticResult):
            self.synthetic_results[result.name] = result

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
                    f"synth_id={synth.synth_id!r}, "
                    f"success={synth.success_count}, "
                    f"failure={synth.failure_count}"
                    f")"
                )

        return "\n".join(lines)
        
    def errors(self):
        return self._errs.keys()

result_factory_map = {
    "aggregate": AggregateResult,
    "log": LogResult,
    "synthetic": SyntheticResult,
    "event": EventResult
}

class EnvDataFactory:
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
            threshold = query_config.get("threshold")
            
            result_class = result_factory_map.get(query_type)
            if not result_class:
                print(f"Unknown query type {query_type} in config for {env_data.env}")
                continue
            print(f"Processing {query_type} query {query} for env {env_data.env}")

            new_result = result_class(env_data, query_name, query, threshold)
            env_data.add_result(new_result)

        return env_data
        
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