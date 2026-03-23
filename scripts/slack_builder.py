from datetime import date


def build_dashboard_slack_blocks(data: list) -> list[dict]:
    """
    Build a dashboard-style Slack Block Kit report from your environment data.

    Expected per-env attributes:
      - env.env
      - env._errs (dict-like, optional) with keys like '504', '502', 'oom'
      - env.synthetic_results (dict-like, optional)
      - env.filtered_fm_jobs (dict[str, int], optional)
    """

    def get_aggregate(results: dict | None, key: str) -> int:
        if not results:
            return 0

        value = results.get(key)
        if value is None:
            return 0

        if hasattr(value, "aggregate"):
            return value.aggregate

        if isinstance(value, dict):
            return value.get("aggregate", 0)

        return int(value)

    def get_status_icon(env) -> str:
        err_504 = get_aggregate(getattr(env, "_errs", None), "504")
        err_502 = get_aggregate(getattr(env, "_errs", None), "502")
        err_oom = get_aggregate(getattr(env, "_errs", None), "oom")
        threshold_504 = getattr(env, "err_504_threshold", 0)
        threshold_502 = getattr(env, "err_502_threshold", 0)
        threshold_oom = getattr(env, "err_oom_threshold", 0)
        fm_jobs = getattr(env, "filtered_fm_jobs", {}) or {}

        total_fm_failures = sum(fm_jobs.values())

        if err_504 > threshold_504 or err_502 > threshold_502 or err_oom > threshold_oom or total_fm_failures:
            return "🔴"
        elif err_504 <= threshold_504 and err_502 <= threshold_502 and err_oom <= threshold_oom:
            return "🟡"
        return "🟢"

    def build_summary_line(env) -> str:
        env_name = getattr(env, "env", "Unknown")
        err_504 = get_aggregate(getattr(env, "_errs", None), "504")
        err_502 = get_aggregate(getattr(env, "_errs", None), "502")
        err_oom = get_aggregate(getattr(env, "_errs", None), "oom")
        threshold_504 = getattr(env, "err_504_threshold", 0)
        threshold_502 = getattr(env, "err_502_threshold", 0)
        threshold_oom = getattr(env, "err_oom_threshold", 0)
        fm_jobs = getattr(env, "filtered_fm_jobs", {}) or {}

        parts = []
        if err_504 >= threshold_504:
            parts.append(f"504: {err_504}")
        if err_502 >= threshold_502:
            parts.append(f"502: {err_502}")
        if err_oom >= threshold_oom:
            parts.append(f"oom: {err_oom}")

        total_fm_failures = sum(fm_jobs.values())
        if total_fm_failures:
            parts.append(f"filemover: {total_fm_failures}")

        if not parts:
            parts.append("no issues")

        return f"{get_status_icon(env)} *{env_name}* — " + ", ".join(parts)

    def build_env_fields(env) -> list[dict]:
        err_504 = get_aggregate(getattr(env, "_errs", None), "504")
        err_502 = get_aggregate(getattr(env, "_errs", None), "502")
        err_oom = get_aggregate(getattr(env, "_errs", None), "oom")

        synthetic_results = getattr(env, "synthetic_results", None) or {}
        synthetic_text = "—"
        if synthetic_results:
            synthetic_parts = []
            for _, result in synthetic_results.items():
                name = getattr(result, "name", "unknown")
                failure_count = getattr(result, "failure_count", 0)
                icon = "✅" if failure_count == 0 else "🔴"
                synthetic_parts.append(f"`{name}` ({failure_count}) {icon} ")
            synthetic_text = "\n".join(synthetic_parts)

        return [
            {"type": "mrkdwn", "text": f"*504:* {err_504}\n *502:* {err_502}\n *oom:* {err_oom}"},
            {"type": "mrkdwn", "text": f"*Synthetic:*{synthetic_text}"},
        ]

    def build_filemover_context(env) -> dict | None:
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

    issue_envs = []
    healthy_envs = []

    for env in data:
        if get_status_icon(env) == "🔴":
            issue_envs.append(env)
        else:
            healthy_envs.append(env)

    blocks = []

    blocks.append(
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"📊 Business Day Infra Report — {date.today().strftime('%Y-%m-%d')}",
            },
        }
    )

    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": (
                        f"*{date.today()}* • "
                        f"{len(data)} environments • "
                        f"{len(issue_envs)} environments with issues"
                    ),
                }
            ],
        }
    )

    if issue_envs:
        summary_lines = [build_summary_line(env) for env in issue_envs]
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Needs attention*\n" + "\n".join(summary_lines),
                },
            }
        )

    if healthy_envs:
        healthy_names = ", ".join(f"*{getattr(env, 'env', 'Unknown')}*" for env in healthy_envs)
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Healthy*\n🟢 {healthy_names}",
                },
            }
        )

    if issue_envs:
        blocks.append({"type": "divider"})

    for i, env in enumerate(issue_envs):
        env_name = getattr(env, "env", "Unknown")

        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"{get_status_icon(env)} *{env_name}*"},
                "fields": build_env_fields(env),
            }
        )

        fm_context = build_filemover_context(env)
        if fm_context:
            blocks.append(fm_context)

        # Optional: add action buttons when you have real URLs
        # blocks.append(
        #     {
        #         "type": "actions",
        #         "elements": [
        #             {
        #                 "type": "button",
        #                 "text": {"type": "plain_text", "text": "Open dashboard"},
        #                 "url": "https://your-dashboard-url",
        #             },
        #             {
        #                 "type": "button",
        #                 "text": {"type": "plain_text", "text": "Runbook"},
        #                 "url": "https://your-runbook-url",
        #             },
        #         ],
        #     }
        # )

        if i < len(issue_envs) - 1:
            blocks.append({"type": "divider"})

    return blocks