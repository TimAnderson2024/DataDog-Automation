from env_data import EnvData
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
        self.build_summary()
    
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
    

    def build_healthy_summary_line(self, healthy_envs: list[EnvData]) -> str:
        return 


    def build_summary(self):
        summary_blocks, green_envs, yellow_envs, red_envs = [], [], [], []

        for env in self.data:
            max_level = 0
            for result_dict in [env.log_results.values(), env._errs.values(), env.synthetic_results.values(), env.event_results.values()]:
                for result in result_dict:
                    print(f"Env: {env.env}, Result: {result.name}, Type: {result.type}, Aggregate: {result.aggregate}, Alert Level: {result.alert_level}")
                    max_level = max(max_level, result.alert_level)
            
            levels = [green_envs, yellow_envs, red_envs]
            levels[max_level].append(env)
    
        if red_envs:
            red_summary_lines = [self.build_issue_summary_line(env, 2) for env in red_envs]
            summary_blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Errors Exceed Threshold*\n" + "\n".join(red_summary_lines),
                    },
                }
            )
        
        if yellow_envs:
            yellow_summary_lines = [self.build_issue_summary_line(env, 1) for env in yellow_envs]
            summary_blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Errors Within Threshold*\n" + "\n".join(yellow_summary_lines),
                    },
                }
            )

        if green_envs: 
            summary_blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Healthy*\n🟢 *{', '.join(env.env for env in green_envs)}*"
                    },
                }
            )
        
        summary_blocks.append({"type": "divider"})
        self.message_blocks.extend(summary_blocks)