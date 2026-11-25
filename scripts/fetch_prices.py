#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
价格采集适配器骨架（**当前未接任何真实数据源**）

⚠️ 这是最重要的一句：本脚本目前**不产生任何真实价格**，也绝不允许让模型编一个价格。
   它只提供：适配器接口、四元组校验、写回 price_history.json / prices.json 的逻辑、--dry-run。
   接入真实源前请读 docs/价格数据契约.md，并自行确认目标站点的 robots / 服务条款、
   是否需要登录或 cookie、反爬与合规风险、更新频率、是否覆盖二手与港版。

设计要点（来自用户口述 P4）：
  - **每日持续采样**，不是只在 618 / 双 11 跑（真实降幅发生在 7/8 月，大促反而不动）
  - **只追加，不覆盖**：Git 天然留下完整价格曲线
  - 一条价格必须有四元组：地域 / 观测日 / 价格类型 / 成色；缺一即 unverified
  - 「券后价」≠「到手价」；国补走资格判定，禁止硬编码 15%

用法：
  python scripts/fetch_prices.py --dry-run          # 只校验与打印计划（默认，安全）
  python scripts/fetch_prices.py --commit-ready     # 供 GitHub Actions 调用（当前仍为空跑）
  python scripts/fetch_prices.py --self-test        # 跑内置的四元组校验用例
