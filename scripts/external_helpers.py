import json
import base64
import logging
from typing import List, Dict

import boto3
import requests

logger = logging.getLogger(__name__)

__all__ = ["get_aws_secrets_helper", "send_slack_message"]


def get_aws_secrets_helper(aws_secret_ids: List[str], aws_region_name: str) -> Dict[str, Dict[str, str]]:
    """Fetch multiple AWS Secrets Manager secrets as a nested dict.

    Returns:
        {
            "<secret_id>": { ...secret JSON... },
            ...
        }

    Raises:
        TypeError: If a secret isn't a JSON object.
        JSONDecodeError / ClientError: For invalid JSON or AWS issues.
    """
    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager", region_name=aws_region_name)

    results: Dict[str, Dict[str, str]] = {}

    for secret_id in aws_secret_ids:
        resp = client.get_secret_value(SecretId=secret_id)
        raw = resp.get("SecretString")
        if raw is None:
            raw = base64.b64decode(resp.get("SecretBinary", b"")).decode("utf-8")

        data = json.loads(raw) if raw else {}
        results[secret_id] = data

    logger.info("Successfully loaded %d secret(s).", len(results))
    return results


def send_slack_message(notification_message: str, slack_channel: str, slack_bot_token: str) -> None:
    """Send a formatted message to a Slack channel via Slack Web API.

    Logs outcomes; raises on transport-level errors.
    """
    payload = {"channel": slack_channel}

    if isinstance(notification_message, list): 
        payload["blocks"] = notification_message
    else:
        payload = {
            "blocks": [
                {"type": "section", "text": {"type": "mrkdwn", "text": notification_message, "verbatim": True}}
            ],
        }

    try:
        response = requests.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {slack_bot_token}"},
            json=payload,
            timeout=10,
        )
        response.raise_for_status()
        result = response.json()

        if result.get("ok"):
            logger.info("Message sent to Slack channel '%s'.", slack_channel)
        else:
            logger.warning("Slack API error for channel '%s': %s", slack_channel, result.get("error", "unknown"))

    except requests.exceptions.RequestException as exc:
        logger.error("Failed to send Slack message: %s", exc)
        raise