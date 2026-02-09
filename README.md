# GitHub AI Trend Tracker

An automated tool that tracks trending GitHub repositories, filters for AI-related content using LLMs, and pushes daily/weekly updates to WeCom (Enterprise WeChat).

## Features

- **Daily Trends**: Fetches top trending repositories daily and pushes the top 5 AI-related projects.
- **Weekly Summary**: Generates a weekly summary of the top 25 AI projects every Friday.
- **AI Filtering**: Uses a local LLM service (OpenAI API compatible) to analyze repository descriptions and READMEs to identify genuine AI projects.
- **Automated Reporting**: Sends formatted reports directly to WeCom group chats via Webhook.

## Prerequisites

- Python 3.9 or higher
- Access to an LLM service (OpenAI API compatible endpoint)
- WeCom Webhook URL for notifications

## Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd github-trend
   ```

2. **Set up the environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Configuration**
   Copy the example configuration and edit it:
   ```bash
   cp config/config.example.yaml config/config.yaml
   nano config/config.yaml
   ```

4. **Initialize Database**
   ```bash
   python main.py --init-db
   ```

5. **Run**
   ```bash
   # Daily run (dry-run mode for testing)
   python main.py --dry-run

   # Install cron jobs
   ./setup.sh install
   ```

## Configuration Guide

Edit `config/config.yaml` to match your environment:

### AI Service
- `base_url`: URL of your LLM service (e.g., `http://127.0.0.1:8045` for local models)
- `api_key`: API Key for the service
- `model`: Model name to use (e.g., `gemini-3-pro-high`)

### WeCom
- `webhook_url`: The Webhook URL provided by WeCom bot

### Tasks
- `daily_limit`: Number of repos to report daily (default: 5)
- `weekly_limit`: Number of repos to report weekly (default: 25)
- `daily_hour`: Hour to run daily check (0-23)
- `weekly_day`: Day of week for weekly report (5 = Friday)

## Manual Usage

You can run the scripts manually for testing or ad-hoc reports:

```bash
# Run daily trend check immediately
python main.py

# Run daily check without sending notification (Dry Run)
python main.py --dry-run

# Run weekly summary immediately
python weekly.py

# Run weekly summary without sending notification
python weekly.py --dry-run
```

## Troubleshooting

- **"Connection refused"**:
  - Ensure your local LLM service is running and accessible at the `base_url` specified in config.

- **"No AI projects found"**:
  - Check if your LLM API key is valid.
  - Verify the model name is correct.
  - Check `logs/app.log` for API error messages.

- **"WeCom send failed"**:
  - Verify the `webhook_url` is correct.
  - Ensure the machine has internet access to reach WeChat servers.

## Logs

Application logs are stored in the `logs/` directory:
- `logs/app.log`: Main application log file containing execution details and errors.
