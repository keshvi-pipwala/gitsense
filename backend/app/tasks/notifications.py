import smtplib
import json
import urllib.request
import urllib.error
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone
from typing import Optional
from app.core.config import settings
from app.core.logging import get_logger
from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.db.models import PullRequest, Notification

logger = get_logger(__name__)

RISK_COLORS = {
    "LOW": "#22c55e",
    "MEDIUM": "#eab308",
    "HIGH": "#ef4444",
    "CRITICAL": "#7f1d1d",
}

RISK_EMOJI = {
    "LOW": "🟢",
    "MEDIUM": "🟡",
    "HIGH": "🔴",
    "CRITICAL": "🚨",
}


def send_slack_notification(pr_db: PullRequest) -> bool:
    if not settings.SLACK_ENABLED or not settings.SLACK_WEBHOOK_URL:
        return False

    analysis = pr_db.analysis_json or {}
    risk = pr_db.risk_level.value if pr_db.risk_level else "UNKNOWN"
    emoji = RISK_EMOJI.get(risk, "⚪")
    color = RISK_COLORS.get(risk, "#6b7280")
    dashboard_url = f"{settings.FRONTEND_URL}/pr/{pr_db.id}"
    recs = analysis.get("recommendations", [])[:3]

    payload = {
        "attachments": [
            {
                "color": color,
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"{emoji} GitSense Alert: {risk} Risk PR Detected",
                        },
                    },
                    {
                        "type": "section",
                        "fields": [
                            {"type": "mrkdwn", "text": f"*PR:*\n<{pr_db.github_pr_url}|#{pr_db.github_pr_number}: {pr_db.title[:60]}>"},
                            {"type": "mrkdwn", "text": f"*Author:*\n@{pr_db.author}"},
                            {"type": "mrkdwn", "text": f"*Risk Level:*\n*{risk}*"},
                            {"type": "mrkdwn", "text": f"*Debt Score:*\n{pr_db.debt_score or 0:.0f}/100"},
                            {"type": "mrkdwn", "text": f"*Blast Radius:*\n{pr_db.blast_radius_count or 0} modules"},
                            {"type": "mrkdwn", "text": f"*Files Changed:*\n{pr_db.files_changed or 0}"},
                        ],
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Summary:*\n{analysis.get('summary', 'N/A')}",
                        },
                    },
                ],
            }
        ]
    }

    if recs:
        payload["attachments"][0]["blocks"].append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Top Recommendations:*\n" + "\n".join(f"• {r}" for r in recs),
            },
        })

    payload["attachments"][0]["blocks"].append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "View Full Analysis"},
                "url": dashboard_url,
                "style": "primary",
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "View PR on GitHub"},
                "url": pr_db.github_pr_url,
            },
        ],
    })

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            settings.SLACK_WEBHOOK_URL,
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                logger.info(f"Slack notification sent for PR #{pr_db.github_pr_number}")
                return True
    except urllib.error.URLError as e:
        logger.error(f"Slack notification failed: {e}")
    return False


def send_email_notification(pr_db: PullRequest) -> bool:
    if not settings.EMAIL_ENABLED or not all([
        settings.SMTP_HOST, settings.SMTP_USER,
        settings.SMTP_PASSWORD, settings.SMTP_FROM
    ]):
        return False

    analysis = pr_db.analysis_json or {}
    risk = pr_db.risk_level.value if pr_db.risk_level else "UNKNOWN"
    emoji = RISK_EMOJI.get(risk, "⚪")
    color = RISK_COLORS.get(risk, "#6b7280")
    dashboard_url = f"{settings.FRONTEND_URL}/pr/{pr_db.id}"

    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f172a; color: #e2e8f0; padding: 20px; margin: 0;">
