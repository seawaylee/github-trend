# GitHub AI Trend Tracker

自动追踪GitHub AI相关开源项目趋势,推送到企业微信。

## 功能

- 每日10:00推送Top 5 AI趋势项目
- 每周五16:00推送本周AI趋势总结

## 快速开始

```bash
# 安装依赖
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 配置
cp config/config.example.yaml config/config.yaml
# 编辑config.yaml填入配置

# 初始化数据库
python main.py --init-db

# 测试运行
python main.py --dry-run
python weekly.py --dry-run

# 安装定时任务
./setup.sh install
```

## 配置说明

参考 `config/config.example.yaml`
