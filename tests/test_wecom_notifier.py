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

    assert "GitHub AI 趋势" in message
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


def test_format_daily_push_messages_split():
    """Test daily push messages are split into trend and summary sections"""
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
    summary = """**每日趋势总结**\n\n趋势总结内容。\n\n🚀 **搜狐业务价值分析**\n\n业务价值内容。"""

    trend_message, summary_message = notifier.format_daily_push_messages(
        projects_with_reasons,
        date(2026, 2, 12),
        summary
    )

    assert "🔥 **今日GitHub AI趋势 Top 1**" in trend_message
    assert "📝 项目描述：Machine learning library" in trend_message
    assert "💡 AI亮点：Uses ML algorithms" in trend_message
    assert "..." not in trend_message
    assert "📝 **AI智能总结 & 业务价值分析**" not in trend_message
    assert "📝 **AI智能总结 & 业务价值分析**" in summary_message
    assert "🚀 **搜狐业务价值分析**" in summary_message


def test_send_daily_report_split(mock_requests):
    """Test sending split daily report to WeCom"""
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
    summary = """**每日趋势总结**\n\n趋势总结内容。\n\n🚀 **搜狐业务价值分析**\n\n业务价值内容。"""

    success = notifier.send_daily_report_split(
        projects_with_reasons,
        date(2026, 2, 12),
        summary
    )

    assert success is True
    assert mock_requests.post.call_count == 2


def test_format_weekly_push_messages_split():
    """Test weekly push messages are split into trend and summary sections"""
    notifier = WeComNotifier("https://test.webhook.url")

    weekly_report = """📊 **本周AI趋势周报**\n\n📅 2026-02-09 ~ 2026-02-13\n\n## 📈 本周概览\n- 发现 **2** 个AI相关项目"""
    weekly_summary = """## 本周趋势总结\n\n本周重点方向是 Agent 与 LLM 工程化。\n\n🚀 **搜狐业务价值分析**\n\n- 搜索引擎：可用于摘要和检索增强。"""

    trend_message, summary_message = notifier.format_weekly_push_messages(
        weekly_report,
        date(2026, 2, 9),
        date(2026, 2, 13),
        weekly_summary
    )

    assert "本周AI趋势周报" in trend_message
    assert "📝 **AI智能总结 & 业务价值分析**" not in trend_message
    assert "📝 **AI智能总结 & 业务价值分析**" in summary_message
    assert "搜狐业务价值分析" in summary_message


def test_send_weekly_report_split(mock_requests):
    """Test sending split weekly report to WeCom"""
    notifier = WeComNotifier("https://test.webhook.url")

    success = notifier.send_weekly_report_split(
        "📊 **本周AI趋势周报**",
        date(2026, 2, 9),
        date(2026, 2, 13),
        "## 本周趋势总结\n\n测试内容"
    )

    assert success is True
    assert mock_requests.post.call_count == 2


def test_send_markdown_retries_with_shorter_content_on_api_error():
    """Should auto-shorten and retry once when WeCom API returns an error."""
    with patch('src.wecom_notifier.requests') as mock_requests_lib:
        first = Mock()
        first.status_code = 200
        first.raise_for_status.return_value = None
        first.json.return_value = {"errcode": 45002, "errmsg": "content too long"}

        second = Mock()
        second.status_code = 200
        second.raise_for_status.return_value = None
        second.json.return_value = {"errcode": 0, "errmsg": "ok"}

        mock_requests_lib.post.side_effect = [first, second]

        notifier = WeComNotifier("https://test.webhook.url")
        success = notifier.send_markdown("A" * 6000)

        assert success is True
        assert mock_requests_lib.post.call_count == 2

        first_payload = mock_requests_lib.post.call_args_list[0][1]["json"]["markdown"]["content"]
        second_payload = mock_requests_lib.post.call_args_list[1][1]["json"]["markdown"]["content"]

        assert len(second_payload.encode("utf-8")) < len(first_payload.encode("utf-8"))
        assert "自动精简重发" in second_payload


def test_format_daily_top_message_rewrites_unavailable_reason():
    """Fallback english reason should be rewritten to readable Chinese highlight."""
    notifier = WeComNotifier("https://test.webhook.url")

    projects_with_reasons = [
        (
            TrendingProject(
                repo_name="test/agent-repo",
                description="An autonomous AI agent for productivity",
                language="Python",
                url="https://github.com/test/agent-repo",
                stars=888,
                stars_growth=88,
                ranking=1
            ),
            FilterResult(is_ai_related=True, reason="Keyword-based detection (LLM unavailable)")
        )
    ]

    message = notifier._format_daily_top_message(
        projects_with_reasons,
        date(2026, 2, 12),
        for_push=False
    )

    assert "LLM unavailable" not in message
    assert "这是一个面向 AI 助手、智能体或工作流编排的项目" in message
    assert "能解决什么问题：主要解决多步骤任务需要人工串联、规划和执行的问题" in message


def test_split_messages_respect_wecom_markdown_limit():
    """Test split messages stay within WeCom markdown length limit"""
    notifier = WeComNotifier("https://test.webhook.url")

    projects_with_reasons = []
    for i in range(10):
        projects_with_reasons.append(
            (
                TrendingProject(
                    repo_name=f"test/project-{i}",
                    description="A" * 500,
                    language="Python",
                    url=f"https://github.com/test/project-{i}",
                    stars=1000 + i,
                    stars_growth=100 + i,
                    ranking=i + 1
                ),
                FilterResult(is_ai_related=True, reason="B" * 1200)
            )
        )

    summary = "C" * 8000

    trend_message, summary_message = notifier.format_daily_push_messages(
        projects_with_reasons,
        date(2026, 2, 12),
        summary
    )

    assert len(trend_message) <= 4096
    assert len(summary_message) <= 4096


