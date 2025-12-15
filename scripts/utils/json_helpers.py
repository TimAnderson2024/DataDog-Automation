import json

def get_json_config(path):
    with open(path) as f:
        return json.load(f)