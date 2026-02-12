from datetime import date

from main import select_daily_projects_for_push
from src.ai_filter import FilterResult
from src.github_scraper import TrendingProject


class FakeDB:
    def __init__(self, pushed):
        self._pushed = pushed

    def get_recently_pushed_repo_names(self, lookback_days: int, reference_date: date):
        return self._pushed


def _make_project(repo_name: str, stars_growth: int):
    return (
        TrendingProject(
            repo_name=repo_name,
            description="desc",
            language="Python",
            url=f"https://github.com/{repo_name}",
            stars=1000,
            stars_growth=stars_growth,
            ranking=1
        ),
        FilterResult(is_ai_related=True, reason="reason")
    )


def test_select_daily_projects_filters_recently_pushed_and_limits_top5():
    ai_projects = [
        _make_project("a/repo1", 500),
        _make_project("a/repo2", 490),
        _make_project("a/repo3", 480),
        _make_project("a/repo4", 470),
        _make_project("a/repo5", 460),
        _make_project("a/repo6", 450),
        _make_project("a/repo7", 440),
    ]
    db = FakeDB({"a/repo2", "a/repo4"})

    selected = select_daily_projects_for_push(
        ai_projects=ai_projects,
        db=db,
        today=date(2026, 2, 12)
    )

    repo_names = [project.repo_name for project, _ in selected]
    assert len(selected) == 5
    assert "a/repo2" not in repo_names
    assert "a/repo4" not in repo_names
    assert repo_names == ["a/repo1", "a/repo3", "a/repo5", "a/repo6", "a/repo7"]
