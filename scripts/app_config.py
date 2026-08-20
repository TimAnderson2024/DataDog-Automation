from pathlib import Path
from time_utils import eastern_now

# noon boundary tolerates retries/delays
RUN_SLOT = "am" if eastern_now().hour < 12 else "pm"  

class AppConfig:
    time_from: str
    time_to: str
    query_path: Path
    output_path: Path
    template_path: Path
    output_channel_id: str
    s3_bucket: str
    s3_key_prefix: str

    def __init__(self):
        if RUN_SLOT == "am":
            self.time_range = "24h"
            self.time_from = "now-24h"
        else:
            self.time_range = "9h"
            self.time_from = "now-9h"

        self.time_to = "now"
        self.output_path = Path("output")
        self.query_path = Path("queries.json")
        self.template_path = Path("slack_template.md")
        self.output_channel_id = "C0ALY9QJ30T"
        # Live channel: "C07050LEJA3"
        # Test channel: "C0ALY9QJ30T"
        # self.output_channel_id = "{{ .Values.dailyMonitoring.slackChannelId }}"
        self.s3_bucket = "stgcore-daily-monitoring-base-us-east-2"