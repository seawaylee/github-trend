"""Weekly report generator"""
import logging
from datetime import date
from typing import List, Dict
from src.database import Database
from src.shared_llm import call_shared_llm


logger = logging.getLogger(__name__)
class WeeklyReporter:
    """Generate weekly AI trends report"""

    def __init__(
        self,
        database: Database,
        ai_base_url: str,
        ai_api_key: str,
        ai_model: str
    ):
        """
        Initialize weekly reporter

        Args:
            database: Database instance
            ai_base_url: LLM API base URL
            ai_api_key: LLM API key
            ai_model: LLM model name
        """
        self.db = database
        self.ai_base_url = (ai_base_url or "").strip()
        self.ai_api_key = (ai_api_key or "").strip()
        self.model = ai_model

    def generate_report(
        self,
        week_start: date,
        week_end: date,
        max_projects: int = 25
    ) -> str:
        """
        Generate weekly report

        Args:
            week_start: Start date (Monday)
            week_end: End date (Friday)
            max_projects: Maximum projects to include

        Returns:
            Formatted markdown report
        """
        report_package = self.generate_report_package(week_start, week_end, max_projects)
        return report_package["report"]

    def generate_report_package(
        self,
        week_start: date,
        week_end: date,
        max_projects: int = 25
    ) -> Dict[str, str]:
        """
        Generate weekly report + standalone summary for split push.

        Returns:
            Dict with keys:
            - report: Top projects + trend analysis
            - summary: AI summary and business value analysis content
        """
        # Fetch weekly trends
        trends = self.db.get_weekly_trends(week_start, week_end)

        if not trends:
            return {
                "report": self._format_empty_report(week_start, week_end),
                "summary": self._format_empty_summary()
            }

        # Deduplicate (keep highest stars for each project)
        unique_projects = self._deduplicate_projects(trends)

        # Limit to max_projects
        top_projects = unique_projects[:max_projects]

        # Generate LLM analysis
        tech_trends = self._analyze_trends(top_projects)
        weekly_summary = self._analyze_weekly_summary(top_projects, tech_trends)

        # Format report
        report = self._format_report(
            week_start,
            week_end,
            top_projects,
            tech_trends
        )

        return {
            "report": report,
            "summary": weekly_summary
        }

    def _deduplicate_projects(self, trends: List[Dict]) -> List[Dict]:
        """Deduplicate projects, keeping highest stars"""
        projects_map = {}

        for trend in trends:
            repo_name = trend['repo_name']
            if repo_name not in projects_map or trend['stars'] > projects_map[repo_name]['stars']:
                projects_map[repo_name] = trend

        # Sort by stars_growth and stars
        unique = list(projects_map.values())
        unique.sort(key=lambda x: (x['stars_growth'], x['stars']), reverse=True)

        return unique

    def _analyze_trends(self, projects: List[Dict]) -> str:
        """Use LLM to analyze technology trends"""

        # Prepare project summary
        summary = []
        for p in projects[:10]:  # Analyze top 10
            summary.append(
                f"- {p['repo_name']}: {p.get('description') or ''} ({p.get('language') or 'Unknown'})"
            )

        prompt = f"""分析以下本周GitHub AI趋势项目，总结技术趋势和热点方向（2-3条要点）：

{chr(10).join(summary)}

请返回简洁的趋势分析（每条1句话）。"""

        try:
            return call_shared_llm(
                prompt,
                system_prompt="你是AI技术趋势分析专家。",
                model=self.model,
                temperature=0.7,
                timeout=120,
                base_url=self.ai_base_url,
                api_key=self.ai_api_key,
                reasoning_effort="xhigh",
            )

        except Exception as e:
            logger.warning(f"LLM trend analysis failed: {e}")
            return "本周AI项目持续活跃，涵盖多个技术方向。"

    def _analyze_weekly_summary(self, projects: List[Dict], tech_trends: str) -> str:
        """Generate weekly AI summary and business value analysis."""
        if not projects:
            return self._format_empty_summary()

        project_lines = []
        for idx, project in enumerate(projects[:8], 1):
            project_lines.append(
                f"{idx}. {project['repo_name']}: {project.get('description') or ''} "
                f"(Language: {project.get('language') or 'Unknown'})"
            )

        prompt = f"""分析以下本周GitHub热门AI项目列表：

{chr(10).join(project_lines)}

补充技术趋势参考：
{tech_trends}

请完成以下任务：
1. 给出“本周趋势总结”（一段话，聚焦核心技术方向和变化）。
2. 评估这些项目对搜狐业务的价值，重点覆盖搜索引擎、推荐系统、AI基础设施（训练/推理/部署）。
   - 仅在确实相关时给出项目与收益说明，不要编造。

输出要求：
- 使用 Markdown。
- 必须包含标题“## 本周趋势总结”。
- 必须包含标题“🚀 **搜狐业务价值分析**”。
"""

        try:
            summary_text = call_shared_llm(
                prompt,
                system_prompt="你是资深AI技术战略分析师，擅长技术趋势和业务价值评估。",
                model=self.model,
                temperature=0.4,
                timeout=120,
                base_url=self.ai_base_url,
                api_key=self.ai_api_key,
                reasoning_effort="xhigh",
            )
            summary_text = summary_text.strip()
            return self._ensure_summary_sections(summary_text, projects)
        except Exception as e:
            logger.warning(f"LLM weekly summary failed: {e}")
            return self._build_fallback_summary(projects)

    def _ensure_summary_sections(self, summary_text: str, projects: List[Dict]) -> str:
        """Ensure summary contains required markdown sections."""
        content = (summary_text or "").strip()
        if not content:
            return self._build_fallback_summary(projects)

        if "本周趋势总结" not in content:
            content = f"## 本周趋势总结\n\n{content}"

        if "搜狐业务价值分析" not in content:
            content = (
                f"{content}\n\n"
                "🚀 **搜狐业务价值分析**\n\n"
                "- 暂未识别到直接可落地的业务价值，建议持续观察。"
            )

        return content

    def _build_fallback_summary(self, projects: List[Dict]) -> str:
        """Build stable weekly summary when LLM output is unavailable."""
        top_names = "、".join([p["repo_name"] for p in projects[:3]]) or "本周上榜项目"
        return (
            "## 本周趋势总结\n\n"
            f"本周热点主要集中在 Agent、LLM 应用与工程工具链，代表项目包括：{top_names}。\n\n"
            "🚀 **搜狐业务价值分析**\n\n"
            "- 搜索引擎：优先验证检索增强、结果摘要与结构化信息抽取。\n"
            "- 推荐系统：可用于内容标签补全、冷启动特征生成与重排优化。\n"
            "- AI基础设施：建议推进统一模型网关、推理成本治理与多模型容灾。"
        )

    def _categorize_projects(self, projects: List[Dict]) -> Dict[str, int]:
        """Categorize projects by technology area"""
        categories = {
            'LLM/NLP': 0,
            '计算机视觉': 0,
            'AI工具/框架': 0,
            '多模态应用': 0,
            '其他': 0
        }

        for p in projects:
            reason = p.get('ai_relevance_reason', '').lower()
            desc = p.get('description', '').lower()
            text = reason + ' ' + desc

            if any(kw in text for kw in ['llm', 'nlp', 'language', 'gpt', 'chatbot', 'embedding']):
                categories['LLM/NLP'] += 1
            elif any(kw in text for kw in ['vision', 'image', 'video', 'opencv', 'detection']):
                categories['计算机视觉'] += 1
            elif any(kw in text for kw in ['framework', 'tool', 'library', 'platform']):
                categories['AI工具/框架'] += 1
            elif any(kw in text for kw in ['multimodal', 'multi-modal', 'audio', 'speech']):
                categories['多模态应用'] += 1
            else:
                categories['其他'] += 1

        return categories

    def _format_report(
        self,
        week_start: date,
        week_end: date,
        projects: List[Dict],
        tech_trends: str
    ) -> str:
        """Format weekly report"""

        total_stars = sum(p['stars_growth'] for p in projects)
        categories = self._categorize_projects(projects)

        lines = [
            "📊 **本周AI趋势周报**",
            f"\n📅 {week_start.strftime('%Y-%m-%d')} ~ {week_end.strftime('%Y-%m-%d')}",
            "\n## 📈 本周概览",
            f"- 发现 **{len(projects)}** 个AI相关项目",
            f"- 总计新增 **{total_stars:,}** stars",
            "\n## 🏆 热门项目 Top 10\n"
        ]

        # Top 10 projects
        for idx, p in enumerate(projects[:10], 1):
            description = p.get('description') or ''
            raw_highlight = p.get('ai_relevance_reason') or ""
            ai_highlight = self._normalize_ai_highlight(raw_highlight, description)
            lines.extend([
                f"{idx}. **{p['repo_name']}** ⭐ {p['stars']:,} (+{p['stars_growth']})",
                f"   📝 {description}",
                f"   💡 AI亮点：{ai_highlight}",
                f"   🔗 [查看项目]({p['url']})\n"
            ])

        # Tech trends
        lines.extend([
            "\n## 🔥 技术趋势分析",
            tech_trends,
            "\n## 📊 分类统计"
        ])

        for category, count in categories.items():
            if count > 0:
                emoji = self._get_category_emoji(category)
                lines.append(f"- {emoji} {category}: {count}个")

        lines.append("\n---\n⏰ 由GitHub-Trend-Bot自动推送")

        return "\n".join(lines)

    def _format_empty_report(self, week_start: date, week_end: date) -> str:
        """Format empty report when no data"""
        return f"""📊 **本周AI趋势周报**

📅 {week_start.strftime('%Y-%m-%d')} ~ {week_end.strftime('%Y-%m-%d')}

⚠️ 本周暂无AI趋势数据

---
⏰ 由GitHub-Trend-Bot自动推送"""

    @staticmethod
    def _format_empty_summary() -> str:
        """Fallback summary when no weekly data."""
        return (
            "## 本周趋势总结\n\n"
            "本周暂无可分析的AI趋势项目。\n\n"
            "🚀 **搜狐业务价值分析**\n\n"
            "- 暂无可评估的项目。"
        )

    @staticmethod
    def _normalize_ai_highlight(reason: str, description: str = "") -> str:
        """Rewrite fallback/technical reasons into readable Chinese highlight."""
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

    def _get_category_emoji(self, category: str) -> str:
        """Get emoji for category"""
        emoji_map = {
            'LLM/NLP': '🤖',
            '计算机视觉': '👁',
            'AI工具/框架': '🛠',
            '多模态应用': '🎨',
            '其他': '📦'
        }
        return emoji_map.get(category, '📦')