<div style="max-width: 600px; margin: 0 auto; background: #1e293b; border-radius: 12px; overflow: hidden; border: 1px solid #334155;">
  <div style="background: {color}; padding: 20px 24px;">
    <h1 style="margin: 0; color: white; font-size: 20px;">{emoji} GitSense Alert: {risk} Risk PR</h1>
  </div>
  <div style="padding: 24px;">
    <h2 style="color: #f1f5f9; margin-top: 0;">
      <a href="{pr_db.github_pr_url}" style="color: #818cf8; text-decoration: none;">PR #{pr_db.github_pr_number}: {pr_db.title}</a>
    </h2>
    <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
      <tr>
        <td style="padding: 8px; color: #94a3b8; border-bottom: 1px solid #334155;">Author</td>
        <td style="padding: 8px; color: #e2e8f0; border-bottom: 1px solid #334155;"><strong>@{pr_db.author}</strong></td>
      </tr>
      <tr>
        <td style="padding: 8px; color: #94a3b8; border-bottom: 1px solid #334155;">Risk Level</td>
        <td style="padding: 8px; border-bottom: 1px solid #334155;"><strong style="color: {color};">{risk}</strong></td>
      </tr>
      <tr>
        <td style="padding: 8px; color: #94a3b8; border-bottom: 1px solid #334155;">Debt Score</td>
        <td style="padding: 8px; color: #e2e8f0; border-bottom: 1px solid #334155;">{pr_db.debt_score or 0:.0f}/100</td>
      </tr>
      <tr>
        <td style="padding: 8px; color: #94a3b8;">Blast Radius</td>
        <td style="padding: 8px; color: #e2e8f0;">{pr_db.blast_radius_count or 0} modules</td>
      </tr>
    </table>

    <h3 style="color: #f1f5f9;">Summary</h3>
    <p style="color: #cbd5e1; line-height: 1.6;">{analysis.get('summary', 'N/A')}</p>

    <h3 style="color: #f1f5f9;">Recommendations</h3>
    <ul style="color: #cbd5e1; line-height: 1.8; padding-left: 20px;">
      {"".join(f'<li>{r}</li>' for r in analysis.get('recommendations', [])[:5])}
    </ul>

    {"<h3 style='color: #f1f5f9;'>⚠️ Breaking Changes</h3><ul style='color: #fca5a5; line-height: 1.8; padding-left: 20px;'>" + "".join(f'<li>{b}</li>' for b in analysis.get('breaking_changes', [])) + "</ul>" if analysis.get('breaking_changes') else ""}

    <div style="margin-top: 24px; text-align: center;">
      <a href="{dashboard_url}" style="background: #4f46e5; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; margin-right: 12px; font-weight: 600;">View Full Analysis</a>
      <a href="{pr_db.github_pr_url}" style="background: #1e293b; color: #818cf8; padding: 12px 24px; border-radius: 8px; text-decoration: none; border: 1px solid #4f46e5; font-weight: 600;">View on GitHub</a>
    </div>
  </div>
  <div style="padding: 16px 24px; border-top: 1px solid #334155; text-align: center;">
    <p style="color: #475569; font-size: 12px; margin: 0;">🤖 GitSense — Autonomous Codebase Intelligence</p>
  </div>
</div>
</body>
</html>
"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"{emoji} [{risk}] PR #{pr_db.github_pr_number}: {pr_db.title[:60]}"
    msg["From"] = settings.SMTP_FROM
    msg["To"] = settings.SMTP_USER
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
        logger.info(f"Email notification sent for PR #{pr_db.github_pr_number}")
        return True
    except Exception as e:
        logger.error(f"Email notification failed: {e}")
        return False


@celery_app.task(name="app.tasks.notifications.send_notifications")
def send_notifications(pr_db_id: int):
    """Send Slack and email notifications for high-risk PRs."""
    db = SessionLocal()
    try:
        pr_db = db.query(PullRequest).filter(PullRequest.id == pr_db_id).first()
        if not pr_db:
            return

        analysis = pr_db.analysis_json or {}
        content_summary = json.dumps({
            "risk": pr_db.risk_level.value if pr_db.risk_level else "UNKNOWN",
            "summary": analysis.get("summary", ""),
            "recommendations": analysis.get("recommendations", [])[:3],
        })

        # Slack
        slack_ok = send_slack_notification(pr_db)
        db.add(Notification(
            pr_id=pr_db_id,
            channel="slack",
            content=content_summary,
            success=slack_ok,
            error_message=None if slack_ok else "Slack delivery failed",
        ))

        # Email
        email_ok = send_email_notification(pr_db)
        db.add(Notification(
            pr_id=pr_db_id,
            channel="email",
            content=content_summary,
            success=email_ok,
            error_message=None if email_ok else "Email delivery failed or not configured",
        ))

        db.commit()
        logger.info(f"Notifications sent for PR {pr_db_id}: slack={slack_ok}, email={email_ok}")

    except Exception as e:
        logger.error(f"Failed to send notifications for PR {pr_db_id}: {e}")
    finally:
        db.close()
