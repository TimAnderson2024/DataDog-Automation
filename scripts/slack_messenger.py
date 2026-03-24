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
