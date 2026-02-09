#!/usr/bin/env python3
"""Main script for daily GitHub AI trends"""
import sys
import argparse
import logging
from datetime import date
from pathlib import Path

from src.config_loader import load_config, ConfigError
from src.database import Database
from src.github_scraper import GitHubScraper
from src.ai_filter import AIFilter
from src.wecom_notifier import WeComNotifier


def setup_logging(config: dict):
    """Setup logging configuration"""
    log_config = config.get('logging', {})
    log_file = log_config.get('file', 'logs/app.log')
    log_level = log_config.get('level', 'INFO')

    # Create logs directory
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )


def init_database(db_path: str = "data/trends.db"):
    """Initialize database schema"""
    db = Database(db_path)
    db.init_db()
    print(f"✓ Database initialized at {db_path}")
    db.close()


def show_stats(db_path: str = "data/trends.db"):
    """Show database statistics"""
    db = Database(db_path)
    cursor = db.conn.cursor()

    # Count projects
    cursor.execute("SELECT COUNT(*) FROM projects")
    project_count = cursor.fetchone()[0]

    # Count trend records
    cursor.execute("SELECT COUNT(*) FROM trend_records")
    record_count = cursor.fetchone()[0]

    # Recent records
    cursor.execute("""
        SELECT date, COUNT(*) as count
        FROM trend_records
        GROUP BY date
        ORDER BY date DESC
        LIMIT 7
    """)
    recent = cursor.fetchall()

    print(f"\n📊 Database Statistics")
    print(f"Total projects: {project_count}")
    print(f"Total trend records: {record_count}")
    print(f"\nRecent activity:")
    for row in recent:
        print(f"  {row[0]}: {row[1]} projects")

    db.close()


def run_daily_task(config: dict, dry_run: bool = False):
    """Run daily trending task"""
    logger = logging.getLogger(__name__)
    logger.info("Starting daily task")

    # Initialize components
    db = Database()
    scraper = GitHubScraper(config['github'].get('token'))
    ai_filter = AIFilter(
        base_url=config['ai']['base_url'],
        api_key=config['ai']['api_key'],
        model=config['ai']['model']
    )
    notifier = WeComNotifier(config['wecom']['webhook_url'])

    try:
        # Fetch trending projects
        logger.info("Fetching daily trending...")
        daily_projects = scraper.fetch_trending('daily')

        logger.info("Fetching weekly trending...")
        weekly_projects = scraper.fetch_trending('weekly')

        all_projects = daily_projects + weekly_projects
        logger.info(f"Total projects fetched: {len(all_projects)}")

        # Filter AI projects
        logger.info("Filtering AI-related projects...")
        ai_projects = ai_filter.batch_filter(all_projects)
        logger.info(f"Found {len(ai_projects)} AI-related projects")

        if not ai_projects:
            logger.warning("No AI projects found today")
            if not dry_run:
                notifier.send_markdown("⚠️ 今日未发现AI相关趋势项目")
            return

        # Save to database
        today = date.today()
        for project, filter_result in ai_projects:
            # Save project
            from src.database import Project, TrendRecord

            db_project = Project(
                repo_name=project.repo_name,
                description=project.description,
                language=project.language,
                url=project.url
            )
            project_id = db.save_project(db_project)

            # Save trend record
            record = TrendRecord(
                project_id=project_id,
                date=today,
                stars=project.stars,
                stars_growth=project.stars_growth,
                trend_type='daily',
                ranking=project.ranking,
                ai_relevance_reason=filter_result.reason
            )
            db.save_trend_record(record)

        # Get top N projects
        daily_limit = config['tasks']['daily_limit']
        top_projects = ai_projects[:daily_limit]

        logger.info(f"Sending top {len(top_projects)} projects to WeCom")

        if dry_run:
            print("\n🔍 DRY RUN - Would send the following message:\n")
            message = notifier._format_daily_message(top_projects, today)
            print(message)
        else:
            success = notifier.send_daily_report(top_projects, today)
            if success:
                logger.info("✓ Daily report sent successfully")
            else:
                logger.error("✗ Failed to send daily report")

    except Exception as e:
        logger.error(f"Daily task failed: {e}", exc_info=True)
        if not dry_run:
            notifier.send_markdown(f"⚠️ 每日任务执行失败：{str(e)}")
        raise

    finally:
        db.close()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='GitHub AI Trend Tracker - Daily Task')
    parser.add_argument('--config', default='config/config.yaml', help='Config file path')
    parser.add_argument('--init-db', action='store_true', help='Initialize database')
    parser.add_argument('--stats', action='store_true', help='Show database statistics')
    parser.add_argument('--dry-run', action='store_true', help='Run without sending notifications')

    args = parser.parse_args()

    # Handle database init
    if args.init_db:
        init_database()
        return 0

    # Handle stats
    if args.stats:
        show_stats()
        return 0

    # Load config
    try:
        config = load_config(args.config)
    except ConfigError as e:
        print(f"❌ Config error: {e}", file=sys.stderr)
        return 1

    # Setup logging
    setup_logging(config)

    # Run daily task
    try:
        run_daily_task(config, dry_run=args.dry_run)
        return 0
    except Exception:
        return 1


if __name__ == '__main__':
    sys.exit(main())
