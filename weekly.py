#!/usr/bin/env python3
"""Weekly report script"""
import sys
import argparse
import logging
from datetime import date, timedelta
from pathlib import Path

from src.config_loader import load_config, ConfigError
from src.database import Database
from src.weekly_reporter import WeeklyReporter
from src.wecom_notifier import WeComNotifier


def compose_weekly_history(report: str, summary: str) -> str:
    """Compose a single markdown file for local weekly history."""
    footer = "\n---\n⏰ 由GitHub-Trend-Bot自动推送"
    report_without_footer = report.rsplit(footer, 1)[0] if footer in report else report
    summary_without_footer = summary.rsplit(footer, 1)[0] if footer in summary else summary

    return "\n".join([
        report_without_footer,
        "\n---\n",
        summary_without_footer,
        footer
    ])


def setup_logging(config: dict):
    """Setup logging configuration"""
    log_config = config.get('logging', {})
    log_file = log_config.get('file', 'logs/app.log').replace('app.log', 'weekly.log')
    log_level = log_config.get('level', 'INFO')

    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )


def get_week_range(target_date: date = None) -> tuple[date, date]:
    """
    Get week range (Monday to Friday)

    Args:
        target_date: Target date (default: today)

    Returns:
        (week_start, week_end) tuple
    """
    if target_date is None:
        target_date = date.today()

    # Get Monday of the week
    days_since_monday = target_date.weekday()
    week_start = target_date - timedelta(days=days_since_monday)

    # Get Friday of the week
    week_end = week_start + timedelta(days=4)

    return week_start, week_end


def run_weekly_task(config: dict, dry_run: bool = False, week_start: date = None):
    """Run weekly report task"""
    logger = logging.getLogger(__name__)
    logger.info("Starting weekly report task")

    # Get week range
    if week_start:
        week_end = week_start + timedelta(days=4)
    else:
        week_start, week_end = get_week_range()

    logger.info(f"Generating report for {week_start} to {week_end}")

    # Initialize components
    db = Database()
    db.init_db()
    reporter = WeeklyReporter(
        database=db,
        ai_base_url=config['ai']['base_url'],
        ai_api_key=config['ai']['api_key'],
        ai_model=config['ai']['model']
    )
    notifier = WeComNotifier(config['wecom']['webhook_url'])

    try:
        # Generate report
        max_projects = config['tasks']['weekly_limit']
        report_package = reporter.generate_report_package(week_start, week_end, max_projects)
        report = report_package["report"]
        summary = report_package["summary"]

        logger.info("Weekly report generated")

        # Save to history
        history_dir = Path("history")
        history_dir.mkdir(exist_ok=True)
        history_file = history_dir / f"{week_end.isoformat()}-weekly.md"
        history_content = compose_weekly_history(report, summary)

        try:
            with open(history_file, 'w', encoding='utf-8') as f:
                f.write(history_content)
            logger.info(f"✓ Weekly report saved to {history_file}")
        except Exception as e:
            logger.error(f"Failed to save history: {e}")

        if dry_run:
            trend_message, summary_message = notifier.format_weekly_push_messages(
                report,
                week_start,
                week_end,
                summary
            )
            print("\n🔍 DRY RUN - Weekly trend message:\n")
            print(trend_message)
            print("\n🔍 DRY RUN - Weekly summary message:\n")
            print(summary_message)
        else:
            success = notifier.send_weekly_report_split(
                report,
                week_start,
                week_end,
                summary
            )
            if success:
                logger.info("✓ Weekly split report sent successfully")
            else:
                logger.error("✗ Failed to send split weekly report")

    except Exception as e:
        logger.error(f"Weekly task failed: {e}", exc_info=True)
        if not dry_run:
            notifier.send_markdown(f"⚠️ 周报生成失败：{str(e)}")
        raise

    finally:
        db.close()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='GitHub AI Trend Tracker - Weekly Report')
    parser.add_argument('--config', default='config/config.yaml', help='Config file path')
    parser.add_argument('--dry-run', action='store_true', help='Run without sending notifications')
    parser.add_argument('--week-start', help='Week start date (YYYY-MM-DD), default: this week Monday')

    args = parser.parse_args()

    # Parse week start
    week_start = None
    if args.week_start:
        try:
            week_start = date.fromisoformat(args.week_start)
        except ValueError:
            print(f"❌ Invalid date format: {args.week_start}", file=sys.stderr)
            return 1

    # Load config
    try:
        config = load_config(args.config)
    except ConfigError as e:
        print(f"❌ Config error: {e}", file=sys.stderr)
        return 1

    # Setup logging
    setup_logging(config)

    # Run weekly task
    try:
        run_weekly_task(config, dry_run=args.dry_run, week_start=week_start)
        return 0
    except Exception:
        return 1


if __name__ == '__main__':
    sys.exit(main())
