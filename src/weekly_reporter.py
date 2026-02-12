"""Weekly report generator"""
import logging
from datetime import date
from typing import List, Dict
from collections import Counter
from openai import OpenAI
from src.database import Database


logger = logging.getLogger(__name__)


def _normalize_base_url(base_url: str) -> str:
    """Normalize OpenAI-compatible base URL to local proxy path."""
    normalized = base_url.rstrip("/")
    if normalized.endswith("/v1"):
        return normalized
    return f"{normalized}/v1"


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
        normalized_base_url = _normalize_base_url(ai_base_url)
        self.llm = OpenAI(base_url=normalized_base_url, api_key=ai_api_key)
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
        # Fetch weekly trends
        trends = self.db.get_weekly_trends(week_start, week_end)

        if not trends:
            return self._format_empty_report(week_start, week_end)

        # Deduplicate (keep highest stars for each project)
        unique_projects = self._deduplicate_projects(trends)

        # Limit to max_projects
        top_projects = unique_projects[:max_projects]

        # Generate LLM analysis
        tech_trends = self._analyze_trends(top_projects)

        # Format report
        report = self._format_report(
            week_start,
            week_end,
            top_projects,
            tech_trends
        )

        return report

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
            summary.append(f"- {p['repo_name']}: {p['description']} ({p['language']})")

        prompt = f"""分析以下本周GitHub AI趋势项目，总结技术趋势和热点方向（2-3条要点）：

{chr(10).join(summary)}

请返回简洁的趋势分析（每条1句话）。"""

        try:
            response = self.llm.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是AI技术趋势分析专家。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=300
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.warning(f"LLM trend analysis failed: {e}")
            return "本周AI项目持续活跃，涵盖多个技术方向。"

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
            lines.extend([
                f"{idx}. **{p['repo_name']}** ⭐ {p['stars']:,} (+{p['stars_growth']})",
                f"   📝 {p['description'][:80]}..." if len(p['description']) > 80 else f"   📝 {p['description']}",
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
