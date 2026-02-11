"""WeCom (Enterprise WeChat) notifier module"""
import requests
import logging
from typing import List
from datetime import date
from src.github_scraper import TrendingProject
from src.ai_filter import FilterResult


logger = logging.getLogger(__name__)


class WeComNotifier:
    """WeCom webhook notifier"""

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

    def _format_daily_message(
        self,
        projects_with_reasons: List[tuple[TrendingProject, FilterResult]],
        report_date: date,
        summary: str = ""
    ) -> str:
        """Format daily message in markdown"""

        limit = len(projects_with_reasons)
        lines = [
            f"🔥 **今日GitHub AI趋势 Top {limit}**",
            f"\n📅 {report_date.strftime('%Y-%m-%d')}",
            "\n---\n"
        ]

        emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

        for idx, (project, result) in enumerate(projects_with_reasons):
            emoji = emojis[idx] if idx < len(emojis) else f"{idx+1}."

            # Format stars with comma
            stars_str = f"{project.stars:,}"
            growth_str = f"+{project.stars_growth}" if project.stars_growth > 0 else ""

            lines.extend([
                f"\n{emoji} **{project.repo_name}** ⭐ {stars_str} ({growth_str})",
                f"🏷 {project.language}",
                f"📝 {project.description[:100]}..." if len(project.description) > 100 else f"📝 {project.description}",
                f"💡 AI亮点：{result.reason}",
                f"🔗 [查看项目]({project.url})\n"
            ])

        if summary:
            lines.append("\n---\n")
            lines.append("📝 **AI智能总结 & 业务价值分析**\n")
            lines.append(summary)

        lines.append("\n---\n⏰ 由GitHub-Trend-Bot自动推送")

        return "\n".join(lines)

    def send_weekly_report(self, report_content: str) -> bool:
        """
        Send weekly report

        Args:
            report_content: Formatted weekly report markdown

        Returns:
            True if successful
        """
        return self.send_markdown(report_content)
