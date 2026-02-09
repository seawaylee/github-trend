import pytest
from unittest.mock import Mock, patch
from src.wecom_notifier import WeComNotifier
from src.github_scraper import TrendingProject
from src.ai_filter import FilterResult
from datetime import date


@pytest.fixture
def mock_requests():
    """Mock requests library"""
    with patch('src.wecom_notifier.requests') as mock:
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"errcode": 0, "errmsg": "ok"}
        mock.post.return_value = response
        yield mock


def test_format_daily_message():
    """Test formatting daily message"""
    notifier = WeComNotifier("https://test.webhook.url")

    projects_with_reasons = [
        (
            TrendingProject(
                repo_name="test/ml-lib",
                description="Machine learning library",
                language="Python",
                url="https://github.com/test/ml-lib",
                stars=1000,
                stars_growth=100,
                ranking=1
            ),
            FilterResult(is_ai_related=True, reason="Uses ML algorithms")
        )
    ]

    message = notifier._format_daily_message(projects_with_reasons, date(2026, 2, 9))

    assert "GitHub AI趋势" in message
    assert "2026-02-09" in message
    assert "test/ml-lib" in message
    assert "⭐ 1,000" in message
    assert "+100" in message


def test_send_notification(mock_requests):
    """Test sending notification"""
    notifier = WeComNotifier("https://test.webhook.url")

    success = notifier.send_markdown("Test message")

    assert success is True
    mock_requests.post.assert_called_once()

    call_args = mock_requests.post.call_args
    assert call_args[0][0] == "https://test.webhook.url"
    assert call_args[1]['json']['msgtype'] == 'markdown'
