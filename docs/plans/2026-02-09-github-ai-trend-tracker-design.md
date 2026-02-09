# GitHub AI趋势追踪系统设计文档

**创建日期:** 2026-02-09
**项目目标:** 每日自动追踪GitHub AI相关开源项目趋势，通过企业微信推送，每周五生成趋势总结报告

---

## 一、需求概述

### 核心功能
1. **每日任务（每天10点）**
   - 抓取GitHub每日和每周趋势榜
   - 使用LLM智能识别AI相关项目
   - 筛选Top 5每日AI项目
   - 推送到企业微信

2. **周报任务（每周五16点）**
   - 汇总本周AI项目趋势
   - 生成深度分析报告（热门项目、技术趋势、分类统计）
   - 推送最多25个精选项目到企业微信

3. **部署方式**
   - macOS本地部署
   - launchd定时任务
   - Python技术栈

---

## 二、系统架构

### 技术栈
- **语言:** Python 3.9+
- **核心库:**
  - `requests` - HTTP请求
  - `beautifulsoup4` - HTML解析
  - `openai` - LLM API调用（兼容接口）
  - `sqlite3` - 数据存储
  - `pyyaml` - 配置管理

### 项目结构
```
github-trend/
├── config/
│   ├── config.yaml              # 配置文件（不提交）
│   └── config.example.yaml      # 配置模板
├── data/
│   └── trends.db               # SQLite数据库
├── logs/
│   ├── app.log                 # 应用日志
│   ├── daily.log               # 每日任务日志
│   └── weekly.log              # 周报任务日志
├── src/
│   ├── github_scraper.py       # GitHub趋势抓取
│   ├── ai_filter.py            # AI项目识别
│   ├── wecom_notifier.py       # 企业微信通知
│   ├── database.py             # 数据库操作
│   └── weekly_reporter.py      # 周报生成
├── main.py                     # 每日任务入口
├── weekly.py                   # 周报任务入口
├── requirements.txt            # 依赖列表
├── setup.sh                    # 一键安装脚本
├── .gitignore
└── README.md
```

---

## 三、数据流程

### 每日任务流程
1. **抓取趋势榜**
   - 访问 `https://github.com/trending?since=daily`
   - 访问 `https://github.com/trending?since=weekly`
   - 解析项目列表（名称、描述、stars、语言、URL）

2. **AI智能筛选**
   - 将项目信息发送给LLM（gemini-3-pro-high）
   - Prompt示例:
     ```
     判断以下GitHub项目是否与AI相关（机器学习、深度学习、LLM、
     计算机视觉、NLP、AI工具等）。
     项目：{name}
     描述：{description}
     语言：{language}

     返回JSON: {"is_ai_related": true/false, "reason": "原因"}
     ```
   - 筛选出AI相关项目

3. **Top 5排序**
   - 按stars增长数和趋势榜排名排序
   - 只保留前5个项目

4. **存储到数据库**
   - 保存项目信息、趋势数据、AI分析结果
   - 去重处理

5. **推送企业微信**
   - Markdown格式卡片消息

### 周报任务流程
1. **数据汇总**
   - 查询本周（周一到周五）所有AI项目记录
   - 去重（同一项目只保留最高stars记录）

2. **LLM深度分析**
   - 提取本周技术趋势
   - 生成总结文案
   - 识别热门技术方向

3. **报告生成**
   - 热门项目Top 10
   - 技术趋势分析
   - 分类统计
   - 新星项目推荐

4. **推送企业微信**
   - 最多25个精选项目
   - Markdown格式周报

---

## 四、数据库设计

### 表结构

```sql
-- 项目表
CREATE TABLE projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_name TEXT UNIQUE NOT NULL,     -- owner/repo
    description TEXT,
    language TEXT,
    url TEXT NOT NULL,
    first_seen DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 趋势记录表
CREATE TABLE trend_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    date DATE NOT NULL,
    stars INTEGER,
    stars_growth INTEGER,               -- 当日增长
    trend_type TEXT NOT NULL,           -- 'daily' or 'weekly'
    ranking INTEGER,                    -- 榜单排名
    ai_relevance_reason TEXT,           -- AI判断理由
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id),
    UNIQUE(project_id, date, trend_type)
);

-- 周报记录表
CREATE TABLE weekly_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week_start DATE NOT NULL,
    week_end DATE NOT NULL,
    summary TEXT,                       -- LLM生成的总结
    tech_trends TEXT,                   -- 技术趋势分析
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 五、配置管理

### config.yaml 结构

```yaml
# GitHub设置
github:
  token: ""  # 可选，提高API限流额度

# LLM服务配置
ai:
  base_url: "http://127.0.0.1:8045"
  api_key: "sk-f750eba34c6145fc857feaf7f3851f5b"
  model: "gemini-3-pro-high"

# 企业微信配置
wecom:
  webhook_url: "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=29f45d56-3f1a-45af-a146-02507f6465b7"

# 任务配置
tasks:
  daily_limit: 5          # 每日推送项目数量
  weekly_limit: 25        # 周报项目数量
  daily_hour: 10          # 每日推送时间
  weekly_day: 5           # 周五
  weekly_hour: 16         # 下午4点

# 日志配置
logging:
  level: "INFO"
  file: "logs/app.log"
  max_bytes: 10485760     # 10MB
  backup_count: 5
