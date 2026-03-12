#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenClaw MCP Server
KOL投放管理系统的MCP服务，暴露核心达人管理功能供其他AI调用。

用法：
  python mcp_server.py                    # stdio模式（默认）
  OPENCLAW_DATA_DIR=/path/to/data python mcp_server.py

注册到Claude Code：
  claude mcp add openclaw -- python /path/to/mcp_server.py
"""

import os
import csv
import json
from pathlib import Path
from datetime import datetime
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("openclaw")

# 数据目录：优先读取环境变量，否则用脚本同级的 data/ 目录
DATA_DIR = Path(os.getenv("OPENCLAW_DATA_DIR", Path(__file__).parent / "data"))
TRACKING_CSV = DATA_DIR / "达人跟进表.csv"


# ─── 核心评级逻辑 ─────────────────────────────────────────────────────────────

def _grade_by_cpm(price: float, avg_views: float) -> str:
    """按CPM评级：S(<8)、A(8-12)、B(12-15)、C(>15)"""
    if avg_views <= 0:
        return "?"
    cpm = (price / avg_views) * 1000
    if cpm < 8:
        return "S"
    elif cpm < 12:
        return "A"
    elif cpm < 15:
        return "B"
    else:
        return "C"


def _grade_by_engagement(followers: int, avg_views: float, samples: int) -> str:
    """
    按粉赞比评级（MediaCrawler数据分析标准）：
    S: >5% + 均赞>1000 + 样本≥5 + 稳定性>30%
    A: >5% + 均赞>1000（但样本不足或不稳定）
    B: 2-5%  C: 1-2%  D: <1%
    估算点赞 = 播放量 × 5%（经验系数）
    """
    if followers <= 0:
        return "?"
    avg_likes = avg_views * 0.05
    rate = (avg_likes / followers) * 100
    if rate > 5 and avg_likes > 1000:
        return "S" if samples >= 5 else "A"
    elif rate >= 2:
        return "B"
    elif rate >= 1:
        return "C"
    else:
        return "D"


def _suggest_price(followers: int, avg_views: float) -> int:
    """建议报价：小微达人固定500，其他按CPM=15计算"""
    if followers < 5000:
        return 500
    return max(300, int(avg_views * 15 / 1000))


def _read_csv() -> tuple[list[dict], list[str]]:
    """读取CSV，返回 (rows, fieldnames)"""
    if not TRACKING_CSV.exists():
        return [], []
    with open(TRACKING_CSV, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        return rows, list(reader.fieldnames or [])


def _write_csv(rows: list[dict], fieldnames: list[str]):
    """写入CSV"""
    TRACKING_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(TRACKING_CSV, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ─── MCP 工具 ─────────────────────────────────────────────────────────────────

@mcp.tool()
def analyze_creator(
    name: str,
    followers: int,
    views: list[float],
    price: float = 0,
) -> str:
    """
    分析达人数据，返回评级和建议报价。

    Args:
        name: 达人昵称
        followers: 粉丝数
        views: 最近视频播放量列表（建议5条）
        price: 当前报价（0=未知，按粉赞比评级）

    Returns:
        JSON格式的评级报告
    """
    if not views:
        return json.dumps({"error": "至少提供1个播放量"}, ensure_ascii=False)

    avg_views = sum(views) / len(views)
    min_views = min(views)
    stability = min_views / avg_views if avg_views > 0 else 0

    if price > 0:
        grade = _grade_by_cpm(price, avg_views)
        cpm = round((price / avg_views) * 1000, 1)
    else:
        grade = _grade_by_engagement(followers, avg_views, len(views))
        cpm = None

    suggested_price = _suggest_price(followers, avg_views)

    _RECOMMENDATIONS = {
        "S": "优先建联，强烈推荐",
        "A": "高潜力，建议建联",
        "B": "良好，可小额测试",
        "C": "一般，谨慎考虑",
        "D": "不建议投放",
    }

    return json.dumps({
        "name": name,
        "followers": followers,
        "avg_views": int(avg_views),
        "stability": f"{stability:.0%}",
        "samples": len(views),
        "grade": grade,
        "cpm": cpm,
        "suggested_price": suggested_price,
        "recommendation": _RECOMMENDATIONS.get(grade, "数据不足"),
        "action": "立即建联" if grade in ("S", "A") else "观望",
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def generate_outreach_script(
    name: str,
    followers: int,
    avg_views: float,
    product: str = "AI工具",
    wechat: str = "[你的微信号]",
) -> str:
    """
    生成个性化建联话术。

    Args:
        name: 达人昵称
        followers: 粉丝数
        avg_views: 平均播放量
        product: 推广产品名称（默认"AI工具"）
        wechat: 微信号（替换话术中的占位符）

    Returns:
        抖音私信话术文本
    """
    suggested_price = _suggest_price(followers, avg_views)
    fans_w = followers / 10000
    views_w = avg_views / 10000

    if followers >= 50000:
        return (
            f"您好，我是{product}的商务负责人。\n\n"
            f"看到您的账号数据稳定，{fans_w:.1f}万粉丝，平均播放{views_w:.1f}万，内容质量很不错。\n\n"
            "想了解：\n1. 您这边的商务合作报价\n2. 近期档期是否方便\n\n"
            f"如果感兴趣，可以加我微信详聊：{wechat}\n期待合作！"
        )
    elif followers < 5000:
        return (
            f"您好！看到您有视频播放量破{views_w:.1f}万，数据很不错👍\n\n"
            f"我们是做{product}的，想和您聊聊合作的可能性。\n\n"
            f"您这边商务报价大概是多少呢？我们预算在{suggested_price}元左右。\n\n"
            f"方便加个微信详聊吗？微信：{wechat}"
        )
    else:
        return (
            f"您好，我负责{product}的达人合作。\n\n"
            f"看到您的账号数据不错，平均播放{views_w:.1f}万，内容质量也很好，"
            "想了解一下商务合作报价？\n\n"
            f"方便加个微信详聊吗？微信：{wechat}"
        )


@mcp.tool()
def list_creators(
    status: str = "",
    grade: str = "",
    limit: int = 20,
) -> str:
    """
    查询达人跟进表。

    Args:
        status: 建联状态筛选（未建联/待建联/已建联/已回复/确定合作，空=全部）
        grade: 达人级别筛选（S/A/B/C/D，空=全部）
        limit: 返回条数上限（默认20）

    Returns:
        JSON格式达人列表
    """
    rows, _ = _read_csv()
    results = []
    for row in rows:
        if not row.get("达人昵称"):
            continue
        if status and row.get("建联状态", "") != status:
            continue
        if grade and row.get("达人级别", "") != grade:
            continue
        results.append({
            "name": row.get("达人昵称"),
            "followers": row.get("粉丝数"),
            "grade": row.get("达人级别"),
            "status": row.get("建联状态"),
            "confirmed": row.get("确定合作"),
            "price": row.get("报价"),
            "last_follow": row.get("最后跟进时间"),
            "notes": row.get("备注"),
        })
        if len(results) >= limit:
            break

    return json.dumps({"total": len(results), "creators": results}, ensure_ascii=False, indent=2)


@mcp.tool()
def add_creator(
    name: str,
    followers: int,
    views: list[float],
    price: float = 0,
    notes: str = "",
    grade: str = "",
) -> str:
    """
    添加新达人到跟进表。

    Args:
        name: 达人昵称
        followers: 粉丝数
        views: 最近视频播放量（最多5个）
        price: 报价（0=未知）
        notes: 备注
        grade: 手动指定评级（留空则自动计算）

    Returns:
        操作结果JSON
    """
    rows, fieldnames = _read_csv()
    if not fieldnames:
        fieldnames = [
            "添加日期", "达人昵称", "粉丝数", "播放1", "播放2", "播放3", "播放4", "播放5",
            "报价", "建联状态", "确定合作", "最后跟进时间", "建联时间", "沟通记录", "备注",
            "达人级别", "微信联系方式", "触达次数", "已创建日历",
        ]

    if any(r.get("达人昵称") == name for r in rows):
        return json.dumps({"error": f"达人 {name} 已存在"}, ensure_ascii=False)

    if not grade and followers > 0 and views:
        avg_views = sum(views) / len(views)
        grade = _grade_by_cpm(price, avg_views) if price > 0 else _grade_by_engagement(followers, avg_views, len(views))

    new_row: dict = {f: "" for f in fieldnames}
    new_row.update({
        "添加日期": datetime.now().strftime("%Y/%m/%d"),
        "达人昵称": name,
        "粉丝数": str(followers),
        "报价": str(int(price)) if price else "",
        "建联状态": "待建联",
        "备注": notes,
        "达人级别": grade,
        "触达次数": "0",
    })
    for i, v in enumerate(views[:5], 1):
        new_row[f"播放{i}"] = str(v)

    rows.append(new_row)
    _write_csv(rows, fieldnames)
    return json.dumps({"success": True, "name": name, "grade": grade}, ensure_ascii=False)


@mcp.tool()
def update_creator_status(
    name: str,
    status: str = "",
    confirmed: str = "",
    notes: str = "",
    wechat: str = "",
) -> str:
    """
    更新达人建联状态。

    Args:
        name: 达人昵称
        status: 新建联状态（未建联/待建联/已建联/已回复/确定合作，留空不更新）
        confirmed: 确定合作标记（确定合作/放弃，留空不更新）
        notes: 追加到沟通记录（留空不更新）
        wechat: 微信联系方式（留空不更新）

    Returns:
        操作结果JSON
    """
    rows, fieldnames = _read_csv()
    if not rows:
        return json.dumps({"error": "数据文件为空或不存在"}, ensure_ascii=False)

    found = False
    for row in rows:
        if row.get("达人昵称") != name:
            continue
        found = True
        today = datetime.now().strftime("%Y/%m/%d")
        if status:
            row["建联状态"] = status
            row["最后跟进时间"] = today
            if status == "已建联" and not row.get("建联时间"):
                row["建联时间"] = today
            try:
                row["触达次数"] = str(int(row.get("触达次数") or 0) + 1)
            except ValueError:
                row["触达次数"] = "1"
        if confirmed:
            row["确定合作"] = confirmed
        if notes:
            existing = row.get("沟通记录", "")
            row["沟通记录"] = f"{existing}，{notes}" if existing else notes
        if wechat:
            row["微信联系方式"] = wechat
        break

    if not found:
        return json.dumps({"error": f"未找到达人：{name}"}, ensure_ascii=False)

    _write_csv(rows, fieldnames)
    return json.dumps({"success": True, "name": name}, ensure_ascii=False)


@mcp.tool()
def get_daily_tasks() -> str:
    """
    获取今日待跟进任务：
    - 未建联的S/A级达人（立即建联）
    - 已建联超过3天未回复的达人（催回复）

    Returns:
        JSON格式的今日任务清单
    """
    rows, _ = _read_csv()
    today = datetime.now()
    priority = []
    followup = []

    for row in rows:
        name = row.get("达人昵称")
        if not name:
            continue
        status = row.get("建联状态", "")
        grade = row.get("达人级别", "")

        if status in ("", "未建联", "待建联") and grade in ("S", "A"):
            priority.append({
                "name": name,
                "grade": grade,
                "followers": row.get("粉丝数"),
                "action": "立即建联",
            })
        elif status == "已建联":
            last = row.get("建联时间") or row.get("最后跟进时间", "")
            if last:
                try:
                    last_date = datetime.strptime(last[:10].replace("-", "/"), "%Y/%m/%d")
                    days = (today - last_date).days
                    if days >= 3:
                        followup.append({
                            "name": name,
                            "days_since_contact": days,
                            "action": "跟进催回复",
                        })
                except ValueError:
                    pass

    return json.dumps({
        "date": today.strftime("%Y-%m-%d"),
        "priority_uncontacted": priority,
        "pending_followup": followup,
        "total_tasks": len(priority) + len(followup),
    }, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run()
