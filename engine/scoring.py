#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
相机选购顾问 v2 · 可解释打分引擎（零外部依赖，纯标准库）

与 app/index.html 里的 JS 引擎严格同源。数据读 data/ 或 references/ 下的 JSON。
方法论出处：docs/方法论.md（P1–P11）。所有系数是示例标定、未实证，界面与导出包须如实标注。

用法：
  python engine/scoring.py --preset hiker
  python engine/scoring.py --budget 10000 --scenes travel,landscape --output wechat \
      --abilities can_raw,willing_post,buy_fast_lens,static_subject --trek-km 20 \
      --pains wide,pixels,tele --constraints phone_battery --finance include_user_sample --top 3
  python engine/scoring.py --validate          # 只校验数据文件完整性
  python engine/scoring.py ... --json          # 输出机器可读 JSON（供 skill / 网站后端调用）
"""
import argparse
import datetime
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CANDIDATES = [
    os.path.normpath(os.path.join(HERE, "..", "data")),
    os.path.normpath(os.path.join(HERE, "..", "references")),
    os.path.join(HERE, "references"),
    os.path.normpath(os.path.join(HERE, "..", "..", "12_camera-advisor-repo", "data")),
]
REF = next((p for p in CANDIDATES if os.path.exists(os.path.join(p, "bodies.json"))), None)
if REF is None:
    sys.exit("找不到数据目录（需含 bodies.json）。候选：\n  " + "\n  ".join(CANDIDATES))


def load(name):
    with open(os.path.join(REF, name), encoding="utf-8") as f:
        return json.load(f)


def money(n):
    return "¥" + format(int(round(n)), ",")


# ---- v3：价格新鲜度与慢变档位 ----------------------------------------------
# 用户 2026-11-26 指出「不能实时联网，价格不就是错的」。解法见 PRICE_FRESHNESS.md。
# 全局上下文，由 main() 初始化；网页版用同一套字段与判定，保证严格同源。
CTX = {"tiers": {}, "fp": {}, "today": None, "strict": True}


def load_optional(name, default):
    p = os.path.join(REF, name)
    if not os.path.exists(p):
        return default
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def tier_of(b, tiers):
    """慢变价格档位。返回 None 表示缺档位表（此时退回示例价并在输出里警告）。"""
    t = tiers.get(b["id"]) if isinstance(tiers, dict) else None
    return t.get("tier") if isinstance(t, dict) else None


def price_freshness(p, fp, today=None):
    """返回 (status, age_days, ttl, label)。status: fresh / stale / unverified。

    只有 confidence 在 trusted_confidence 里、且观测日在 TTL 内，才算 fresh。
    目前库里没有任何 verified 价格 → 全部 unverified，这是诚实的默认值。
    """
    today = today or datetime.date.today()
    conf = p.get("confidence", "unverified")
    obs = str(p.get("observed_at", ""))[:10]
    try:
        d = datetime.date.fromisoformat(obs)
        age = (today - d).days
    except (ValueError, TypeError):
        return ("unverified", None, None, "无有效观测日 → 未核实")
    ttl = fp.get("ttl_days_by_type", {}).get(
        p.get("price_type", "final_price"), fp.get("default_ttl_days", 7))
    if conf not in fp.get("trusted_confidence", ["verified"]):
        return ("unverified", age, ttl, "来源未核实（confidence=%s）" % conf)
    if age < 0:
        return ("unverified", age, ttl, "观测日在未来，拒绝采信")
    if age > ttl:
        return ("stale", age, ttl, "已过期 %d 天（TTL %d 天）" % (age, ttl))
    return ("fresh", age, ttl, "观测于 %d 天前，未过期" % age)


def freshness_summary(bodies, fp, today):
    out = {"fresh": 0, "stale": 0, "unverified": 0, "as_of": str(today)}
    for b in bodies:
        s = price_freshness(b["price"], fp, today)[0]
        out[s] += 1
    out["all_stale"] = out["fresh"] == 0
    return out


# ---- v3.1：按剩余预算给「机身 + 镜头」具体搭配建议 -------------------------
def _nums(s):
    import re as _re
    return [float(x) for x in _re.findall(r"\d+(?:\.\d+)?", str(s or ""))] or [50.0]


def lens_min_focal(l):
    """焦距字符串最小值：'16-50' → 16，用来判断够不够广。"""
    return min(_nums(l.get("focal")))


def lens_max_aperture(l):
    """最大光圈的 f 值（数值越小光圈越大）：'3.5-6.3' → 3.5。"""
    return min(_nums(l.get("aperture")))


def suggest_kit(q, b, lenses, tier):
    """按慢变档位算：「机身档位 + 配件」之后还剩多少钱买镜头，能配齐几颗。

    这是**搭配建议**不是报价：所有镜头价格同样是示例 / 未核实。
    """
    body = tier if tier is not None else kit_of(b["price"])
    acc = b["price"].get("accessories", 500)
    remain = q["budget"] - body - acc
    usable = [l for l in lenses
              if l["brand_type"] in q["lens_groups"]
              and (b["mount"] in l["mount"] or l["mount"] == "多卡口")
              and l["price"] > 0]
    wide = sorted([l for l in usable if lens_min_focal(l) <= 18],
                  key=lambda x: x["price"])
    fast = sorted([l for l in usable if lens_max_aperture(l) <= 2.0],
                  key=lambda x: x["price"])
    w = wide[0] if wide else None
    p = next((l for l in fast if not w or l["id"] != w["id"]), None)
    both = (w["price"] if w else 0) + (p["price"] if p else 0)
    return {"body_tier": body, "accessories": acc, "remaining": remain,
            "wide": w, "portrait": p, "both_total": both,
            "fits_both": bool(w and p) and both <= remain,
            "short_by": max(0, both - remain)}


PRESETS = {
    "hiker": dict(budget=10000, sensor="any", scenes="travel,landscape",
                  priorities="light", current_gear="xiaomi_13pro", existing_kit="none",
                  trek_km=20, hand_size="small", height=170, tendinitis=True,
                  output="wechat", expertise="enthusiast", social=0.05,
                  pains="wide,pixels,tele,post", constraints="phone_battery,time_scarce",
                  finance="transitional_ok,include_user_sample",
                  abilities="can_raw,willing_post,buy_fast_lens,static_subject",
                  lens_groups="原厂,副厂,国产"),
    "student": dict(budget=6000, sensor="any", scenes="street,travel", priorities="light",
                    current_gear="phone_other", existing_kit="some", trek_km=5,
                    hand_size="small", height=170, tendinitis=False, output="wechat",
                    expertise="novice", social=0.25, pains="pixels,tele,battery",
                    constraints="money_scarce", finance="accept_used,transitional_ok",
                    abilities="", lens_groups="原厂,副厂,国产"),
    "vlogger": dict(budget=14000, sensor="any", scenes="video,workflow", priorities="ibis,video_spec",
                    current_gear="phone_other", existing_kit="none", trek_km=5,
                    hand_size="medium", height=170, tendinitis=False, output="douyin",
                    expertise="enthusiast", social=0.20, pains="lowlight,dynamic",
                    constraints="time_scarce", finance="", abilities="can_raw",
                    lens_groups="原厂,副厂,国产"),
    # 用户 2026-11-26 现场提问：总预算 10000，功能尽可能多，又拍风光又拍人像
    "allround_10k": dict(budget=10000, sensor="any", scenes="landscape,portrait,travel",
                         priorities="light,af", current_gear="phone_other", existing_kit="none",
                         trek_km=8, hand_size="medium", height=170, tendinitis=False,
                         output="xiaohongshu", expertise="enthusiast", social=0.15,
                         pains="wide,pixels,tele", constraints="money_scarce",
                         finance="transitional_ok", abilities="can_raw,willing_post,buy_fast_lens",
                         lens_groups="原厂,副厂,国产"),
    "print": dict(budget=30000, sensor="全画幅", scenes="landscape", priorities="",
                  current_gear="old_camera", existing_kit="lenses", trek_km=10,
                  hand_size="large", height=180, tendinitis=True, output="print",
                  expertise="power", social=0.10, pains="pixels,dynamic",
                  constraints="", finance="", abilities="can_raw,willing_post",
                  lens_groups="原厂,副厂,国产"),
}

PAIN_LABEL = {"wide": "广角不够 / 拍不全", "tele": "长焦不行 / 拉不远",
              "pixels": "像素 / 清晰度不够", "lowlight": "暗光噪点多",
              "dynamic": "动态范围 / 大光比", "battery": "设备电量不够用",
              "post": "后期太麻烦 / 上限低"}


def csv(v):
    return [x.strip() for x in (v or "").split(",") if x.strip()]


def final_of(p):
    return max(0, p["list_price"] - p["coupon"] - p["subsidy"] - p["trade_in"] + p["shipping"])


def kit_of(p):
    return final_of(p) + p["lens"] + p["accessories"]


def weight_limit(q, wp):
    limit = wp["limit_at_20km_g"] + (20 - q["trek_km"]) * 18
    if q["hand_size"] == "small":
        limit *= 0.88
    if q["tendinitis"]:
        limit *= 0.85
    return round(limit)


def compute(q, b, rules, lenses, rep):
    """返回逐条可复算的结果字典。与网页 compute() 一致。"""
    d = {"name": b["name"], "body": b, "parts": [], "cap_items": [], "comp_items": [], "blocked": None}
    limit = weight_limit(q, rules["weight_policy"])
    kit = kit_of(b["price"])
    # v3：慢变档位管决策，快变 spot 只管展示；每条价格运行期算新鲜度。
    tier = tier_of(b, CTX.get("tiers", {}))
    fs = price_freshness(b["price"], CTX.get("fp", {}), CTX.get("today"))
    d["price_tier"] = tier
    d["price_status"], d["price_age"], d["price_ttl"], d["price_label"] = fs
    # 价格不可信时不让它污染性价比与持有成本（严格模式）
    basis = kit
    if CTX.get("strict") and fs[0] != "fresh":
        basis = tier or kit
        d["price_basis"] = "tier（价格 %s，已改用慢变档位）" % fs[0]
    else:
        d["price_basis"] = "spot（价格 fresh）"
    d["price_basis_value"] = basis
    # 档位通过但示例整套价超预算 → 只警告，不否决（示例价不可信，不拿它做决策）
    d["budget_warning"] = (
        "示例整套价 %s 已超预算 %s（非实时价，仅供参考：换更便宜镜头或联网核实实时价）"
        % (money(kit), money(q["budget"]))) if kit > q["budget"] else None
    d["kit_suggestion"] = suggest_kit(q, b, lenses, tier)
    # P7 修正：整套重量按该卡口「能配到的最轻镜头」算，不能给套机硬塞一颗 520g 标变，
    # 否则 Z30+16-50(135g) 这类「愿意带出去」的方案会被误判过重而全部否决。
    usable = [l for l in lenses if l["brand_type"] in q["lens_groups"]
              and (b["mount"] in l["mount"] or l["mount"] == "多卡口")]
    lens_w = min((l["weight_g"] for l in usable), default=300)
    total_w = b["weight_g"] + lens_w
    d["kit"], d["total_w"], d["lens_w"], d["limit"] = kit, total_w, lens_w, limit

    veto_g = rules["weight_policy"].get("hard_veto_total_g", 900)
    # ---- M1 硬过滤 ----------------------------------------------------------
    if b.get("user_reported") and "include_user_sample" not in q["finance"]:
        d["blocked"] = "用户自述样例机（默认不参与真实推荐）"
    elif q["sensor"] != "any" and b["sensor"] != q["sensor"]:
        d["blocked"] = "画幅不符合"
    elif "accept_used" not in q["finance"] and b.get("used"):
        d["blocked"] = "你不接受二手"
    elif tier is not None and tier > q["budget"]:
        d["blocked"] = "价格档位 %s 超出预算（档位慢变，不依赖会过期的到手价）" % money(tier)
    elif tier is None and kit > q["budget"]:
        d["blocked"] = "整套超出预算（⚠️ 缺档位表，用示例价兜底，不可信）"
    elif q["trek_km"] >= 15 and total_w > veto_g:
        d["blocked"] = "徒步≥15km 且整套>%dg：一票否决" % veto_g
    elif total_w > limit * 1.35:
        d["blocked"] = "整套重量超出负重上限 %dg" % limit
    if d["blocked"]:
        return d

    # ---- M2 裸分 ------------------------------------------------------------
    base, detail = 0.0, []
    labels = rules["attr_labels"]
    for sid in q["scenes"]:
        sc = rules["scene_to_attributes"].get(sid, {})
        for a, w in sc.items():
            v = b["attrs"].get(a, 0) * w
            base += v
            detail.append({"label": labels.get(a, a), "scene": rules["scene_labels"].get(sid, sid), "w": w, "v": v})
    for pid in q["priorities"]:
        p = rules["priority_boost"].get(pid)
        if not p:
            continue
        v = b["attrs"].get(p["attr"], 0) * p["weight"]
        base += v
        detail.append({"label": labels.get(p["attr"], p["attr"]), "scene": "特别在意：" + p["label"], "w": p["weight"], "v": v})
    d["base"], d["detail"] = base, detail

    # ---- M7a 品牌加分（已过 banned_rules；口碑 outdated/disputed 权重恒 0）----
    bonus = 0.0
    for r in rules["brand_bonus"]:
        if r["brand"] != b["brand"]:
            continue
        ok = True
        for n in r["requires"]:
            if n == "jpeg_only":
                ok = "can_raw" not in q["abilities"]
            elif n == "accept_used":
                ok = "accept_used" in q["finance"]
            elif n == "low_budget":
                ok = "money_scarce" in q["constraints"]
            elif n == "full_frame":
                ok = b["sensor"] == "全画幅"
            else:
                ok = n in q["scenes"]
            if not ok:
                break
        if ok:
            bonus += r["weight"]
            d["parts"].append({"k": "品牌加分 " + r["id"], "v": r["weight"],
                               "why": r["why"] + " [" + r["evidence"] + " 级，已过时间戳检查]"})
    d["bonus"] = bonus

    # ---- M7b 社交认同（用户可调显式维度）-----------------------------------
    social = q["social"] * b.get("social_perception", 0.5)
    d["social"] = social
    if social > 0:
        d["parts"].append({"k": "社交认同（你拉高的权重）", "v": social,
                           "why": "social_weight × 该机型社交认知示例分"})

    # ---- M2b 补偿（P5）------------------------------------------------------
    comp_gain, comp_cost = 0.0, 0.0
    shortfall = {
        "dynamic_range": 1 - b["attrs"].get("dynamic_range", 0),
        "low_light_noise": 1 - b["attrs"].get("dynamic_range", 0),
        "total_light": 1 - (b["attrs"].get("dynamic_range", 0) * 0.5 + 0.35),
    }
    caps = rules["output_caps"][q["output"]].get("caps", {})
    for cat, means in rules["compensations"].items():
        if cat.startswith("_"):
            continue
        for m in means:
            req = m.get("requires")
            if req and req not in q["abilities"]:
                continue
            capped = ("超分" in m["means"]) and (caps.get("megapixels_score", 1) < 0.5)
            g = m["gain"] * shortfall.get(cat, 0) * (0.3 if capped else 1.0)
            c = m.get("cost_min", 0) * 0.006 + m.get("cost_money", 0) / 6000.0
            comp_gain += g
            comp_cost += c
            d["comp_items"].append({"cat": cat, "means": m["means"], "gain": g, "cost": c,
                                   "note": m["note"] + ("（输出端已压缩，超分收益打折）" if capped else "")})
    d["comp_gain"], d["comp_cost"] = comp_gain, comp_cost

    # ---- M3 输出端天花板（P6）----------------------------------------------
    oc = rules["output_caps"][q["output"]]
    pen = oc.get("over_cap_penalty", 0)
    cap_loss = 0.0
    for a, cap in caps.items():
        over = max(0, b["attrs"].get(a, 0) - cap)
        if over <= 0:
            continue
        w = 0.0
        for sid in q["scenes"]:
            w += rules["scene_to_attributes"].get(sid, {}).get(a, 0)
        for pid in q["priorities"]:
            p = rules["priority_boost"].get(pid, {})
            if p.get("attr") == a:
                w += p.get("weight", 0)
        loss = over * pen * max(0.3, w)
        cap_loss += loss
        d["cap_items"].append({"attr": labels.get(a, a), "cap": cap,
                               "actual": b["attrs"].get(a, 0), "loss": loss})
    d["cap_loss"] = cap_loss

    # ---- M4 携带意愿（P7，乘性）--------------------------------------------
    ratio = min(1.0, limit / max(1, total_w))
    carry = 0.55 + 0.45 * ratio ** rules["weight_policy"].get("carry_exponent", 0.9)
    d["carry"] = carry

    # ---- 汇总 ---------------------------------------------------------------
    pre = base + bonus + social + comp_gain - cap_loss - comp_cost
    d["score"] = max(0.0, pre) * carry
    d["parts"].insert(0, {"k": "裸分（场景+特别在意）", "v": base, "why": "按你选的场景逐条累加"})
    if comp_gain:
        d["parts"].append({"k": "短板补偿 +", "v": comp_gain, "why": "RAW/低ISO/大光圈/后期，见补偿清单"})
    if comp_cost:
        d["parts"].append({"k": "补偿代价 −", "v": -comp_cost, "why": "后期时间 + 器材钱"})
    if cap_loss:
        d["parts"].append({"k": "输出端超出部分折损 −", "v": -cap_loss, "why": oc["label"]})
    d["parts"].append({"k": "× 携带意愿因子", "v": carry,
                       "why": "整套 %dg（机身 %dg + 最轻镜头 %dg）/ 上限 %dg → 出勤率 %d%%" % (
                           total_w, b["weight_g"], lens_w, limit, round(carry * 100)), "mul": True})

    # ---- M5 边际性价比（v3：用 basis，不用可能过期的 spot）------------------
    d["value_ratio"] = d["score"] / (max(1, basis) / 1000.0)

    # ---- M6 持有成本（P4/P8）------------------------------------------------
    off = rules["secondary_use_offset"]
    offset = min(off["max_offset"], len(b.get("secondary_uses", [])) * off["per_use_offset"]) * basis
    dep = (max(0, b["first_launch_price"] - basis)
           if b.get("first_launch_price") else round(basis * 0.22))
    resale = round(basis * 0.15) if "care_resale" in q["finance"] else 0
    d["holding"] = {"depreciation": dep, "resale": resale, "offset": offset,
                    "net": max(0, dep + resale - offset)}

    # ---- 镜头搭配 -----------------------------------------------------------
    ls = [l for l in lenses if l["brand_type"] in q["lens_groups"]
          and (b["mount"] in l["mount"] or l["mount"] == "多卡口")]
    d["lenses"] = sorted(ls, key=lambda x: x["price"])[:4]
    return d


def profile(q, rules):
    oc = rules["output_caps"][q["output"]]
    main = ["补齐「" + PAIN_LABEL.get(p, p) + "」这个现有装备的短板" for p in q["pains"]]
    if "phone_battery" in q["constraints"]:
        main.append("手机电量是稀缺资源 → 需要一台独立拍摄设备，别再靠手机硬扛")
    if q["trek_km"] >= 15:
        main.append("单次 %dkm 徒步 → 整机重量与出勤率优先于纸面画质" % q["trek_km"])
    if not main:
        main.append("先明确「主要拍什么」，否则权重会分散")
    main.append("输出端是「" + oc["label"] + "」→ 超过这个上限的投入是白花钱")

    sec = ["整套预算 %s 必须同时覆盖机身 + 镜头 + 配件" % money(q["budget"]),
           "补偿能力：%s" % ("%d 项可用，短板可被部分抵消" % len(q["abilities"]) if q["abilities"] else "暂不具备，短板按裸分承担"),
           "社交认同权重 %.2f%s" % (q["social"], "（较高，品牌观感会明显影响排序）" if q["social"] >= 0.3 else "（较低）")]
    if q["height"] >= 180:
        sec.append("身高 ≥180cm：三脚架工作高度建议 ≥160cm，别买矮架")
    if q["hand_size"] == "small":
        sec.append("手小 / 劲儿小：优先 small grip、整机 ≤550g，避免单手长焦")
    if q["tendinitis"]:
        sec.append("担心筋膜炎：负重上限已下调 15%，优先塑料机身 + 轻定焦")

    skip = ["%s（在 %s 下超出 %.2f 的部分不计收益）" % (rules["attr_labels"].get(a, a), oc["label"], c)
            for a, c in oc.get("caps", {}).items()]
    skip.append("镜头 MTF 的最后一档差距、发电机是哪次工业革命的产物 —— 对你的目标不构成主要矛盾")

    should = ("phone_battery" in q["constraints"] or
              any(p in q["pains"] for p in ("wide", "tele", "pixels")))
    return {"main": main, "secondary": sec, "skip": skip, "should_add_device": should,
            "output_label": oc["label"], "output_note": oc["note"]}


def validate():
    rules, bodies = load("rules.json"), load("bodies.json")["bodies"]
    lenses, rep = load("lenses.json")["lenses"], load("reputation.json")["reputation"]
    errs = []
    keys = set(rules["attr_labels"].keys())
    for b in bodies:
        for k in ("weight_g", "role", "social_perception", "secondary_uses"):
            if k not in b:
                errs.append("%s 缺 v2 字段 %s" % (b["id"], k))
        for a in b["attrs"]:
            if a not in keys:
                errs.append("%s 的 attr '%s' 不在 attr_labels 里" % (b["id"], a))
    for r in rep:
        for k in ("as_of", "status", "source_type", "bias"):
            if k not in r:
                errs.append("口碑 %s 缺 %s" % (r["id"], k))
        if r["status"] not in ("current", "improved", "outdated", "disputed"):
            errs.append("口碑 %s status 非法" % r["id"])
        if r["status"] in ("outdated", "disputed") and r["weight"] != 0:
            errs.append("口碑 %s 已过时/存疑但权重非 0" % r["id"])
    for l in lenses:
        if l["brand_type"] not in ("原厂", "副厂", "国产"):
            errs.append("镜头 %s brand_type 非法" % l["id"])
    print("数据校验：机身 %d / 镜头 %d / 口碑 %d / 输出端 %d" % (
        len(bodies), len(lenses), len(rep), len(rules["output_caps"]) - 1))
    if errs:
        print("❌ 发现 %d 个问题：" % len(errs))
        for e in errs:
            print("  · " + e)
        return 1
    print("✅ 全部通过：v2 字段、属性名、口碑状态与权重、镜头分类均合法")
    return 0


def build_parser():
    ap = argparse.ArgumentParser(description="相机选购顾问 v2 · 可解释推荐引擎")
    ap.add_argument("--preset", choices=list(PRESETS), help="载入预设身份（口述原例 / 学生党 / vlog / 打印）")
    ap.add_argument("--budget", type=float, default=10000)
    ap.add_argument("--sensor", default="any")
    ap.add_argument("--scenes", default="travel")
    ap.add_argument("--priorities", default="")
    ap.add_argument("--current-gear", default="none")
    ap.add_argument("--existing-kit", default="none")
    ap.add_argument("--trek-km", type=int, default=0)
    ap.add_argument("--hand-size", default="medium")
    ap.add_argument("--height", type=int, default=170)
    ap.add_argument("--tendinitis", action="store_true")
    ap.add_argument("--output", default="wechat", help="wechat/douyin/xiaohongshu/bilibili/print/commercial")
    ap.add_argument("--expertise", default="enthusiast")
    ap.add_argument("--social", type=float, default=0.15)
    ap.add_argument("--pains", default="")
    ap.add_argument("--constraints", default="")
    ap.add_argument("--finance", default="")
    ap.add_argument("--abilities", default="")
    ap.add_argument("--lens-groups", default="原厂,副厂,国产")
    ap.add_argument("--top", type=int, default=3)
    ap.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    ap.add_argument("--validate", action="store_true", help="只校验数据文件")
    ap.add_argument("--no-strict-price", action="store_true",
                    help="关闭严格价格模式（不推荐，仅供对照实验）")
    ap.add_argument("--price-report", action="store_true", help="只打印价格新鲜度汇总")
    return ap


def make_q(args):
    base = dict(budget=args.budget, sensor=args.sensor, scenes=csv(args.scenes),
                priorities=csv(args.priorities), current_gear=args.current_gear,
                existing_kit=args.existing_kit, trek_km=args.trek_km,
                hand_size=args.hand_size, height=args.height, tendinitis=args.tendinitis,
                output=args.output, expertise=args.expertise, social=args.social,
                pains=csv(args.pains), constraints=csv(args.constraints),
                finance=csv(args.finance), abilities=csv(args.abilities),
                lens_groups=csv(args.lens_groups))
    if args.preset:
        p = PRESETS[args.preset]
        # 命令行显式给出的项优先：这里简化为 preset 全量覆盖（用 --preset 时不另传覆盖项）
        for k, v in p.items():
            if k in ("scenes", "priorities", "pains", "constraints", "finance", "abilities", "lens_groups"):
                base[k] = csv(v)
            else:
                base[k] = v
    return base


def main():
    args = build_parser().parse_args()
    if args.validate:
        return validate()

    rules = load("rules.json")
    bodies = load("bodies.json")["bodies"]
    lenses = load("lenses.json")["lenses"]
    rep = load("reputation.json")["reputation"]
    tiers = load_optional("price_tiers.json", {}).get("tiers", {})
    fp = load_optional("freshness_policy.json", {"default_ttl_days": 7,
                                                 "trusted_confidence": ["verified"]})
    today = datetime.date.today()
    CTX.update({"tiers": tiers, "fp": fp, "today": today,
                "strict": not args.no_strict_price})
    summary = freshness_summary(bodies, fp, today)
    if args.price_report:
        print("价格新鲜度汇总：", json.dumps(summary, ensure_ascii=False))
        return 0
    q = make_q(args)

    bad = [x for x in q["scenes"] if x not in rules["scene_to_attributes"]]
    if bad:
        sys.exit("未知场景 %s，可用：%s" % (bad, ", ".join(rules["scene_to_attributes"])))
    if q["output"] not in rules["output_caps"]:
        sys.exit("未知输出端 %s，可用：%s" % (q["output"], ", ".join(k for k in rules["output_caps"] if k[0] != "_")))

    allx = [compute(q, b, rules, lenses, rep) for b in bodies]
    valid = sorted([x for x in allx if not x["blocked"]], key=lambda x: x["score"], reverse=True)
    top, blocked = valid[:args.top], [x for x in allx if x["blocked"]]
    prof = profile(q, rules)

    if args.json:
        out = {"schema_version": "3.0", "notice": "示例数据，非实时报价，禁止用于下单",
               "price_freshness": summary,
               "input": {k: v for k, v in q.items()},
               "profile": prof,
               "results": [{"rank": i + 1, "name": d["name"], "score": round(d["score"], 4),
                            "kit": d["kit"], "value_ratio": round(d["value_ratio"], 4),
                            "parts": d["parts"], "comp_items": d["comp_items"],
                            "cap_items": d["cap_items"], "holding": d["holding"],
                            "lenses": [l["name"] for l in d["lenses"]],
                            "price_confidence": d["body"]["price"]["confidence"],
                            "price_status": d["price_status"], "price_label": d["price_label"],
                            "price_tier": d["price_tier"], "price_basis": d["price_basis"],
                            "budget_warning": d["budget_warning"],
                            "kit_suggestion": {k: (v["name"] if isinstance(v, dict) and "name" in v else v)
                                               for k, v in d["kit_suggestion"].items()}}
                           for i, d in enumerate(top)],
               "blocked": [{"name": x["name"], "reason": x["blocked"]} for x in blocked]}
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    print("=" * 74)
    print("相机选购顾问 v2 · 可解释推荐（示例数据，非实时报价）")
    print("=" * 74)
    print("输入：预算 %s ｜ 画幅 %s ｜ 场景 %s ｜ 输出端 %s" % (
        money(q["budget"]), q["sensor"], "、".join(rules["scene_labels"].get(s, s) for s in q["scenes"]),
        rules["output_caps"][q["output"]]["label"]))
    print("      现有装备 %s ｜ 徒步 %dkm ｜ 手型 %s ｜ 补偿能力 %d 项 ｜ 社交权重 %.2f" % (
        q["current_gear"], q["trek_km"], q["hand_size"], len(q["abilities"]), q["social"]))
    print("候选 %d 台，通过硬过滤 %d 台，排除 %d 台" % (len(allx), len(valid), len(blocked)))
    print("⚠️ 价格全部是示例 / 举证 / 用户自述未核实，禁止用于下单；所有系数为示例标定、未实证。")
    print("价格新鲜度：fresh %d / stale %d / unverified %d ｜ 观测基准日 %s" % (
        summary["fresh"], summary["stale"], summary["unverified"], today))
    if summary["all_stale"]:
        print("🚨 本结果仅为规则排序，不含任何实时到手价结论，请联网复核。")
        print("   预算硬过滤已改用慢变档位 data/price_tiers.json，不用会过期的到手价。")
    print()
    print("── 用户画像（只给对你这个目标有用的信息，不做全才）──")
    print("【主要矛盾】")
    for x in prof["main"]:
        print("  · " + x)
    print("【次要矛盾】")
    for x in prof["secondary"]:
        print("  · " + x)
    print("【不必纠结】")
    for x in prof["skip"][:5]:
        print("  · " + x)
    print("【是否建议增加独立拍摄设备】", "建议要" if prof["should_add_device"] else "暂时不必")
    print()

    if not top:
        print("按当前条件，示例库里没有能整套配下来的机器。可放宽预算 / 负重 / 画幅，或加 --finance include_user_sample")
    for i, d in enumerate(top, 1):
        b, p = d["body"], d["body"]["price"]
        print("-" * 74)
        print("第 %d 名  %s   有效分 %.2f（相对排序用，不是绝对评分）" % (i, b["name"], d["score"]))
        print("       %s / %s / %s 卡口 ｜ %dg ｜ 角色 %s ｜ 第二用途 %s" % (
            b["brand"], b["sensor"], b["mount"], d["total_w"], b["role"],
            "、".join(b.get("secondary_uses", [])) or "无"))
        print("  有效分怎么来的（逐条可复算）：")
        for x in d["parts"]:
            print("    · %-24s %s" % (x["k"], ("×%.3f" % x["v"]) if x.get("mul") else
                                     ("+%.2f" % x["v"] if x["v"] >= 0 else "%.2f" % x["v"])))
            print("        ↳ %s" % x["why"])
        print("  为什么是它：")
        for x in sorted(d["detail"], key=lambda z: z["v"], reverse=True)[:4]:
            print("    · %-20s %.2f 分（来自「%s」）" % (x["label"], x["v"], x["scene"]))
        if d["comp_items"]:
            print("  短板补偿清单（田忌赛马）：")
            for x in d["comp_items"][:5]:
                print("    · %s → +%.2f，代价 %.0f 单位 ｜ %s" % (x["means"], x["gain"], x["cost"] * 100, x["note"]))
        if d["cap_items"]:
            print("  哪些钱是白花的（输出端天花板）：")
            for x in d["cap_items"][:4]:
                print("    · %s：机器 %.2f，但输出端只承载 %.2f → 折损 %.2f" % (
                    x["attr"], x["actual"], x["cap"], x["loss"]))
        print("  镜头搭配（原厂 / 副厂 / 国产）：")
        for l in (d["lenses"] or [x for x in lenses if b["mount"] in x["mount"]][:3]):
            print("    · [%s] %s · %dg · %s · MTF示例档 %s" % (
                l["brand_type"], l["name"], l["weight_g"], money(l["price"]) if l["price"] else "套机含", l["mtf_grade"]))
        print("  边际性价比 %.2f 分/千元 ｜ 持有成本净额 %s（折旧 %s + 二手折价 %s − 第二用途抵扣 %s）" % (
            d["value_ratio"], money(d["holding"]["net"]), money(d["holding"]["depreciation"]),
            money(d["holding"]["resale"]), money(d["holding"]["offset"])))
        print("  价格算式：挂牌 %s − 券 %s − 国补 %s + 运费 %s = 机身到手 %s；+ 镜头 %s + 配件 %s = 整套 %s" % (
            money(p["list_price"]), money(p["coupon"]), money(p["subsidy"]), money(p["shipping"]),
            money(final_of(p)), money(p["lens"]), money(p["accessories"]), money(d["kit"])))
        print("    观测日 %s ｜ 来源 %s ｜ 可信度 %s ｜ 价格状态 %s（%s）" % (
            p["observed_at"], p["origin"], p["confidence"], d["price_status"], d["price_label"]))
        print("    决策用档位 %s ｜ 计算基准 %s ｜ 展示用整套示例价 %s（非实时）" % (
            money(d["price_tier"]) if d["price_tier"] else "缺失",
            d["price_basis"], money(d["kit"])))
        if d["budget_warning"]:
            print("    ⚠️ " + d["budget_warning"])
        ks = d["kit_suggestion"]
        print("    预算怎么分（按慢变档位，非实时报价）：机身档位 %s + 配件 %s → 留给镜头 %s" % (
            money(ks["body_tier"]), money(ks["accessories"]), money(ks["remaining"])))
        if ks["wide"]:
            print("      · 风光广角：%s（示例 %s）%s" % (
                ks["wide"]["name"], money(ks["wide"]["price"]),
                "✓ 买得起" if ks["wide"]["price"] <= ks["remaining"] else "✗ 超剩余"))
        if ks["portrait"]:
            print("      · 人像大光圈：%s（示例 %s）%s" % (
                ks["portrait"]["name"], money(ks["portrait"]["price"]),
                "✓ 买得起" if ks["portrait"]["price"] <= ks["remaining"] else "✗ 超剩余"))
        if not ks["fits_both"]:
            print("      ⚠️ 这个预算内配不齐「广角 + 人像」两颗（合计 %s，还差约 %s）。"
                  "要么把预算提到约 %s，要么降一档机身。" % (
                      money(ks["both_total"]), money(ks["short_by"]),
                      money(q["budget"] + ks["short_by"])))

    print("-" * 74)
    print("被硬过滤掉的：")
    for x in blocked[:6]:
        print("  · %s —— %s" % (x["name"], x["blocked"]))
    if len(blocked) > 6:
        print("  · ……还有 %d 台" % (len(blocked) - 6))
    print()
    print("口碑时间戳（outdated / disputed 权重恒 0，不照抄旧结论）：")
    for r in rep:
        print("  [%s] %s ｜ %s ｜ as_of %s" % (r["status"], r["claim"], r["bias"], r["as_of"]))
    print()
    print("出处与完整方法论：docs/方法论.md / 10_用户方法论_第一性原理.md / 09_来源与核实记录.md")
    print("请把上面这段连同 08_给其他AI的吩咐 一起交给第二个模型做交叉论证。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