```

### 安全措施
- `config.yaml` 加入 `.gitignore`
- 提供 `config.example.yaml` 模板
- 支持环境变量覆盖

---

## 六、消息格式设计

### 每日推送格式

```markdown
🔥 今日GitHub AI趋势 Top 5

📅 2026-02-09

---

1️⃣ **owner/repo-name** ⭐ 1,234 (+567)
🏷 Python | Machine Learning
📝 项目简介：一个革命性的LLM训练框架...
💡 AI亮点：创新的模型压缩技术，提升推理速度3倍
🔗 [查看项目](https://github.com/...)

2️⃣ **owner/another-repo** ⭐ 890 (+234)
🏷 TypeScript | LLM Tools
📝 ...
💡 ...
🔗 ...

[3️⃣-5️⃣ 类似格式]

---
⏰ 由GitHub-Trend-Bot自动推送
```

### 周报推送格式

```markdown
📊 本周AI趋势周报

📅 2026-02-03 ~ 2026-02-07

## 📈 本周概览
- 发现 **32** 个AI相关项目
- 总计新增 **45,678** stars
- LLM应用工具占比 40%，多模态项目增长显著

## 🏆 热门项目 Top 10
1. **owner/repo** ⭐ 5,678 (+2,345)
   📝 项目描述...
   🔗 [查看](https://...)

[2-10 类似格式]

## 🔥 技术趋势分析
本周AI领域呈现以下趋势：
1. **LLM推理优化**成为热点，多个量化加速框架上榜
2. **AI Agent框架**持续火热，工作流编排工具受关注
3. **多模态应用**增长明显，视频生成、音频处理项目涌现

## 📊 分类统计
- 🤖 LLM/NLP: 15个
- 👁 计算机视觉: 8个
- 🛠 AI工具/框架: 7个
- 🎨 多模态应用: 2个

## 🌟 值得关注的新星
[首次上榜但潜力大的3-5个项目]

---
⏰ 由GitHub-Trend-Bot自动推送
```

---

## 七、定时任务配置

### launchd plist文件

**每日任务:** `~/Library/LaunchAgents/com.github-trend.daily.plist`
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.github-trend.daily</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/NikoBelic/app/git/github-trend/venv/bin/python</string>
        <string>/Users/NikoBelic/app/git/github-trend/main.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>10</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/NikoBelic/app/git/github-trend/logs/daily.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/NikoBelic/app/git/github-trend/logs/daily.error.log</string>
    <key>WorkingDirectory</key>
    <string>/Users/NikoBelic/app/git/github-trend</string>
</dict>
</plist>
```

**周报任务:** `~/Library/LaunchAgents/com.github-trend.weekly.plist`
- 每周五16点运行
- `<key>Weekday</key><integer>5</integer>`
- `<key>Hour</key><integer>16</integer>`

---

## 八、错误处理与监控

### 容错机制

1. **网络请求重试**
   - GitHub抓取失败：最多重试3次，指数退避
   - LLM API失败：降级使用关键词匹配
   - 企业微信推送失败：记录日志，不中断流程

2. **降级策略**
   - LLM不可用时，使用关键词匹配（AI, ML, LLM, GPT, etc.）
   - 数据不足时，周报标注数据缺失但仍发送

3. **异常通知**
   - 严重错误发送告警到企业微信
   - 示例：`⚠️ GitHub趋势抓取失败，请检查网络`

### 日志管理
- **级别:** INFO, WARNING, ERROR
- **滚动:** 单文件10MB，保留5个备份
- **内容:**
  - 抓取项目数量
  - 筛选结果统计
  - API调用耗时
  - 错误堆栈

### 手动测试命令
```bash
# 初始化数据库
python main.py --init-db

# 测试每日任务（不发送消息）
python main.py --dry-run

# 测试周报生成
python weekly.py --dry-run

# 查看数据库统计
python main.py --stats

# 手动运行每日任务
python main.py

# 生成指定周的周报
python weekly.py --week-start 2026-02-03
```

---

## 九、部署流程

### 快速启动

```bash
# 1. 克隆/初始化项目
cd /Users/NikoBelic/app/git/github-trend
git init

# 2. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置
cp config/config.example.yaml config/config.yaml
# 编辑配置文件（API密钥、webhook等已预设）

# 5. 初始化数据库
python main.py --init-db

# 6. 测试运行
python main.py --dry-run
python weekly.py --dry-run

# 7. 安装定时任务
./setup.sh install

# 8. 验证定时任务
launchctl list | grep github-trend
```

---

## 十、后续扩展可能性

1. **多渠道推送**
   - 钉钉、飞书、邮件
   - 支持多个企业微信群

2. **Web界面**
   - 查看历史趋势图表
   - 手动触发任务
   - 配置管理界面

3. **高级分析**
   - 项目趋势曲线
   - 技术栈演变分析
   - 开发者影响力排名

4. **数据导出**
   - CSV/JSON导出
   - API接口提供数据

---

## 附录：依赖清单

```txt
requests>=2.31.0
beautifulsoup4>=4.12.0
lxml>=4.9.0
openai>=1.12.0
pyyaml>=6.0
python-dateutil>=2.8.2
```

---

**设计完成日期:** 2026-02-09
**预计开发时间:** 2-3小时
**维护难度:** 低