"""
import argparse
import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

PRICE_TYPES = {"msrp", "list_price", "coupon_price", "final_price",
               "used_ask", "used_sold", "trade_in_quote"}
REQUIRED = ("region", "observed_at", "price_type", "condition")
STALE_AFTER_DAYS = 7

# 接入清单：来源 | 是否公开 API | 主要合规/反爬注意 | 覆盖二手/港版
# 状态来自 v1 的 09_来源与核实记录.md（2026-11-25 检索），本轮未重新核实，**接入前必须自己再查一遍**。
SOURCE_CANDIDATES = [
    {"name": "京东商品页 / 京东联盟", "official_api": "联盟 API 需申请资质",
     "risk": "商品页反爬；联盟 API 有准入与调用规范", "used": False, "grey": False},
    {"name": "什么值得买", "official_api": "未核实",
     "risk": "多为爆料价（时点、地域、券条件常缺），需人工核四元组", "used": False, "grey": True},
    {"name": "慢慢买 / 历史价格查询", "official_api": "未核实",
     "risk": "历史曲线可用，但口径与到手价不一定一致", "used": False, "grey": False},
    {"name": "闲鱼", "official_api": "未核实",
     "risk": "二手需登录、反爬强；成色/快门数/保修状态需人工归一化", "used": True, "grey": True},
    {"name": "MPB / KEH", "official_api": "未核实",
     "risk": "海外二手，成色分级规范；需处理汇率、运费、关税与地域", "used": True, "grey": False},
    {"name": "B&H / Amazon", "official_api": "部分有联盟 API",
     "risk": "海外 MSRP/挂牌价为主，不等于国内到手价，禁止直接换算", "used": False, "grey": False},
    {"name": "Camera Price Compare / Google Shopping", "official_api": "未核实",
     "risk": "聚合口径，需回溯到原始商家页", "used": False, "grey": False},
]



# ---- v3：真实开源抓价项目的适配器契约 --------------------------------------
# 来源：jakobowsky/AmazonPriceTracker 的 /simple_tracker.py（2026-11-26 亲自打开）
# 借鉴的是 GenerateReport 的「date / title / seller / price / url 落 JSON 报告 +
# 按 price 排序取 best_item」结构；**没有复制它的 Selenium 代码**，原因：
#   find_element_by_xpath 等 API 已废弃、绑定单一电商站点、反爬与合规风险高、
#   而且抓的是挂牌价，不是本项目要的「到手价」。
UPSTREAM_ADAPTERS = [
    {"repo": "jakobowsky/AmazonPriceTracker", "url": "https://github.com/jakobowsky/AmazonPriceTracker",
     "reused": "报告结构：观测日 + 标题 + 卖家 + 价格 + 链接，落 JSON", "not_reused": "Selenium 抓取代码"},
    {"repo": "chen-tf/price-tracker-bot", "url": "https://github.com/chen-tf/price-tracker-bot",
     "reused": "每日定时采样 + 降价提醒的成熟形态", "not_reused": "Telegram 机器人本体"},
    {"repo": "Den4200/amazon-price-tracker", "url": "https://github.com/Den4200/amazon-price-tracker",
     "reused": "目标价触发提醒的思路", "not_reused": "代码（未打开单文件）"},
]


def from_adapter_payload(payload):
    """把上游/自采适配器给的一条原始商品记录，转成本项目四元组 quote。

    payload 至少要有：observed_at / title / seller / price / url。
    缺任何一项 → 返回 None（抓不到就返回空，绝不许造数）。
    注意：这里只做字段映射，**不推算、不补全、不把挂牌价改叫到手价**。
    """
    needed = ("observed_at", "title", "seller", "price", "url")
    if any(not payload.get(k) for k in needed):
        return None
    return {
        "region": payload.get("region") or "未标注（须补地域）",
        "observed_at": str(payload["observed_at"])[:10],
        "price_type": payload.get("price_type") or "list_price",
        "condition": payload.get("condition") or "未标注（须补成色）",
        "price": payload["price"],
        "origin": payload["url"],
        "seller": payload["seller"],
        "title": payload["title"],
        "verified": bool(payload.get("verified")),
        "note": "字段来自适配器；price_type 默认 list_price，禁止直接当到手价展示",
    }


class PriceSource:
    """适配器接口：接入真实源时继承它，实现 fetch()。禁止在 fetch() 里「推算」或「补全」价格。"""

    name = "abstract"

    def fetch(self, item_id):
        """返回 quote 列表，或 [] 表示本次抓不到。抓不到就返回空，绝不许造一个数。"""
        raise NotImplementedError

    def compliance_note(self):
        return "接入前确认 robots / 服务条款 / 登录要求 / 反爬风险 / 更新频率"


class NoOpSource(PriceSource):
    """默认源：明确表示「没有接真实源」，永远返回空列表。"""

    name = "NO_REAL_SOURCE_CONNECTED"

    def fetch(self, item_id):
        return []


def validate_quote(q):
    """四元组校验 + 价格类型合法性 + 过期降级。返回 (是否可入库, 原因列表)。"""
    problems = []
    for k in REQUIRED:
        if not q.get(k):
            problems.append("缺 " + k)
    if q.get("price_type") not in PRICE_TYPES:
        problems.append("price_type 非法：%r" % q.get("price_type"))
    if q.get("price") is not None:
        try:
            if float(q["price"]) < 0:
                problems.append("价格为负")
        except (TypeError, ValueError):
            problems.append("price 不是数字")
    if not q.get("origin"):
        problems.append("缺 origin（来源链接或出处说明）")
    if not q.get("observed_at"):
        problems.append("缺 observed_at")
    else:
        try:
            d = datetime.date.fromisoformat(q["observed_at"][:10])
            age = (datetime.date.today() - d).days
            if age > STALE_AFTER_DAYS:
                problems.append("观测日距今 %d 天，超过 stale_after_days=%d，须标 stale" % (age, STALE_AFTER_DAYS))
        except ValueError:
            problems.append("observed_at 不是 YYYY-MM-DD")
    if q.get("price_type") == "coupon_price":
        problems.append("⚠️ 券后价不可直接当到手价展示")
    return (len(problems) == 0, problems)


def append_history(item, quotes):
    """只追加，不覆盖。"""
    path = os.path.join(DATA, "price_history.json")
    with open(path, encoding="utf-8") as f:
        hist = json.load(f)
    for s in hist["series"]:
        if s["item"] == item:
            for q in quotes:
                s["points"].append({
                    "date": q["observed_at"], "price": q.get("price"),
                    "price_type": q["price_type"], "region": q["region"],
                    "condition": q["condition"], "event": "自动采样",
                    "origin": q["origin"], "observed_at": q["observed_at"],
                    "confidence": "verified" if q.get("verified") else "unverified",
                })
            break
    else:
        hist["series"].append({"item": item, "user_reported": False,
                               "first_launch_price": None, "points": [],
                               "lesson": "自动采样新建序列"})
        hist["series"][-1]["points"] = [
            {"date": q["observed_at"], "price": q.get("price"),
             "price_type": q["price_type"], "region": q["region"],
             "condition": q["condition"], "event": "自动采样",
             "origin": q["origin"], "observed_at": q["observed_at"],
             "confidence": "unverified"} for q in quotes]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=2)
        f.write("\n")


def self_test():
    cases = [
        ({"region": "中国大陆", "observed_at": datetime.date.today().isoformat(),
          "price_type": "final_price", "condition": "全新", "price": 3000,
          "origin": "https://example.com/a"}, True, "完整四元组"),
        ({"region": "中国大陆", "observed_at": "2026-01-01",
          "price_type": "final_price", "condition": "全新", "price": 3000,
          "origin": "https://example.com/a"}, False, "过期应标 stale"),
        ({"observed_at": datetime.date.today().isoformat(),
          "price_type": "final_price", "condition": "全新", "price": 3000,
          "origin": "https://example.com/a"}, False, "缺地域"),
        ({"region": "中国大陆", "observed_at": datetime.date.today().isoformat(),
          "price_type": "coupon_price", "condition": "全新", "price": 3000,
          "origin": "https://example.com/a"}, False, "券后价不可当到手价"),
    ]
    ok = 0
    for q, expect, label in cases:
        passed, problems = validate_quote(q)
        good = passed == expect
        ok += good
        print("  %s %-22s → %s %s" % ("✅" if good else "❌", label,
                                     "可入库" if passed else "拒绝/降级",
                                     "" if good else problems))
    print("四元组自检：%d/%d 通过" % (ok, len(cases)))
    return 0 if ok == len(cases) else 1


def main():
    ap = argparse.ArgumentParser(description="价格采集适配器骨架（当前未接真实源）")
    ap.add_argument("--dry-run", action="store_true", help="只校验与打印计划（默认）")
    ap.add_argument("--commit-ready", action="store_true", help="供 GitHub Actions 调用")
    ap.add_argument("--self-test", action="store_true", help="跑四元组校验用例")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    src = NoOpSource()
    print("=" * 66)
    print("价格采集 · 适配器骨架")
    print("=" * 66)
    print("当前接入的真实源：%s" % src.name)
    print("⚠️ 本脚本不产生任何真实价格，也绝不允许模型编一个价格。")
    print("   抓不到就返回空，界面显示「价格未核实 / 已过期，请自行核对」。")
    print()
    print("采样策略：每日持续采样（不是只在大促跑）、只追加不覆盖、全历史留痕。")
    print("原因：用户口述 50-250 的最大降幅在 7/8 月，双 11 双 12 反而没变化。")
    print()
    print("待接入来源清单（状态来自 2026-11-25 检索，接入前必须重新核实）：")
    for s in SOURCE_CANDIDATES:
        print("  · %-32s API:%-12s 二手:%s 港版:%s" % (
            s["name"], s["official_api"], "是" if s["used"] else "否", "是" if s["grey"] else "否"))
        print("      注意：%s" % s["risk"])
    print()
    print("v3 已接入的开源适配器契约（真实核实过，见 UPSTREAM.md）：")
    for a in UPSTREAM_ADAPTERS:
        print("  · %-34s 复用：%s ｜ 未复用：%s" % (a["repo"], a["reused"], a["not_reused"]))
    print("  · from_adapter_payload() 把上游记录映射成四元组 quote，缺字段直接返回 None，不许造数。")
    print()
    print("接入步骤：")
    print("  1. 继承 PriceSource 实现 fetch(item_id)，抓不到返回 []；")
    print("  2. 每条 quote 过 validate_quote()（四元组 + 类型 + 过期）；")
    print("  3. 通过才 append_history() 与更新 prices.json，否则标 unverified；")
    print("  4. 在 .github/workflows/update-prices.yml 里把 NoOpSource 换成你的适配器；")
    print("  5. 先跑 --self-test 和 engine/scoring.py --validate 再合入。")
    print()
    print("--dry-run 结束：未写入任何文件。" if not args.commit_ready else "--commit-ready 结束：无真实源，未写入任何文件。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
