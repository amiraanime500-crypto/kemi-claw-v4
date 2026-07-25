"""Slack alerts and Jira issue creation for critical findings."""
import os

import httpx


async def notify_slack(text: str):
    url = os.getenv("SLACK_WEBHOOK_URL")
    if not url:
        return {"skipped": "no SLACK_WEBHOOK_URL"}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(url, json={"text": text})
        return {"status": r.status_code}


async def create_jira_issue(summary: str, description: str):
    base = os.getenv("JIRA_BASE_URL")
    user = os.getenv("JIRA_USER")
    token = os.getenv("JIRA_TOKEN")
    project = os.getenv("JIRA_PROJECT", "SEC")
    if not all([base, user, token]):
        return {"skipped": "jira not configured"}
    async with httpx.AsyncClient(timeout=30, auth=(user, token)) as c:
        r = await c.post(
            f"{base}/rest/api/2/issue",
            json={
                "fields": {
                    "project": {"key": project},
                    "summary": summary,
                    "description": description,
                    "issuetype": {"name": "Bug"},
                }
            },
        )
        return {"status": r.status_code, "body": r.json()}
