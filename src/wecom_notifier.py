"""WeCom (Enterprise WeChat) notifier module"""
import requests
import logging
import time
from typing import List
from datetime import date
from src.github_scraper import TrendingProject
from src.ai_filter import FilterResult


logger = logging.getLogger(__name__)


class WeComNotifier:
    """WeCom webhook notifier"""
    PUSH_MARKDOWN_LIMIT = 3800

    def __init__(self, webhook_url: str):
        """
        Initialize notifier

        Args:
            webhook_url: WeCom webhook URL
        """
        self.webhook_url = webhook_url

    def send_markdown(self, content: str) -> bool:
        """
        Send markdown message to WeCom

        Args:
            content: Markdown content

        Returns:
            True if successful
        """
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": content
            }
        }

        try:
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            response.raise_for_status()

            result = response.json()
            if result.get('errcode') == 0:
                logger.info("Message sent successfully to WeCom")
                return True
            else:
                logger.error(f"WeCom API error: {result}")
                return False

        except requests.RequestException as e:
            logger.error(f"Failed to send WeCom message: {e}")
            return False

    def format_daily_report(
        self,
        projects_with_reasons: List[tuple[TrendingProject, FilterResult]],
        report_date: date,
        summary: str = ""
    ) -> str:
        """Format daily report without sending"""
        return self._format_daily_message(projects_with_reasons, report_date, summary)

    def format_daily_push_messages(
        self,
        projects_with_reasons: List[tuple[TrendingProject, FilterResult]],
        report_date: date,
        summary: str = ""
    ) -> tuple[str, str]:
        """Format two WeCom messages: trend list + summary/business analysis."""
        trend_message = self._format_daily_top_message(projects_with_reasons, report_date)
        summary_message = self._format_daily_summary_message(report_date, summary)
        return trend_message, summary_message

    def send_daily_report(
        self,
        projects_with_reasons: List[tuple[TrendingProject, FilterResult]],
        report_date: date,
        summary: str = ""
    ) -> bool:
        """
        Send daily AI trends report

        Args:
            projects_with_reasons: List of (project, filter_result) tuples
            report_date: Date of the report
            summary: Optional LLM-generated summary

        Returns:
            True if successful
        """
        message = self._format_daily_message(projects_with_reasons, report_date, summary)
        return self.send_markdown(message)

    def send_daily_report_split(
        self,
        projects_with_reasons: List[tuple[TrendingProject, FilterResult]],
        report_date: date,
        summary: str = ""
    ) -> bool:
        """Send daily report as two WeCom markdown messages."""
        trend_message, summary_message = self.format_daily_push_messages(
            projects_with_reasons,
            report_date,
            summary
        )

        if not self.send_markdown(trend_message):
            return False

        # Avoid hitting bot webhook rate limits with immediate back-to-back calls.
        time.sleep(1)
        return self.send_markdown(summary_message)

    def _format_daily_top_message(
        self,
        projects_with_reasons: List[tuple[TrendingProject, FilterResult]],
        report_date: date,
        for_push: bool = True
    ) -> str:
        """Format top projects message in markdown."""
        limit = len(projects_with_reasons)
        lines = [
            f"🔥 **今日GitHub AI趋势 Top {limit}**",
            f"\n📅 {report_date.strftime('%Y-%m-%d')}",
            "\n---\n"
        ]

        emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

        for idx, (project, result) in enumerate(projects_with_reasons):
            emoji = emojis[idx] if idx < len(emojis) else f"{idx+1}."

            stars_str = f"{project.stars:,}"
            growth_str = f"+{project.stars_growth}" if project.stars_growth > 0 else ""
            max_desc_length = 80 if for_push else 100
            max_reason_length = 120 if for_push else 1200
            short_desc = self._truncate_text(project.description, max_desc_length)
            short_reason = self._truncate_text(result.reason, max_reason_length)

            lines.extend([
                f"\n{emoji} **{project.repo_name}** ⭐ {stars_str} ({growth_str})",
                f"🏷 {project.language}",
                f"📝 {short_desc}",
                f"💡 AI亮点：{short_reason}",
                f"🔗 [查看项目]({project.url})\n"
            ])

        lines.append("\n---\n⏰ 由GitHub-Trend-Bot自动推送")
        message = "\n".join(lines)
        return self._fit_markdown_limit(message) if for_push else message

    def _format_daily_summary_message(self, report_date: date, summary: str, for_push: bool = True) -> str:
        """Format summary/business analysis message in markdown."""
        summary_content = summary.strip() if summary and summary.strip() else "（生成总结失败）"

        lines = [
            "📝 **AI智能总结 & 业务价值分析**",
            f"\n📅 {report_date.strftime('%Y-%m-%d')}",
            "\n---\n",
            summary_content,
            "\n---\n⏰ 由GitHub-Trend-Bot自动推送"
        ]
        message = "\n".join(lines)
        return self._fit_markdown_limit(message) if for_push else message

    def _format_daily_message(
        self,
        projects_with_reasons: List[tuple[TrendingProject, FilterResult]],
        report_date: date,
        summary: str = ""
    ) -> str:
        """Format daily message in markdown"""
        top_message = self._format_daily_top_message(
            projects_with_reasons,
            report_date,
            for_push=False
        )
        summary_message = self._format_daily_summary_message(
            report_date,
            summary,
            for_push=False
        )

        # Keep history output as one markdown document.
        top_without_footer = top_message.rsplit("\n---\n⏰ 由GitHub-Trend-Bot自动推送", 1)[0]
        summary_body = summary_message.split("\n---\n", 1)[-1]
        summary_without_footer = summary_body.rsplit("\n---\n⏰ 由GitHub-Trend-Bot自动推送", 1)[0]

        lines = [
            top_without_footer,
            "\n---\n",
            summary_without_footer,
            "\n---\n⏰ 由GitHub-Trend-Bot自动推送"
        ]
        return "\n".join(lines)

    def _fit_markdown_limit(self, content: str) -> str:
        """Ensure markdown content stays within WeCom message UTF-8 byte limit."""
        if len(content.encode("utf-8")) <= self.PUSH_MARKDOWN_LIMIT:
            return content

        suffix = "\n\n（内容过长，已截断）"
        suffix_bytes = len(suffix.encode("utf-8"))
        if suffix_bytes >= self.PUSH_MARKDOWN_LIMIT:
            return self._truncate_by_bytes(suffix, self.PUSH_MARKDOWN_LIMIT)

        allowed_bytes = self.PUSH_MARKDOWN_LIMIT - suffix_bytes
        return self._truncate_by_bytes(content, allowed_bytes) + suffix

    @staticmethod
    def _truncate_by_bytes(text: str, max_bytes: int) -> str:
        """Truncate text by UTF-8 bytes without breaking characters."""
        if max_bytes <= 0:
            return ""
        if len(text.encode("utf-8")) <= max_bytes:
            return text

        left = 0
        right = len(text)
        while left < right:
            mid = (left + right + 1) // 2
            if len(text[:mid].encode("utf-8")) <= max_bytes:
                left = mid
            else:
                right = mid - 1
        return text[:left]

    @staticmethod
    def _truncate_text(text: str, max_length: int) -> str:
        """Truncate text with ellipsis when necessary."""
        if len(text) <= max_length:
            return text
        return text[:max_length] + "..."

    def send_weekly_report(self, report_content: str) -> bool:
        """
        Send weekly report

        Args:
            report_content: Formatted weekly report markdown

        Returns:
            True if successful
        """
        return self.send_markdown(report_content)
