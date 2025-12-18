import json

def load_json_from_file(path) -> dict:
    with open(path) as f:
        return json.load(f)
    
def write_json_to_file(data: dict, filepath: str):
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=4)