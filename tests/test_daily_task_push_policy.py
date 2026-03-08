from unittest.mock import patch

from main import run_daily_task
from src.ai_filter import FilterResult
from src.github_scraper import TrendingProject


def _config() -> dict:
    return {
        "ai": {
            "base_url": "https://gmn.chuangzuoli.com",
            "api_key": "sk-test",
            "model": "gpt-5.4",
        },
        "wecom": {
            "webhook_url": "https://example.com/webhook",
        },
        "logging": {
            "file": "logs/test.log",
            "level": "INFO",
        },
    }


def _ai_project(repo_name: str = "org/repo") -> tuple[TrendingProject, FilterResult]:
    project = TrendingProject(
        repo_name=repo_name,
        description="AI project",
        language="Python",
        url=f"https://github.com/{repo_name}",
        stars=1000,
        stars_growth=100,
        ranking=1,
    )
    return project, FilterResult(is_ai_related=True, reason="reason")


@patch("main.Database")
@patch("main.GitHubScraper")
@patch("main.AIFilter")
@patch("main.OpenClawNotifier")
@patch("main.WeComNotifier")
def test_run_daily_task_no_ai_projects_does_not_push(
    mock_notifier_cls,
    mock_openclaw_cls,
    mock_filter_cls,
    mock_scraper_cls,
    mock_db_cls,
):
    mock_db = mock_db_cls.return_value
    mock_db.init_db.return_value = None
    mock_db.close.return_value = None

    mock_scraper = mock_scraper_cls.return_value
    mock_scraper.fetch_trending.side_effect = [[], []]

    mock_filter = mock_filter_cls.return_value
    mock_filter.batch_filter.return_value = []
    mock_filter.last_filter_had_llm_failure = False
    mock_filter.last_summary_had_llm_failure = False

    notifier = mock_notifier_cls.return_value
    mock_openclaw_cls.from_config.return_value.is_enabled = False

    run_daily_task(_config(), dry_run=False)

    notifier.send_markdown.assert_not_called()
    notifier.send_daily_report_split.assert_not_called()


@patch("main.Database")
@patch("main.GitHubScraper")
@patch("main.AIFilter")
@patch("main.OpenClawNotifier")
@patch("main.WeComNotifier")
def test_run_daily_task_filter_llm_fallback_still_pushes(
    mock_notifier_cls,
    mock_openclaw_cls,
    mock_filter_cls,
    mock_scraper_cls,
    mock_db_cls,
):
    mock_db = mock_db_cls.return_value
    mock_db.init_db.return_value = None
    mock_db.close.return_value = None
    mock_db.get_recently_pushed_repo_names.return_value = set()
    mock_db.save_project.return_value = 1
    mock_db.save_trend_record.return_value = 1

    mock_scraper = mock_scraper_cls.return_value
    mock_scraper.fetch_trending.side_effect = [[], []]

    mock_filter = mock_filter_cls.return_value
    mock_filter.batch_filter.return_value = [_ai_project("org/repo-a")]
    mock_filter.last_filter_had_llm_failure = True
    mock_filter.last_summary_had_llm_failure = False
    mock_filter.generate_daily_summary.return_value = "summary from fallback-filtered projects"

    notifier = mock_notifier_cls.return_value
    notifier.send_daily_report_split.return_value = True
    mock_openclaw_cls.from_config.return_value.is_enabled = False

    run_daily_task(_config(), dry_run=False)

    notifier.send_markdown.assert_not_called()
    notifier.send_daily_report_split.assert_called_once()
    mock_db.save_daily_push_records.assert_called_once()


@patch("main.Database")
@patch("main.GitHubScraper")
@patch("main.AIFilter")
@patch("main.OpenClawNotifier")
@patch("main.WeComNotifier")
def test_run_daily_task_summary_llm_fallback_still_pushes(
    mock_notifier_cls,
    mock_openclaw_cls,
    mock_filter_cls,
    mock_scraper_cls,
    mock_db_cls,
):
    mock_db = mock_db_cls.return_value
    mock_db.init_db.return_value = None
    mock_db.close.return_value = None
    mock_db.get_recently_pushed_repo_names.return_value = set()
    mock_db.save_project.return_value = 1
    mock_db.save_trend_record.return_value = 1

    mock_scraper = mock_scraper_cls.return_value
    mock_scraper.fetch_trending.side_effect = [[], []]

    mock_filter = mock_filter_cls.return_value
    mock_filter.batch_filter.return_value = [_ai_project("org/repo-a")]
    mock_filter.last_filter_had_llm_failure = False
    mock_filter.last_summary_had_llm_failure = True
    mock_filter.generate_daily_summary.return_value = "fallback summary"

    notifier = mock_notifier_cls.return_value
    notifier.send_daily_report_split.return_value = True
    mock_openclaw_cls.from_config.return_value.is_enabled = False

    run_daily_task(_config(), dry_run=False)

    notifier.send_markdown.assert_not_called()
    notifier.send_daily_report_split.assert_called_once()
    mock_db.save_daily_push_records.assert_called_once()


@patch("main.Database")
@patch("main.GitHubScraper")
@patch("main.AIFilter")
@patch("main.OpenClawNotifier")
@patch("main.WeComNotifier")
def test_run_daily_task_sends_markdown_attachment_via_openclaw_when_enabled(
    mock_notifier_cls,
    mock_openclaw_cls,
    mock_filter_cls,
    mock_scraper_cls,
    mock_db_cls,
):
    mock_db = mock_db_cls.return_value
    mock_db.init_db.return_value = None
    mock_db.close.return_value = None
    mock_db.get_recently_pushed_repo_names.return_value = set()
    mock_db.save_project.return_value = 1
    mock_db.save_trend_record.return_value = 1

    mock_scraper = mock_scraper_cls.return_value
    mock_scraper.fetch_trending.side_effect = [[], []]

    mock_filter = mock_filter_cls.return_value
    mock_filter.batch_filter.return_value = [_ai_project("org/repo-a")]
    mock_filter.last_filter_had_llm_failure = False
    mock_filter.last_summary_had_llm_failure = False
    mock_filter.generate_daily_summary.return_value = "summary"

    notifier = mock_notifier_cls.return_value
    notifier.send_daily_report_split.return_value = True

    openclaw = mock_openclaw_cls.from_config.return_value
    openclaw.is_enabled = True
    openclaw.send_markdown_file.return_value = True

    run_daily_task({**_config(), "openclaw": {"enabled": True}}, dry_run=False)

    openclaw.send_markdown_file.assert_called_once()
