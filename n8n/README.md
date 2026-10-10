# n8n (optional)

Hermod POSTs every new adherence flag to `N8N_ALERT_WEBHOOK_URL` as JSON
(see `hermod/harness/alerts.py`). Build a workflow in n8n starting with a
**Webhook** node and fan out to Gmail / Slack / Telegram. Export the workflow
JSON into this folder so it lives in git.
