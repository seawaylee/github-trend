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
from src.openclaw_notifier import OpenClawNotifier
from src.wecom_notifier import WeComNotifier

DAILY_PUSH_LIMIT = 10
RECENT_PUSH_LOOKBACK_DAYS = 7
DAILY_TOOLING_FLOOR = 2
TOOLING_PRIORITY_CATEGORIES = {"ai_native_tooling", "agent_workflow"}


def _notify_agent_llm_failure(
    openclaw_notifier: OpenClawNotifier,
    today: date,
    stage: str,
) -> None:
    message = (
        "⚠️ GitHub Trend 本次未推送\n"
        f"日期：{today.isoformat()}\n"
        f"阶段：{stage}\n"
        "原因：LLM 调用失败，已按策略停止推送。\n"
        "请检查 GMN Responses API、API Key 与服务状态。"
    )
    if not openclaw_notifier.is_enabled:
        logging.getLogger(__name__).warning(
            "OpenClaw notifier disabled, cannot notify agent about LLM failure"
        )
        return
    if openclaw_notifier.send_message(message):
        logging.getLogger(__name__).info("✓ Agent notified about LLM failure")
    else:
        logging.getLogger(__name__).error("✗ Failed to notify agent about LLM failure")


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


def merge_trending_projects(*project_lists):
    """Merge multiple trending lists and keep the first occurrence of each repo."""
    merged = []
    seen_repo_names = set()

    for projects in project_lists:
        for project in projects:
            if project.repo_name in seen_repo_names:
                continue
            seen_repo_names.add(project.repo_name)
            merged.append(project)

    return merged


def run_daily_task(config: dict, dry_run: bool = False):
    """Run daily trending task"""
    logger = logging.getLogger(__name__)
    logger.info("Starting daily task")

    # Initialize components
    db = Database()
    db.init_db()

    # safe get github token
    github_config = config.get('github', {})
    scraper = GitHubScraper(
        github_token=github_config.get('token'),
        request_timeout=github_config.get('request_timeout', 60),
    )

    ai_filter = AIFilter(
        base_url=config['ai']['base_url'],
        api_key=config['ai']['api_key'],
        model=config['ai']['model'],
        timeout=config['ai'].get('timeout', 30),
        max_retries=config['ai'].get('max_retries', 1),
    )
    notifier = WeComNotifier(config['wecom']['webhook_url'])
    openclaw_notifier = OpenClawNotifier.from_config(config.get('openclaw'))
    today = date.today()

    try:
        # Fetch trending projects
        logger.info("Fetching daily trending...")
        daily_projects = scraper.fetch_trending('daily')

        logger.info("Fetching weekly trending...")
        weekly_projects = scraper.fetch_trending('weekly')

        all_projects = merge_trending_projects(daily_projects, weekly_projects)
        logger.info(
            "Total projects fetched: %s unique (%s daily + %s weekly)",
            len(all_projects),
            len(daily_projects),
            len(weekly_projects)
        )

        # Filter AI projects
        logger.info("Filtering AI-related projects...")
        ai_projects = ai_filter.batch_filter(all_projects)
        logger.info(f"Found {len(ai_projects)} AI-related projects")

        if ai_filter.last_filter_had_llm_failure:
            logger.warning("LLM filter failed in this run, stop push and notify agent")
            if not dry_run:
                _notify_agent_llm_failure(openclaw_notifier, today, "AI过滤")
            return

        if not ai_projects:
            logger.warning("No AI projects found today, skip push")
            return

        # Select Top5 while excluding repos pushed in last 7 days.
        top_projects = select_daily_projects_for_push(ai_projects, db, today)
        logger.info(
            "Selected %s projects for push (Top%s, excluding last %s days)",
            len(top_projects),
            DAILY_PUSH_LIMIT,
            RECENT_PUSH_LOOKBACK_DAYS
        )

        if not top_projects:
            logger.warning("No new projects to push after 7-day de-duplication, skip push")
            return

        # Generate per-project deep analysis
        logger.info("Generating per-project deep analysis...")
        analysis_map = ai_filter.analyze_projects(top_projects)

        # Save to database
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

        # Generate summary
        logger.info("Generating daily summary and business analysis...")
        summary = ai_filter.generate_daily_summary(top_projects)
        if not summary or not summary.strip():
            logger.warning("Daily summary is empty, skip push")
            return
        if ai_filter.last_summary_had_llm_failure:
            logger.warning("LLM summary failed in this run, stop push and notify agent")
            if not dry_run:
                _notify_agent_llm_failure(openclaw_notifier, today, "总结生成")
            return

        ai_result_by_repo = {project.repo_name: result for project, result in ai_projects}
        weekly_ranked = [
            (project, ai_result_by_repo[project.repo_name])
            for project in weekly_projects
            if project.repo_name in ai_result_by_repo
        ]

        logger.info("Fetching monthly trending for local markdown appendix...")
        monthly_projects = scraper.fetch_trending('monthly')
        monthly_ranked = []
        if monthly_projects:
            logger.info("Filtering monthly AI-related projects for local markdown appendix...")
            monthly_filter = AIFilter(
                base_url=config['ai']['base_url'],
                api_key=config['ai']['api_key'],
                model=config['ai']['model'],
                timeout=config['ai'].get('timeout', 30),
                max_retries=config['ai'].get('max_retries', 1),
            )
            monthly_ranked = monthly_filter.batch_filter(monthly_projects)
            logger.info("Found %s AI-related monthly trending projects for appendix", len(monthly_ranked))

        # Generate report content
        report_content = notifier.format_daily_report(
            top_projects,
            today,
            summary,
            weekly_references=weekly_ranked,
            monthly_references=monthly_ranked,
            analysis_map=analysis_map,
        )

        # Save to history
        history_dir = Path("history")
        history_dir.mkdir(exist_ok=True)
        history_file = history_dir / f"{today.isoformat()}-daily.md"

        try:
            with open(history_file, 'w', encoding='utf-8') as f:
                f.write(report_content)
            logger.info(f"✓ Daily report saved to {history_file}")
        except Exception as e:
            logger.error(f"Failed to save history: {e}")

        logger.info(f"Sending top {len(top_projects)} projects and summary to WeCom")

        if dry_run:
            print("\n🔍 DRY RUN - Would send the following message:\n")
            print(report_content)
            if openclaw_notifier.is_enabled:
                print(f"\n📎 DRY RUN - Would send markdown attachment via OpenClaw: {history_file}")
        else:
            wecom_success = notifier.send_daily_report_split(
                top_projects, today, summary, analysis_map=analysis_map
            )
            if wecom_success:
                pushed_repo_names = [project.repo_name for project, _ in top_projects]
                db.save_daily_push_records(pushed_repo_names, today)
                logger.info("✓ Daily report split sent successfully")
            else:
                logger.error("✗ Failed to send split daily report")

            if openclaw_notifier.is_enabled:
                openclaw_success = openclaw_notifier.send_markdown_file(
                    history_file,
                    title=f"GitHub AI 趋势日报 {today.isoformat()}（自动推送）",
                )
                if openclaw_success:
                    logger.info("✓ Daily markdown attachment sent via OpenClaw")
                else:
                    logger.error("✗ Failed to send daily markdown attachment via OpenClaw")

    except Exception as e:
        logger.error(f"Daily task failed: {e}", exc_info=True)
        if not dry_run:
            try:
                if 'notifier' in locals():
                    notifier.send_markdown(f"⚠️ 每日任务执行失败：{str(e)}")
            except Exception:
                pass
        raise

    finally:
        db.close()


