# openclaw-mcp

KOL 投放管理 MCP 服务 — 将达人筛选、评级、建联话术等核心能力封装为标准 MCP 工具，供 Claude Code 及任意支持 MCP 协议的 AI 直接调用，无需自建服务器。

> 完整的 KOL 投放管理系统见 [kol-claw](https://github.com/sz8887031-bot/kol-claw)

---

## 快速开始

### 1. 克隆并安装依赖

```bash
git clone https://github.com/sz8887031-bot/kol-claw-mcp.git
cd kol-claw-mcp
pip install -r requirements.txt
```

### 2. 注册到 Claude Code

```bash
claude mcp add openclaw -- python /path/to/kol-claw-mcp/mcp_server.py
```

### 3. （可选）指定数据目录

默认读取 `data/` 目录下的 `达人跟进表.csv`，可通过环境变量自定义：

```bash
OPENCLAW_DATA_DIR=/your/data/path claude mcp add openclaw -- python /path/to/mcp_server.py
```

---

## MCP 工具（6个）

| 工具名 | 功能 | 核心参数 |
|--------|------|----------|
| `analyze_creator` | 分析达人数据，输出评级和建议报价 | name, followers, views[], price |
| `generate_outreach_script` | 生成个性化建联私信话术 | name, followers, avg_views, product |
| `list_creators` | 查询达人跟进表（支持筛选） | status, grade, limit |
| `add_creator` | 添加新达人到跟进表 | name, followers, views[], price |
| `update_creator_status` | 更新建联状态和沟通记录 | name, status, notes, wechat |
| `get_daily_tasks` | 获取今日待跟进任务清单 | — |

### 评级标准

**有报价时（按 CPM）**：S < 8 / A 8-12 / B 12-15 / C > 15

**无报价时（按粉赞比，估算点赞 = 播放 × 5%）**：
- S：粉赞比 > 5% + 均赞 > 1000 + 样本 ≥ 5 条
- A：粉赞比 > 5% + 均赞 > 1000（样本不足）
- B：粉赞比 2-5%
- C：粉赞比 1-2%
- D：粉赞比 < 1%

---

## Claude Code Skills（3个斜杠命令）

Skills 文件位于 `.claude/commands/`，在 Claude Code 对话中直接使用：

| 命令 | 功能 | 示例 |
|------|------|------|
| `/kol-analyze` | 分析达人数据并给出评级 | `/kol-analyze 粉丝50万，播放30万、28万、35万，报价8000` |
| `/kol-outreach` | 生成建联话术 | `/kol-outreach 美食博主小李，粉丝8.5万，均播32万` |
| `/kol-daily` | 获取今日跟进清单 | `/kol-daily` |

---

## 数据格式

跟进表路径：`data/达人跟进表.csv`（运行时自动创建，`data/sample/` 提供示例）

| 字段 | 说明 |
|------|------|
| 达人昵称 | 唯一标识 |
| 粉丝数 | 整数 |
| 播放1~5 | 最近5条视频播放量 |
| 报价 | 元，0 或空表示未知 |
| 建联状态 | 未建联 / 待建联 / 已建联 / 已回复 / 确定合作 |
| 达人级别 | S / A / B / C / D（自动计算或手动填写） |
| 沟通记录 | 逐条追加 |

---

## License

MIT
