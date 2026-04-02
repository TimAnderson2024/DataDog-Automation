import json

from dataclasses import dataclass
from pathlib import Path

CONFIG_PATH = Path("config/config.json")

@dataclass
class AppConfig:
    time_from: str
    time_to: str
    query_path: Path
    output_path: Path
    template_path: Path
    output_channel_id: str
    s3_bucket: str
    s3_key_prefix: str

def load_config(path) -> AppConfig:
    with open(path, "r") as f:
        data = json.load(f)

    return AppConfig(
        time_from=data["TIME_FROM"],
        time_to=data["TIME_TO"],
        query_path=Path(data["QUERY_PATH"]),
        output_path=Path(data["OUTPUT_PATH"]),  
        template_path=Path(data["TEMPLATE_PATH"]),
        output_channel_id=data["OUTPUT_CHANNEL_ID"],
        s3_bucket=data["S3_BUCKET"],
        s3_key_prefix=data["S3_KEY_PREFIX"]
    )