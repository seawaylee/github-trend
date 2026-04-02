from datetime import date

from main import merge_trending_projects, select_daily_projects_for_push
from src.ai_filter import FilterResult
from src.github_scraper import TrendingProject


class FakeDB:
    def __init__(self, pushed):
        self._pushed = pushed

    def get_recently_pushed_repo_names(self, lookback_days: int, reference_date: date):
        return self._pushed


def _make_project(
    repo_name: str,
    stars_growth: int,
    description: str = "desc",
    category: str = "general_ai",
):
    return (
        TrendingProject(
            repo_name=repo_name,
            description=description,
            language="Python",
            url=f"https://github.com/{repo_name}",
            stars=1000,
            stars_growth=stars_growth,
            ranking=1
        ),
        FilterResult(is_ai_related=True, reason="reason", category=category)
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


def test_select_daily_projects_keeps_tooling_signal_visible_when_available():
    ai_projects = [
        _make_project(f"a/repo{i}", 600 - i * 10)
        for i in range(1, 11)
    ] + [
        _make_project(
            "jackwener/opencli",
            120,
            description="AI-native runtime for AI agents",
            category="ai_native_tooling",
        ),
        _make_project(
            "some/cli-everything",
            110,
            description="Agent workflow bridge for tools",
            category="agent_workflow",
        ),
    ]
    db = FakeDB(set())

    selected = select_daily_projects_for_push(
        ai_projects=ai_projects,
        db=db,
        today=date(2026, 2, 12)
    )

    repo_names = [project.repo_name for project, _ in selected]
    assert len(selected) == 10
    assert "jackwener/opencli" in repo_names
    assert "some/cli-everything" in repo_names



def test_merge_trending_projects_deduplicates_repo_names_and_keeps_daily_version():
    daily_projects = [
        TrendingProject(
            repo_name="a/shared",
            description="daily desc",
            language="Python",
            url="https://github.com/a/shared",
            stars=1000,
            stars_growth=200,
            ranking=2
        ),
        TrendingProject(
            repo_name="a/daily-only",
            description="daily only",
            language="Python",
            url="https://github.com/a/daily-only",
            stars=900,
            stars_growth=180,
            ranking=4
        ),
    ]
    weekly_projects = [
        TrendingProject(
            repo_name="a/shared",
            description="weekly desc",
            language="Python",
            url="https://github.com/a/shared",
            stars=1000,
            stars_growth=1200,
            ranking=1
        ),
        TrendingProject(
            repo_name="a/weekly-only",
            description="weekly only",
            language="Python",
            url="https://github.com/a/weekly-only",
            stars=800,
            stars_growth=700,
            ranking=3
        ),
    ]

    merged = merge_trending_projects(daily_projects, weekly_projects)

    assert [project.repo_name for project in merged] == [
        "a/shared",
        "a/daily-only",
        "a/weekly-only",
    ]
    assert merged[0].stars_growth == 200
    assert merged[0].description == "daily desc"