def select_daily_projects_for_push(
    ai_projects: list[tuple],
    db: Database,
    today: date
) -> list[tuple]:
    """Select Top10 daily projects, while giving AI-native tooling enough exposure."""
    recent_pushed = db.get_recently_pushed_repo_names(
        lookback_days=RECENT_PUSH_LOOKBACK_DAYS,
        reference_date=today
    )
    candidates = [
        item for item in ai_projects
        if item[0].repo_name not in recent_pushed
    ]
    if len(candidates) <= DAILY_PUSH_LIMIT:
        return candidates

    selected = candidates[:DAILY_PUSH_LIMIT]

    def is_tooling_item(item: tuple) -> bool:
        _, result = item
        return getattr(result, 'category', '') in TOOLING_PRIORITY_CATEGORIES

    tooling_candidates = [item for item in candidates if is_tooling_item(item)]
    target_tooling_count = min(DAILY_TOOLING_FLOOR, len(tooling_candidates), DAILY_PUSH_LIMIT)
    current_tooling_count = sum(1 for item in selected if is_tooling_item(item))

    if current_tooling_count >= target_tooling_count:
        return selected

    replacement_indexes = [
        idx for idx in range(len(selected) - 1, -1, -1)
        if not is_tooling_item(selected[idx])
    ]
    selected_repo_names = {project.repo_name for project, _ in selected}
    extra_tooling = [
        item for item in candidates[DAILY_PUSH_LIMIT:]
        if is_tooling_item(item) and item[0].repo_name not in selected_repo_names
    ]

    missing = min(
        target_tooling_count - current_tooling_count,
        len(replacement_indexes),
        len(extra_tooling),
    )
    for offset in range(missing):
        selected[replacement_indexes[offset]] = extra_tooling[offset]

    return selected


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
    except Exception as e:
        logging.getLogger(__name__).error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
