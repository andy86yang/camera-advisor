#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v3 收尾补丁：预算超出警告 + 具体镜头搭配建议（回答「1 万预算用什么机身/镜头」）

起因：跑 --preset allround_10k 时发现，改用慢变档位做硬过滤后，
佳能 R7 的「示例整套价 10,698」已超 1 万却仍排第 1。档位管决策是对的，
但必须把「示例价超预算」显式提示出来，并给出在预算内怎么配镜头。

用法：
  python scripts/finalize_v3.py
  python scripts/rebuild_data.py
  python scripts/upgrade_v3.py --sync
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def patch(rel, pairs):
    p = os.path.join(ROOT, rel)
    with open(p, encoding="utf-8") as f:
        s = f.read()
    for old, new in pairs:
        if old not in s:
            raise SystemExit("❌ %s 找不到锚点：\n%s" % (rel, old[:200]))
        s = s.replace(old, new, 1)
    with open(p, "w", encoding="utf-8") as f:
        f.write(s)
    print("  ~ %s (%d 处)" % (rel, len(pairs)))


KIT_FUNCS = r'''

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
'''


def main():
    print("v3 收尾补丁")

    patch("engine/scoring.py", [
        ("import argparse\nimport datetime\nimport json\nimport os\nimport sys\n",
         "import argparse\nimport datetime\nimport json\nimport os\nimport re\nimport sys\n"),

        ('''    out["all_stale"] = out["fresh"] == 0
    return out
''',
         '''    out["all_stale"] = out["fresh"] == 0
    return out
''' + KIT_FUNCS),

        ('''    d["price_basis_value"] = basis
''',
         '''    d["price_basis_value"] = basis
    # 档位通过但示例整套价超预算 → 只警告，不否决（示例价不可信，不拿它做决策）
    d["budget_warning"] = (
        "示例整套价 %s 已超预算 %s（非实时价，仅供参考：换更便宜镜头或联网核实实时价）"
        % (money(kit), money(q["budget"]))) if kit > q["budget"] else None
    d["kit_suggestion"] = suggest_kit(q, b, lenses, tier)
'''),

        ('''        print("    决策用档位 %s ｜ 计算基准 %s ｜ 展示用整套示例价 %s（非实时）" % (
            money(d["price_tier"]) if d["price_tier"] else "缺失",
            d["price_basis"], money(d["kit"])))
''',
         '''        print("    决策用档位 %s ｜ 计算基准 %s ｜ 展示用整套示例价 %s（非实时）" % (
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
'''),

        ('''                            "price_status": d["price_status"], "price_label": d["price_label"],
                            "price_tier": d["price_tier"], "price_basis": d["price_basis"]}
''',
         '''                            "price_status": d["price_status"], "price_label": d["price_label"],
                            "price_tier": d["price_tier"], "price_basis": d["price_basis"],
                            "budget_warning": d["budget_warning"],
                            "kit_suggestion": {k: (v["name"] if isinstance(v, dict) and "name" in v else v)
                                               for k, v in d["kit_suggestion"].items()}}
'''),
    ])

    patch("scripts/web_template.html", [
        ('''  const basis=(fresh.status!=="fresh"&&tier!=null)?tier:kit;
''',
         '''  const basis=(fresh.status!=="fresh"&&tier!=null)?tier:kit;
  d.budgetWarning = kit>q.budget
    ? "示例整套价 "+fmt(kit)+" 已超预算 "+fmt(q.budget)+"（非实时价，仅供参考：换更便宜镜头或联网核实实时价）"
    : null;
'''),

        ('''         '<br><b>⚠️ 示例 / 非实时报价，禁止用于下单；本行数字只作展示，不参与排序</b></div></div>';
''',
         '''         '<br><b>⚠️ 示例 / 非实时报价，禁止用于下单；本行数字只作展示，不参与排序</b>'+
         (d.budgetWarning?'<br><b style="color:#b42318">⚠️ '+d.budgetWarning+'</b>':'')+'</div></div>';
'''),

        ('''      h+='</ul><div class="hint">MTF 档位为示例分级、非实测、未核实；真实选型须查实测 MTF 图。</div></div>';
''',
         '''      h+='</ul><div class="hint">MTF 档位为示例分级、非实测、未核实；真实选型须查实测 MTF 图。'+
         '<br>预算分配（慢变档位，非实时）：机身档位 '+(d.priceTier?fmt(d.priceTier):'缺失')+
         ' + 配件 '+fmt(p.accessories)+' → 留给镜头 '+fmt(Math.max(0,q.budget-(d.priceTier||finalOf(p))-p.accessories))+
         '。上面按价格从低到高列了 4 颗，先看能同时买下几颗，别只看单颗。</div></div>';
'''),
    ])

    print("完成。接着跑 rebuild_data.py 与 upgrade_v3.py --sync")


if __name__ == "__main__":
    main()
