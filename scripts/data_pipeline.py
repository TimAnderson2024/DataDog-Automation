from datadog_api_client import Configuration
from dotenv import load_dotenv
from utils.json_helpers import get_json_config
from utils.query import get_dd_config, get_simple_aggregate, get_aggregate_avg

class Data_Point:
    def __init__(self, err_type: str, value: int):
        self.err_type = err_type
        self.value = value
    
    def __repr__(self):
        return f"Data_Point(err={self.err_type}, value={self.value})"

    def __str__(self):
        return f"{self.err_type}: {self.value}"

def get_env_data(dd_config: Configuration, env: str, queries: dict) -> dict:
    env_data = { "24h": [], "2week_avg": [] }

    for metric, query in queries.items():
        value_24h = get_simple_aggregate(dd_config, query, time_from="now-24h")
        value_2week_avg = get_aggregate_avg(dd_config, query, weeks_back=2, weekday=True, weekend=False)

        env_data["24h"].append(Data_Point(err_type="24h", value=value_24h))
        env_data["2week_avg"].append(Data_Point(err_type=metric, value=value_2week_avg))

    return env_data

def main():
    load_dotenv()
    json_config = get_json_config("config/queries.json")
    
    env_data = { }
    for env in json_config.keys():
        env_config, env_queries = json_config[env], json_config[env]["queries"]
        try:
            dd_config = get_dd_config(env_config)
            env_data = env_data | { env: get_env_data(dd_config, env, env_queries) }
        except KeyError:
            print(f"Skipping {env} due to missing API keys.")
    

    for env, env_data_points in env_data.items():
        print(f"{env}:")
        for aggregate_type, data_points in env_data_points.items():
            print(f"\t{aggregate_type}:")
            for data_point in data_points:
                print(f"\t\t{data_point}")

if __name__ == "__main__":
    main()

