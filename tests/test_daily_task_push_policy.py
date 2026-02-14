from unittest.mock import patch

from main import run_daily_task
from src.ai_filter import FilterResult
from src.github_scraper import TrendingProject


def _config() -> dict:
    return {
        "ai": {
            "base_url": "http://localhost:8045",
            "api_key": "sk-test",
            "model": "gemini-3-pro-high",
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
@patch("main.WeComNotifier")
def test_run_daily_task_no_ai_projects_does_not_push(
    mock_notifier_cls,
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

    run_daily_task(_config(), dry_run=False)

    notifier.send_markdown.assert_not_called()
    notifier.send_daily_report_split.assert_not_called()


@patch("main.Database")
@patch("main.GitHubScraper")
@patch("main.AIFilter")
@patch("main.WeComNotifier")
def test_run_daily_task_filter_llm_failure_does_not_push(
    mock_notifier_cls,
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
    mock_filter.batch_filter.return_value = [_ai_project("org/repo-a")]
    mock_filter.last_filter_had_llm_failure = True
    mock_filter.last_summary_had_llm_failure = False

    notifier = mock_notifier_cls.return_value

    run_daily_task(_config(), dry_run=False)

    notifier.send_markdown.assert_not_called()
    notifier.send_daily_report_split.assert_not_called()


@patch("main.Database")
@patch("main.GitHubScraper")
@patch("main.AIFilter")
@patch("main.WeComNotifier")
def test_run_daily_task_summary_llm_failure_does_not_push(
    mock_notifier_cls,
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

    run_daily_task(_config(), dry_run=False)

    notifier.send_markdown.assert_not_called()
    notifier.send_daily_report_split.assert_not_called()
