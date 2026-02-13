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
    RETRY_SHRINK_LIMIT = 2500
    SUMMARY_CONTENT_LIMIT = 2600

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
        message = self._fit_markdown_limit(content)
        success, result = self._send_markdown_once(message)
        if success:
            logger.info("Message sent successfully to WeCom")
            return True

        if result is None:
            return False

        # If WeCom rejects content, auto-shorten and retry once.
        shrunk_message = self._shrink_for_retry(message)
        if shrunk_message == message:
            logger.error(f"WeCom API error: {result}")
            return False

        logger.warning(f"WeCom API error: {result}. Retrying with shorter content...")
        retry_success, retry_result = self._send_markdown_once(shrunk_message)
        if retry_success:
            logger.info("Message sent successfully to WeCom (shortened retry)")
            return True

        logger.error(f"WeCom API error after shortened retry: {retry_result}")
        return False

    def _send_markdown_once(self, content: str) -> tuple[bool, dict | None]:
        """Send one markdown request and return (success, api_result)."""
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
            return result.get('errcode') == 0, result
        except requests.RequestException as e:
            logger.error(f"Failed to send WeCom message: {e}")
            return False, None

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

    def format_weekly_push_messages(
        self,
        report_content: str,
        week_start: date,
        week_end: date,
        summary: str = ""
    ) -> tuple[str, str]:
        """Format two weekly messages: trend report + summary/business analysis."""
        trend_message = self._fit_markdown_limit(report_content)
        summary_message = self._format_weekly_summary_message(week_start, week_end, summary)
        return trend_message, summary_message

    def send_weekly_report_split(
        self,
        report_content: str,
        week_start: date,
        week_end: date,
        summary: str = ""
    ) -> bool:
        """Send weekly report as two WeCom markdown messages."""
        trend_message, summary_message = self.format_weekly_push_messages(
            report_content,
            week_start,
            week_end,
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
            normalized_reason = self._normalize_ai_highlight(result.reason, project.description)
            short_reason = self._truncate_text(normalized_reason, max_reason_length)

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
        summary_content = self._prepare_summary_content(summary)

        lines = [
            "📝 **AI智能总结 & 业务价值分析**",
            f"\n📅 {report_date.strftime('%Y-%m-%d')}",
            "\n---\n",
            summary_content,
            "\n---\n⏰ 由GitHub-Trend-Bot自动推送"
        ]
        message = "\n".join(lines)
        return self._fit_markdown_limit(message) if for_push else message

    def _format_weekly_summary_message(
        self,
        week_start: date,
        week_end: date,
        summary: str,
        for_push: bool = True
    ) -> str:
        """Format weekly summary/business analysis message in markdown."""
        summary_content = self._prepare_summary_content(summary)

        lines = [
            "📝 **AI智能总结 & 业务价值分析**",
            f"\n📅 {week_start.strftime('%Y-%m-%d')} ~ {week_end.strftime('%Y-%m-%d')}",
            "\n---\n",
            summary_content,
            "\n---\n⏰ 由GitHub-Trend-Bot自动推送"
        ]
        message = "\n".join(lines)
        return self._fit_markdown_limit(message) if for_push else message

    def _prepare_summary_content(self, summary: str) -> str:
        """Normalize summary and keep it within a stable size budget."""
        content = summary.strip() if summary and summary.strip() else "（生成总结失败）"
        if len(content.encode("utf-8")) <= self.SUMMARY_CONTENT_LIMIT:
            return content

        suffix = "\n\n（总结较长，已自动精简）"
        suffix_bytes = len(suffix.encode("utf-8"))
        allowed = self.SUMMARY_CONTENT_LIMIT - suffix_bytes
        if allowed <= 0:
            return self._truncate_by_bytes(content, self.SUMMARY_CONTENT_LIMIT)
        return self._truncate_by_bytes(content, allowed) + suffix

    def _shrink_for_retry(self, content: str) -> str:
        """Shrink markdown for one retry attempt after API rejection."""
        content_bytes = len(content.encode("utf-8"))
        if content_bytes <= self.RETRY_SHRINK_LIMIT:
            return content

        suffix = "\n\n（首次推送失败，已自动精简重发）"
        suffix_bytes = len(suffix.encode("utf-8"))
        allowed = self.RETRY_SHRINK_LIMIT - suffix_bytes
        if allowed <= 0:
            return self._truncate_by_bytes(content, self.RETRY_SHRINK_LIMIT)
        return self._truncate_by_bytes(content, allowed) + suffix

    @staticmethod
    def _normalize_ai_highlight(reason: str, description: str = "") -> str:
        """Rewrite unreadable fallback reasons into a user-facing Chinese highlight."""
        normalized = (reason or "").strip()
        lower_reason = normalized.lower()

        fallback_markers = (
            "keyword-based detection",
            "keyword based detection",
            "llm unavailable"
        )
        if not normalized or any(marker in lower_reason for marker in fallback_markers):
            desc_text = (description or "").lower()
            if any(kw in desc_text for kw in ("agent", "assistant", "copilot", "workflow")):
                area = "AI Agent/智能助手方向"
            elif any(kw in desc_text for kw in ("llm", "gpt", "chat", "rag", "prompt")):
                area = "LLM 应用方向"
            elif any(kw in desc_text for kw in ("vision", "image", "video", "multimodal")):
                area = "多模态/视觉方向"
            else:
                area = "AI 应用或工具方向"

            return f"基于项目描述中的关键词判定，该项目与 {area}相关，建议后续结合 README 做进一步复核。"

        return normalized

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
