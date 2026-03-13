import sys
import json

import utils.query as q
import utils.time_utils 

from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from dataclasses import dataclass
from datadog_api_client import Configuration

ULP_QUERIES_PATH = "config/ulp_queries.json"

@dataclass 
class LogResult:
    name: str
    query: str
    raw: list[dict]
    aggregate: int 

    def __init__(self, name: str, query: str, raw: list[dict]):
        self.name = name
        self.query = query
        self.raw = raw
        self.aggregate = len(raw)

@dataclass 
class AggregateResult:
    name: str
    query: str
    aggregate: int

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

    def __init__(self, name, synth_id, query_logs):
        self.name = name
        self.synth_id = synth_id
        self.logs = query_logs

        success, failure = 0, 0 
        for test in query_logs:
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

    def __init__(self, name: str, query: str, result: list) -> EventResult:
        self.name = name
        self.query = query
        self.event_list = result
        self.aggregate = len(result)


class EnvData:
    def __init__(
        self, 
        env: str, 
        err_by_type: dict[str, AggregateResult], 
        log_results: dict[str, LogResult],
        event_results: dict[str, EventResult], 
        synthetic_results: dict[str, SyntheticResult],
        filtered_fm_jobs: dict[str, int] = None
        ) -> EnvData:

        self.env = env
        self._errs = err_by_type

        for err_type, result in err_by_type.items():
            setattr(self, err_type, result)

        self.log_results = log_results
        self.event_results = event_results
        self.synthetic_results = synthetic_results
    
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

class EnvDataFactory:
    def _envdata_factory(
        json_config: dict,
        start: str,
        end: str
    ):
        # Build the Datadog config object
        env_name: str = json_config["name"]
        try:
            dd_config: Configuration = q.get_dd_config(json_config["API_KEY"], json_config["APP_KEY"])
        except Exception as e:
            print(f"Failed to create EnvData for {env_name} due to missing API or APP key")
            sys.exit(1)

        # Send aggregate queries
        timerange = utils.time_utils.normalize_time(start, end)
        err_by_type: dict[str, AggregateResult] = {}
        aggregate_queries: dict = json_config.get("aggregate_queries")
        if aggregate_queries:
            for err_name, query in aggregate_queries.items():
                raw_result: int = q.query_log_count_aggregate(dd_config, query, timerange)
                result = AggregateResult(err_name, query, raw_result)
                err_by_type[err_name] = result
        
        # Send log queries
        log_queries: dict = json_config.get("log_queries")
        log_results: dict[str, LogResult] = {}
        if log_queries:
            for name, query in log_queries.items():
                raw: list[dict] = q.query_logs(dd_config, query, timerange)
                result: LogResult = LogResult(name, query, raw)
                log_results[name] = result

        # Send event queries
        event_queries: dict = json_config.get("event_queries")
        event_results: dict[str, EventResult] = {}
        if event_queries:
            for event_name, query in event_queries.items():
                raw = q.query_events(dd_config, query, timerange)
                result = EventResult(event_name, query, raw)
                event_results[event_name] = result
            
        # Send synthetic queries
        synthetic_queries: dict = json_config.get("synthetic_queries")
        synthetic_results: dict[str, SyntheticResult] = {}
        if synthetic_queries:
            for synth_name, synth_id in synthetic_queries.items():
                raw_result: list[dict] = q.query_synthetic_test(dd_config, synth_id, timerange)
                result = SyntheticResult(synth_name, synth_id, raw_result)
                synthetic_results[synth_name] = result
                
        return EnvData(env_name, err_by_type, log_results, event_results, synthetic_results)
        
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