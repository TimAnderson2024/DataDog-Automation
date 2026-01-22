import sys
import json

import utils.query as q

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

class EnvData:
    def __init__(self, env: str, err_by_type: dict[str, QueryResult]):
        self.env = env
        self._errs = err_by_type

        for err_type, result in err_by_type.items():
            setattr(self, err_type, result)
    
    def __getitem__(self, key: str) -> QueryResult:
        return self._errs[key]
    
    def __repr__(self) -> str:
        lines = [f"EnvData(env={self.env!r})"]
        for key in sorted(self._errs):
            result = self._errs[key]
            lines.append(f"  {key}: {result!r}")
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
        queries: dict = json_config["queries"]
        err_by_type: dict[str, QueryResult] = {}
        for err_name, query in queries.items():
            count = q.query_log_count_aggregate(dd_config, query, [start, end])
            result = QueryResult(err_name, query, count)
            err_by_type[err_name] = result
        
        return EnvData(env_name, err_by_type)

def main():
    load_dotenv()
    env_data = EnvDataFactory.from_json_file(ULP_QUERIES_PATH, "now-24h", "now")
    print(env_data)

    

if __name__ == "__main__":
    main()