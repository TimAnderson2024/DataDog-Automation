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
class QueryResult:
    name: str
    query: str
    result: int

    def __repr__(self) -> str:
        query_preview = (
            self.query if len(self.query) <= 60 else self.query[:57] + "..."
        )
        return (
            f"QueryResult("
            f"name={self.name!r}, "
            f"query={query_preview!r}, "
            f"result={self.result}"
            f")"
        )
    
class SyntheticResult:
    name: str
    synth_id: str
    logs: list[dict]
    failure_count: int
    success_count: int

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
        self.success, self.failure = success, failure

class EnvData:
    def __init__(self, env: str, err_by_type: dict[str, QueryResult], synthetic_results: dict[str, SyntheticResult]):
        self.env = env
        self._errs = err_by_type

        for err_type, result in err_by_type.items():
            setattr(self, err_type, result)
        
        self.synthetic_tests = synthetic_results
    
    def __getitem__(self, key: str) -> QueryResult:
        return self._errs[key]
    
    def __repr__(self) -> str:
        lines = [f"EnvData(env={self.env!r})"]

        if self._errs:
            lines.append(" Errors:")
            for key in sorted(self._errs):
                result = self._errs[key]
                lines.append(f"  {key}: {result!r}")

        if self.synthetic_tests:
            lines.append(" SyntheticResults:")
            for key in sorted(self.synthetic_tests):
                synth = self.synthetic_tests[key]
                lines.append(
                    f"  {key}: SyntheticResult("
                    f"name={synth.name!r}, "
                    f"synth_id={synth.synth_id!r}, "
                    f"success={synth.success}, "
                    f"failure={synth.failure}"
                    f")"
                )

        return "\n".join(lines)
        
    def errors(self):
        return self._errs.keys()

class EnvDataFactory:
    @classmethod
    def from_json_file(
        cls,
        path: str,
        start: str,
        end: str,
    ):
        with open(path) as f:
            json_config: dict = json.load(f)
        
        # Build the Datadog config object
        env_name: str = json_config["name"]
        try:
            dd_config: Configuration = q.get_dd_config(json_config["API_KEY"], json_config["APP_KEY"])
        except Exception as e:
            print(f"Failed to create EnvData for {env_name} due to missing API or APP key")
            sys.exit(1)

        # Make queries and record results 
        timerange = utils.time_utils.normalize_time(start, end)

        queries: dict = json_config["queries"]
        err_by_type: dict[str, QueryResult] = {}
        for err_name, query in queries.items():
            raw_result: int = q.query_log_count_aggregate(dd_config, query, timerange)
            result = QueryResult(err_name, query, raw_result)
            err_by_type[err_name] = result
        
        synthetics: dict = json_config["synthetic_tests"]
        synthetic_results: dict[str, SyntheticResult] = {}
        for synth_name, synth_id in synthetics.items():
            raw_result: list[dict] = q.query_synthetic_test(dd_config, synth_id, timerange)
            result = SyntheticResult(synth_name, synth_id, raw_result)
            synthetic_results[synth_name] = result

                
        return EnvData(env_name, err_by_type, synthetic_results)

def main():
    load_dotenv()
    env_data = EnvDataFactory.from_json_file(ULP_QUERIES_PATH, "now-24h", "now")
    print(env_data)

    

if __name__ == "__main__":
    main()