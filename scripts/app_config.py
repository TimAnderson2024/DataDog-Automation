from pathlib import Path

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
        self.time_from = "now-24h"
        self.time_to = "now"
        self.output_path = Path("output")
        self.query_path = Path("queries.json")
        self.template_path = Path("slack_template.md")
        self.output_channel_id = "C0ALY9QJ30T"
        #self.output_channel_id = "{{ .Values.dailyMonitoring.slackChannelId }}"
        self.s3_bucket = "{{ .Values.dailyMonitoring.s3BucketName }}"