import json
import base64
import logging
from typing import List, Dict

import boto3
import requests
import os

logger = logging.getLogger(__name__)

__all__ = ["get_aws_secrets_helper", "send_slack_message", "send_slack_file"]


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


def send_slack_file(file_path: str, slack_channel: str, slack_bot_token: str) -> None:
    """Upload a file to a Slack channel via Slack Web API.

    Logs outcomes; raises on transport-level errors.
    """
    # Step 1: Request an external upload URL from Slack
    filename = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)

    get_url_resp = requests.post(
        "https://slack.com/api/files.getUploadURLExternal",
        headers={"Authorization": f"Bearer {slack_bot_token}"},
        data={"filename": filename, "length": str(file_size)},
        timeout=15,
    )
    get_url_resp.raise_for_status()
    get_url_data = get_url_resp.json()
    if not get_url_data.get("ok"):
        logger.error("files.getUploadURLExternal failed: %s", get_url_data)
        raise RuntimeError(f"files.getUploadURLExternal failed: {get_url_data.get('error')}")

    upload_url = get_url_data.get("upload_url")
    file_id = get_url_data.get("file_id")
    if not upload_url or not file_id:
        raise RuntimeError("files.getUploadURLExternal did not return upload_url or file_id")

    # Step 2: PUT the raw file bytes to the provided upload_url
    with open(file_path, "rb") as fh:
        put_headers = {"Content-Type": "application/octet-stream"}
        put_resp = requests.post(upload_url, headers=put_headers, data=fh, timeout=60)

    # Some endpoints may return plain HTTP 200 with body 'OK - <length>'
    if put_resp.status_code < 200 or put_resp.status_code >= 300:
        logger.error("Upload to external URL failed: status=%s, body=%s", put_resp.status_code, put_resp.text)
        raise RuntimeError(f"Upload to external URL failed: status={put_resp.status_code}")

    # Step 3: Tell Slack the upload is complete and share it to a channel
    files_payload = json.dumps([{"id": file_id, "title": filename}])
    complete_resp = requests.post(
        "https://slack.com/api/files.completeUploadExternal",
        headers={"Authorization": f"Bearer {slack_bot_token}"},
        data={
            "files": files_payload,
            "channel_id": slack_channel if slack_channel and slack_channel.startswith("C") else None,
            "channels": slack_channel if slack_channel and not slack_channel.startswith("C") else None,
        },
        timeout=15,
    )
    complete_resp.raise_for_status()
    complete_data = complete_resp.json()
    if not complete_data.get("ok"):
        logger.error("files.completeUploadExternal failed: %s", complete_data)
        raise RuntimeError(f"files.completeUploadExternal failed: {complete_data.get('error')}")

    logger.info("Completed external upload of '%s' (file_id=%s) to Slack.", filename, file_id)
    return complete_data