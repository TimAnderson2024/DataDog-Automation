import os
from dotenv import load_dotenv

from utils import json_helpers
from utils.query import get_dd_config, get_two_week_average

def main():
    load_dotenv()
    los_queries_json = json_helpers.get_json_config('config/queries.json')[1]
    dd_config = get_dd_config(
        os.getenv(los_queries_json["API_KEY"]),
        os.getenv(los_queries_json["APP_KEY"]),
        los_queries_json["dd_url"]
    )
    