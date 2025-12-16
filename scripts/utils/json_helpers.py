import json

def get_json_config(path) -> dict:
    with open(path) as f:
        return json.load(f)