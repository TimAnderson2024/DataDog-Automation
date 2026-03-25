from env_data import EnvData, Result
from datetime import date

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

class SlackMessenger:
    data: dict[EnvData]
    message_blocks: list[dict]
    token: str
    channel_id: str

    def __init__(self, all_env_data: dict[EnvData], token: str, channel_id: str):
        self.data = all_env_data
        self.message_blocks = []
        self.token = token
        self.channel_id = channel_id

    def send_message(self):
        if not self.token:
            raise ValueError("SLACK_API_KEY is not set")
        
        if not self.channel_id:
            raise ValueError("OUTPUT_CHANNEL_ID is not set")
        
        client = WebClient(self.token)
        try:
            auth_response = client.auth_test()
            print(
                f"Authenticated to Slack as '{auth_response['user']}' in workspace '{auth_response['team']}'"
            )

            response = client.chat_postMessage(
                channel=self.channel_id,
                blocks=self.message_blocks,
            )

            print(f"Slack message sent successfully. ts={response['ts']}")

        except SlackApiError as e:
            print(f"Slack API error: {e.response['error']}")
            raise
    
    def build_message(self):
        self.build_header()

        # Split up envs by alert level
        alert_envs = {"green": [], "yellow": [], "red": []}
        for env in self.data:
            if env.alert_level == 2:
                alert_envs["red"].append(env)
            elif env.alert_level == 1:
                alert_envs["yellow"].append(env)
            else:
                alert_envs["green"].append(env)

        # Get manual review results
        manual_review_envs = [env for env in self.data if getattr(env, "manual_review", False)]
        self.build_summary(alert_envs, manual_review_envs)
        self.build_env_breakdowns(alert_envs)
    
    def build_header(self):
        header_blocks = []

        header_blocks.append(
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"📊 ENV Health Status — {date.today().strftime('%Y-%m-%d')}",
                },
            }
        )

        env_list = [env.env for env in self.data]
        header_blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": (
                            f"{len(env_list)} environments • "
                            f"{', '.join(f'*{env_name}*' for env_name in env_list)}"
                        ),
                    }
                ],
            }
        )

        self.message_blocks.extend(header_blocks)

    
    def build_issue_summary_line(self, env: EnvData, alert_level: int) -> str:
        all_results = env.get_all_results()
        alert_results = [f"{result.aggregate} {result.name}" for result in all_results.values() if result.alert_level == alert_level]

        if alert_level == 2:
            return f"🔴 *{env.env}* — " + ", ".join(alert_results)
        return f"🟡 *{env.env}* — " + ", ".join(alert_results)     


    def build_summary(self, alert_envs: dict[str, list[EnvData]], manual_review_envs: list[EnvData]):
        summary_blocks = []

        if manual_review_envs:
            manual_review_lines = [f"🔎 *{env.env}* — {', '.join(f'{result.name} ({result.aggregate})' for result in env.get_manual_review_results().values())}" for env in manual_review_envs]
            summary_blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Manual Review*\n" + "\n".join(manual_review_lines),
                    }
                }
            )

        if alert_envs["green"]:
            summary_blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Healthy*\n🟢 *{', '.join(env.env for env in alert_envs['green'])}*"
                    },
                }
            )
        
        summary_blocks.append({"type": "divider"})
        self.message_blocks.extend(summary_blocks)
    
    @staticmethod
    def get_status_icon(obj: EnvData | Result) -> str:
        if obj.alert_level == 2:
            return "🔴"
        elif obj.alert_level == 1:
            return "🟡"
        else:
            return "🟢"

    def build_env_fields(self, env: EnvData) -> list[dict]:
        env_blocks = []
        all_results = env.get_all_results()

        err_text = ""
        for err in ["504", "502", "oom"]:
            result = all_results.get(err)
            err_text = err_text + f"*{self.get_status_icon(result)} {err}:* {result.aggregate} \n"
        if all_results.get("503").aggregate > 0:
            result = all_results.get("503")
            err_text = err_text + f"*{self.get_status_icon(result)} 503:* {result.aggregate} \n"
        env_blocks.append({"type": "mrkdwn", "text": err_text})

        synthetic_results = getattr(env, "synthetic_results", None) or {}
        if synthetic_results and len(synthetic_results.values()) > 0:
            synthetic_parts = []
            for _, result in synthetic_results.items():
                name = getattr(result, "name", "unknown")
                failure_count = getattr(result, "failure_count", 0)
                icon = "✅" if failure_count == 0 else "🔴"
                synthetic_parts.append(f"`{name}` ({failure_count}) {icon} ")
            synthetic_text = "*Synthetic:* " + "\n".join(synthetic_parts)
            env_blocks.append({"type": "mrkdwn", "text": synthetic_text})

        return env_blocks
    
    def build_filemover_context(self, env) -> dict | None:
        fm_jobs = getattr(env, "filtered_fm_jobs", {}) or {}
        if not fm_jobs:
            return None

        fm_parts = [f"`{job}` ({count})" for job, count in fm_jobs.items()]
        return {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "*Filemover failures:* " + ", ".join(fm_parts),
                }
            ],
        }

    def build_env_breakdowns(self, alert_envs: dict[str, list[EnvData]]) -> list[dict]:
        for env in [*alert_envs["yellow"], *alert_envs["red"]]:
            env_block = {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{env.env}*"
                },
                "fields": self.build_env_fields(env)
            }

            self.message_blocks.append(env_block)
            fm_context = self.build_filemover_context(env)
            print(fm_context)
            if fm_context:
                self.message_blocks.append(fm_context)
            self.message_blocks.append({"type": "divider"})      