def test_split_messages_respect_wecom_markdown_byte_limit_with_chinese():
    """Test split messages stay within WeCom markdown byte limit (UTF-8)."""
    notifier = WeComNotifier("https://test.webhook.url")

    projects_with_reasons = [
        (
            TrendingProject(
                repo_name="test/chinese",
                description="这是一个非常长的中文描述" * 200,
                language="Python",
                url="https://github.com/test/chinese",
                stars=1234,
                stars_growth=120,
                ranking=1
            ),
            FilterResult(is_ai_related=True, reason="这是一个很长的中文理由" * 300)
        )
    ]

    summary = "这是一个非常长的中文总结内容" * 800

    trend_message, summary_message = notifier.format_daily_push_messages(
        projects_with_reasons,
        date(2026, 2, 12),
        summary
    )

    assert len(trend_message.encode("utf-8")) <= notifier.PUSH_MARKDOWN_LIMIT
    assert len(summary_message.encode("utf-8")) <= notifier.PUSH_MARKDOWN_LIMIT
    assert "📝 项目描述：" in trend_message
    assert "💡 AI亮点：" in trend_message
    assert "（内容过长，已截断）" not in trend_message


def test_format_daily_report_keeps_full_local_content_without_truncation():
    """Local history report should keep full content; truncation is push-only."""
    notifier = WeComNotifier("https://test.webhook.url")

    long_desc = "DESC-" + ("A" * 260)
    long_reason = "REASON-" + ("B" * 1500)
    long_summary = "SUMMARY-" + ("C" * 3200)

    projects_with_reasons = [
        (
            TrendingProject(
                repo_name="test/full-local",
                description=long_desc,
                language="Python",
                url="https://github.com/test/full-local",
                stars=4321,
                stars_growth=321,
                ranking=1
            ),
            FilterResult(is_ai_related=True, reason=long_reason)
        )
    ]

    report = notifier.format_daily_report(
        projects_with_reasons,
        date(2026, 3, 6),
        long_summary
    )

    assert long_desc in report
    assert long_reason in report
    assert long_summary in report
    assert "（总结较长，已自动精简）" not in report


def test_format_daily_report_uses_detailed_local_intro_and_appends_weekly_monthly_refs():
    """Local Markdown should focus on project intro/problem and append weekly/monthly refs."""
    notifier = WeComNotifier("https://test.webhook.url")

    projects_with_reasons = [
        (
            TrendingProject(
                repo_name="test/notebooklm-py",
                description="Unofficial Python API for Google NotebookLM",
                language="Python",
                url="https://github.com/test/notebooklm-py",
                stars=3763,
                stars_growth=196,
                ranking=1
            ),
            FilterResult(
                is_ai_related=True,
                reason=(
                    "该项目是 Google NotebookLM 的非官方 Python API。"
                    "NotebookLM 是基于大语言模型的 AI 笔记与研究助手，"
                    "因此为其提供 API 封装属于 AI 工具/LLM 生态相关项目。"
                )
            )
        )
    ]

    weekly_references = [
        (
            TrendingProject(
                repo_name="test/weekly-agent",
                description="An agent workflow framework for multi-step tasks",
                language="TypeScript",
                url="https://github.com/test/weekly-agent",
                stars=5200,
                stars_growth=440,
                ranking=1
            ),
            FilterResult(is_ai_related=True, reason="该项目面向 AI agent 工作流编排。")
        )
    ]

    monthly_references = [
        (
            TrendingProject(
                repo_name="test/monthly-browser",
                description="Headless browser built for AI automation",
                language="Rust",
                url="https://github.com/test/monthly-browser",
                stars=8800,
                stars_growth=930,
                ranking=1
            ),
            FilterResult(is_ai_related=True, reason="该项目用于 AI 场景下的浏览器自动化。")
        )
    ]

    report = notifier.format_daily_report(
        projects_with_reasons,
        date(2026, 3, 9),
        "",
        weekly_references=weekly_references,
        monthly_references=monthly_references,
    )
    trend_message, _ = notifier.format_daily_push_messages(
        projects_with_reasons,
        date(2026, 3, 9),
        ""
    )

    assert "## 榜单速览" not in report
    assert "## 项目卡片" in report
    assert "- 项目描述：Unofficial Python API for Google NotebookLM" in report
    assert "- 它是干什么的：这是一个面向文档与知识处理的工具" in report
    assert "- 能解决什么问题：主要解决文档、PDF、知识资料难以直接进入 AI/LLM 工作流的问题" in report
    assert "📝 原始描述：" not in report
    assert "💡 AI亮点：" not in report
    assert "📌 项目介绍：" not in report
    assert "- 一句话：" not in report
    assert "## 周榜参考" in report
    assert "test/weekly-agent" in report
    assert "## 月榜参考" in report
    assert "test/monthly-browser" in report
    assert "📝 项目描述：Unofficial Python API for Google NotebookLM" in trend_message
    assert "💡 AI亮点：" in trend_message
    assert "📌 项目介绍：" not in trend_message
