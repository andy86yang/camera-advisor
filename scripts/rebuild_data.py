#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
相机选购顾问 v2 · 数据与网页重建脚本（零外部依赖，纯标准库）

做四件事：
  1. 读 data/bodies.v1.json + rules.v1.json，追加 v2 字段（重量/人体工学/第二用途/
     社交认知/首发价/角色），并补入 Nikon Z30（用户自述样例）。
  2. 生成 lenses.json / reputation.json / price_history.json / rules.json(v2)。
  3. 把 data/*.json 同步到会话目录的 06_MVP/data 与 07_camera-advisor-skill/references。
  4. 读 scripts/web_template.html，把全部数据注入 /*__DATA_V2__*/，生成
     app/index.html 与 06_MVP/index.html（单文件、离线双击可开）。

用法：python scripts/rebuild_data.py
改数据请改本文件里的常量后重跑，不要手改生成的 JSON —— 保证三处永远一致。
"""
import json
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # 仓库根
SESSION = os.path.dirname(ROOT)                                      # 会话产物目录
DATA = os.path.join(ROOT, "data")
SCRIPTS = os.path.join(ROOT, "scripts")

REVIEWED = "2026-11-25"
NOTICE = ("示例数据。规格为公开资料归纳，价格为举证/占位，非实时报价，禁止用于下单。"
          "attrs 一律「越高越好」0~1。v2 新增字段见 docs/方法论.md。")


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def dump(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


# ---------------------------------------------------------------------------
# 1. 机身扩展字段（P3 过渡机 / P7 人体工学 / P8 第二用途 / P10 社交认知 / P4 首发价）
# ---------------------------------------------------------------------------
# weight_g 为整机含电池近似值（示例归纳，未实测）；material/grip 为示例分级。
EXT = {
    "canon_r8":     dict(weight_g=461, material="工程塑料+金属骨架", grip="medium", release_year=2023, role="primary",      secondary_uses=[],                      social_perception=0.70, first_launch_price=10499),
    "canon_r7":     dict(weight_g=612, material="镁合金顶盖",        grip="medium", release_year=2022, role="primary",      secondary_uses=[],                      social_perception=0.65, first_launch_price=8999),
    "sony_a6700":   dict(weight_g=493, material="工程塑料",          grip="small",  release_year=2023, role="primary",      secondary_uses=["vlog"],                 social_perception=0.75, first_launch_price=9999),
    "sony_a7c2":    dict(weight_g=514, material="镁合金",            grip="small",  release_year=2023, role="primary",      secondary_uses=[],                      social_perception=0.85, first_launch_price=12999),
    "nikon_z5ii":   dict(weight_g=700, material="镁合金",            grip="large",  release_year=2025, role="primary",      secondary_uses=[],                      social_perception=0.60, first_launch_price=9999),
    "nikon_d750":   dict(weight_g=840, material="镁合金+塑料",        grip="large",  release_year=2014, role="transitional", secondary_uses=["备机"],                 social_perception=0.50, first_launch_price=12000),
    "fuji_xt5":     dict(weight_g=557, material="镁合金",            grip="medium", release_year=2022, role="primary",      secondary_uses=[],                      social_perception=0.90, first_launch_price=11990),
    "fuji_x100vi":  dict(weight_g=521, material="镁合金",            grip="small",  release_year=2024, role="primary",      secondary_uses=["街拍备机"],             social_perception=0.95, first_launch_price=11390),
    "lumix_s5ii":   dict(weight_g=740, material="镁合金",            grip="large",  release_year=2023, role="primary",      secondary_uses=[],                      social_perception=0.55, first_launch_price=12999),
    "lumix_gh7":    dict(weight_g=805, material="镁合金",            grip="large",  release_year=2024, role="primary",      secondary_uses=[],                      social_perception=0.60, first_launch_price=13999),
    "om1ii":        dict(weight_g=511, material="镁合金",            grip="medium", release_year=2024, role="primary",      secondary_uses=[],                      social_perception=0.55, first_launch_price=15999),
}

# 用户口述里的那台过渡机。价格点来自用户自述、未核实，只作 price_history 的样例，
# 不参与真实推荐计算（confidence=user_reported，界面标「用户自述样例」）。
Z30 = {
    "id": "nikon_z30",
    "name": "尼康 Z30 + 16-50 套机（用户自述样例）",
    "brand": "Nikon", "sensor": "APS-C", "mount": "Z", "used": False,
    "role": "transitional", "release_year": 2022,
    "weight_g": 405, "material": "工程塑料", "grip": "small",
    "secondary_uses": ["vlog", "直播副机位", "备机"],
    "social_perception": 0.50, "first_launch_price": 4799,
    "user_reported": True,
    "note": "用户口述：25-11 以 3006 购入，26 双 11 约 3000；机身+双套一年折旧约 1000。数据未核实",
    "attrs": {
        "jpeg_skin_tone": .68, "eye_af": .75, "portrait_prime_count": .50,
        "ibis_stops": 0, "log_lut_tools": .35, "unlimited_record": .50,
        "bit_depth": .50, "audio_io": .25, "third_party_lens_breadth": .50,
        "system_tiers": .50, "film_simulations": .25, "physical_dials": .20,
        "compact_size": .95, "weight_score": .95, "weather_sealing": .30,
        "crop_advantage": .65, "tele_advantage": .70,
        "dynamic_range": .60, "megapixels_score": .50,
    },
    "price": {
        "list_price": 3000, "coupon": 0, "subsidy": 0,
        "subsidy_note": "用户自述时点价，未核实；不参与国补口径判定",
        "trade_in": 0, "shipping": 0, "lens": 0,
        "lens_name": "Z DX 16-50mm（套机含）", "accessories": 300,
        "origin": "用户自述 / 未核实（2026 双 11 时点）",
        "observed_at": "2026-11-11", "confidence": "user_reported",
    },
}


# ---------------------------------------------------------------------------
# 2. 镜头库：原厂 / 副厂（腾龙·适马）/ 国产（维卓仕·老蛙·七工匠）+ MTF 示例档
#    mtf_grade 全部是「示例分级、非实测、未核实」，只用于演示边际曲线，不许当实测结论。
# ---------------------------------------------------------------------------
LENSES = [
    # 原厂
    dict(id="nikon_z_1650", name="NIKKOR Z DX 16-50mm f/3.5-6.3 VR", brand="Nikon", brand_type="原厂", mount="Z", focal="16-50", aperture="3.5-6.3", weight_g=135, price=0, mtf_grade="B", note="套机头，塑料、极轻；爬山友好", marginal_note="轻便带来的出勤率收益，在徒步场景常大于画质损失"),
    dict(id="nikon_z_50250", name="NIKKOR Z DX 50-250mm f/4.5-6.3 VR", brand="Nikon", brand_type="原厂", mount="Z", focal="50-250", aperture="4.5-6.3", weight_g=405, price=1395, mtf_grade="B", note="用户自述从 1700/1800 降到 1395/1400（未核实）", marginal_note="长焦端补齐「手机长焦不行」的痛点；但发朋友圈时 250mm 与 50mm 的差距会被压缩"),
    dict(id="canon_rf_5018", name="RF 50mm F1.8 STM", brand="Canon", brand_type="原厂", mount="RF", focal="50", aperture="1.8", weight_g=160, price=1599, mtf_grade="B", note="低价大光圈定焦", marginal_note="F1.8→F1.2 的进光增益，在 ISO100+RAW 下边际收益快速递减"),
    dict(id="canon_rfs_18150", name="RF-S 18-150mm F3.5-6.3", brand="Canon", brand_type="原厂", mount="RF", focal="18-150", aperture="3.5-6.3", weight_g=310, price=1999, mtf_grade="B", note="APS-C 一镜走天下", marginal_note="一镜覆盖减少换镜与背负，属「愿意带出去」维度"),
    dict(id="sony_e_1655", name="E 16-55mm F2.8 G", brand="Sony", brand_type="原厂", mount="E", focal="16-55", aperture="2.8", weight_g=494, price=2299, mtf_grade="A", note="APS-C 标变标杆", marginal_note="恒定 2.8 的收益在白天户外几乎用不满，夜里才体现"),
    dict(id="fuji_xf_23", name="XF 23mm F2 R WR", brand="Fujifilm", brand_type="原厂", mount="X", focal="23", aperture="2.0", weight_g=180, price=2990, mtf_grade="A", note="小巧定焦", marginal_note="与胶片模拟配合，直出收益高；纯 RAW 用户收益下降"),
    dict(id="lumix_s_5018", name="Lumix S 50mm F1.8", brand="Panasonic", brand_type="原厂", mount="L", focal="50", aperture="1.8", weight_g=300, price=2499, mtf_grade="B", note="L 卡口低价定焦", marginal_note="L 卡口副厂分摊成本，长期系统成本下降"),
    # 副厂
    dict(id="tamron_1770", name="腾龙 17-70mm F2.8 Di III-A VC RXD", brand="Tamron", brand_type="副厂", mount="E", focal="17-70", aperture="2.8", weight_g=525, price=4290, mtf_grade="A-", note="索尼 APS-C 恒定 2.8 + 防抖，副厂标杆", marginal_note="副厂近年素质已追近原厂；「副厂不如原厂」属过时口碑（P9）"),
    dict(id="tamron_28200", name="腾龙 28-200mm F2.8-5.6 Di III RXD", brand="Tamron", brand_type="副厂", mount="E", focal="28-200", aperture="2.8-5.6", weight_g=575, price=4690, mtf_grade="B+", note="大变焦旅行头", marginal_note="一颗顶两颗，背负成本下降；但全焦段画质不均"),
    dict(id="sigma_1850", name="适马 18-50mm F2.8 DC DN Contemporary", brand="Sigma", brand_type="副厂", mount="E/Z/X", focal="18-50", aperture="2.8", weight_g=290, price=2399, mtf_grade="A-", note="多卡口、290g 恒定 2.8", marginal_note="轻 + 便宜 + 恒定光圈，是「田忌赛马」型选择"),
    dict(id="sigma_56", name="适马 56mm F1.4 DC DN Contemporary", brand="Sigma", brand_type="副厂", mount="E/Z/X", focal="56", aperture="1.4", weight_g=280, price=1999, mtf_grade="A", note="APS-C 人像定焦", marginal_note="等效 85mm 人像，价格远低于原厂同级"),
    dict(id="sigma_2470", name="适马 24-70mm F2.8 DG DN Art", brand="Sigma", brand_type="副厂", mount="E/L", focal="24-70", aperture="2.8", weight_g=830, price=5999, mtf_grade="A", note="全幅标变", marginal_note="830g 对徒步是明显负担，需与「愿意带出去」对冲"),
    # 国产
    dict(id="viltrox_13", name="维卓仕 AF 13mm F1.4 XF", brand="Viltrox", brand_type="国产", mount="X", focal="13", aperture="1.4", weight_g=420, price=2299, mtf_grade="B+", note="国产自动对焦超广角", marginal_note="补齐「爬山要广角」痛点；国产头已非「只能玩玩」（P9）"),
    dict(id="viltrox_75", name="维卓仕 AF 75mm F1.2 Pro", brand="Viltrox", brand_type="国产", mount="X/Z/E", focal="75", aperture="1.2", weight_g=670, price=3499, mtf_grade="A-", note="F1.2 超大光圈自动头", marginal_note="对应用户口述「不用 1.8 用 1.2」的补光思路；但 670g 需计入负重"),
    dict(id="viltrox_27", name="维卓仕 AF 27mm F1.2 Pro", brand="Viltrox", brand_type="国产", mount="X/Z/E", focal="27", aperture="1.2", weight_g=560, price=2999, mtf_grade="A-", note="国产大光圈标准视角", marginal_note="暗光补偿手段之一，成本远低于换全画幅机身"),
    dict(id="laowa_9", name="老蛙 9mm F2.8 C&D-Dreamer", brand="Laowa", brand_type="国产", mount="多卡口", focal="9", aperture="2.8", weight_g=215, price=1499, mtf_grade="B", note="215g 超广角、手动", marginal_note="轻+广角，正对徒步风景；手动对焦是补偿成本"),
    dict(id="laowa_100", name="老蛙 100mm F2.8 2:1 微距", brand="Laowa", brand_type="国产", mount="多卡口", focal="100", aperture="2.8", weight_g=638, price=2699, mtf_grade="A-", note="2:1 微距", marginal_note="对应用户口述「手机微距还可以」，若已有手机微距，此头边际收益低"),
    dict(id="7artisans_35", name="七工匠 35mm F1.4（手动）", brand="7artisans", brand_type="国产", mount="多卡口", focal="35", aperture="1.4", weight_g=228, price=499, mtf_grade="C", note="极低价手动定焦", marginal_note="零成本试错大光圈的入门路径；画质与手感是明确短板"),
]


# ---------------------------------------------------------------------------
# 3. 口碑 / 来源五分类（P9 时间戳 + P10 多元来源 + 利益标注 + 已改善状态）
#    status: current(现行) / improved(历史问题已改善) / outdated(已过时) / disputed(存疑)
# ---------------------------------------------------------------------------
SOURCE_TYPES = {
    "official":   {"label": "品牌官方", "default_weight": 0.35, "bias": "王婆卖瓜，倾向只列优点、隐藏缺点", "note": "占比可高，但不可全信；必须标明是厂商自述"},
    "media":      {"label": "权威媒体 / 头部主播", "default_weight": 0.20, "bias": "可能受品牌方、广告商、二手商利益驱动", "note": "敌对媒体放大缺点，友好媒体只夸优点；名气 ≠ 专业度"},
    "consumer":   {"label": "消费者 / 实际使用者", "default_weight": 0.25, "bias": "样本偏个人、易以个别体验泛化", "note": "品牌教育用户有产品周期；设计有的过于超前有的过于落后，使用者叙事能补官方盲区"},
    "outsider":   {"label": "圈外视角", "default_weight": 0.10, "bias": "不懂术语，但能反映社交观感与真实使用门槛", "note": "只看圈内人 = 圈内自嗨"},
    "measured":   {"label": "可复现实测 / 硬规格", "default_weight": 0.40, "bias": "测量条件差异", "note": "可量化，最高权重；但也要标测试条件"},
}

REPUTATION = [
    dict(id="Q01", claim="佳能直出肤色讨喜", brand="Canon", source_type="official", bias="厂商调校自述 + 社区口碑", as_of=REVIEWED, status="current", review_due="2027-05-25", weight=0.15, note="记忆色 / Portrait 照片风格，口碑级，只小额加分"),
    dict(id="Q02", claim="索尼 E 卡口镜头群广、产品线分层全", brand="Sony", source_type="measured", bias="可数规格", as_of=REVIEWED, status="current", review_due="2027-05-25", weight=0.20, note="第三方镜头数量与 FX/Cinema 分层可核实"),
    dict(id="Q03", claim="全画幅最便宜 = 尼康", brand="Nikon", source_type="media", bias="旧共识被新机型推翻", as_of=REVIEWED, status="outdated", review_due="已作废", weight=0.0, note="2026-11 全新机最低为佳能 EOS R8；仅二手语境常是尼康老单反。出处见 09 来源记录"),
    dict(id="Q04", claim="松下色彩更好", brand="Panasonic", source_type="consumer", bias="主观审美", as_of=REVIEWED, status="disputed", review_due="2027-02-25", weight=0.0, note="查不到量化证据；能核实的是视频工具链"),
    dict(id="Q05", claim="港版一定更便宜", brand="*", source_type="consumer", bias="忽略保修与国补", as_of=REVIEWED, status="outdated", review_due="已作废", weight=0.0, note="厂商税后统一价 + 国补只给国行；佳能中国保修条款已亲自复核"),
    dict(id="Q06", claim="富士胶片模拟是固件内 JPEG 管线", brand="Fujifilm", source_type="measured", bias="厂商规格可复现", as_of=REVIEWED, status="current", review_due="2027-05-25", weight=0.25, note="约 20 种、不影响 RAW，属硬事实"),
    dict(id="Q07", claim="副厂镜头素质普遍不如原厂", brand="Tamron/Sigma", source_type="media", bias="旧世代经验", as_of=REVIEWED, status="improved", review_due="2027-05-25", weight=0.05, note="腾龙/适马近年多支镜头已达 A- 档；曾经成立，现在不能照抄"),
    dict(id="Q08", claim="国产镜头只能玩玩", brand="Viltrox/Laowa/7artisans", source_type="media", bias="品牌歧视式旧标签", as_of=REVIEWED, status="improved", review_due="2027-05-25", weight=0.05, note="维卓仕自动对焦 F1.2、老蛙特殊规格已可用；曾经有问题≠现在还在错"),
    dict(id="Q09", claim="半画幅顶配只有富士 / 索尼", brand="*", source_type="media", bias="列举不全", as_of=REVIEWED, status="outdated", review_due="已作废", weight=0.0, note="漏了佳能 EOS R7"),
    dict(id="Q10", claim="一英寸底一定优于略小底", brand="*", source_type="media", bias="22/23 年阶段性共识", as_of="2023-06-01", status="outdated", review_due="已作废", weight=0.0, note="25/26 手机纷纷选略小底 + 可变光圈/一镜双目/RYYB/计算摄影，换动态范围与帧率；用户口述例证，未独立核实"),
]

# 跨领域教训：手机品牌的历史问题，用于演示「曾经犯过错 ≠ 现在还在错」。
# 明确：不参与相机打分，只作 P9 的教学条目。
CROSS_DOMAIN = [
    dict(brand="小米", issue="11 系列发热 / 烧 WiFi", status="improved", note="用户口述：后续机型已改善；要质疑但不能全盘否定"),
    dict(brand="华为", issue="疏油层 / 内存门 / 屏幕门 / 高价低配争议", status="improved", note="用户口述：早期事件后来未再出现；「现在确实高价低配」属当下评价，与历史问题分开"),
    dict(brand="OPPO / vivo", issue="「厂妹机」标签", status="outdated", note="用户口述：后来确实变厉害了，标签已过时"),
]


# ---------------------------------------------------------------------------
# 4. 价格史（P4）：持续采样而非大促快照；用户自述点单独标 user_reported
# ---------------------------------------------------------------------------
PRICE_HISTORY = {
    "schema_version": "2.0",
    "notice": "用户自述价格点未经核实，仅用于演示数据结构，禁止用于下单或真实推荐计算。",
    "sampling_policy": {
        "frequency": "daily",
        "not_event_driven": True,
        "why": "用户口述：50-250 的最大降幅发生在 7/8 月，双 11 双 12 反而无明显变化；只在 618/双 11 抓价会系统性漏掉真实低点",
        "required_fields": ["date", "price", "price_type", "region", "condition", "origin", "observed_at"],
        "retention": "全历史永不覆盖，Git 每次采样自动提交，天然留下价格曲线",
        "stale_after_days": 7,
    },
    "series": [
        {
            "item": "Nikon Z30 + 16-50 套机", "user_reported": True,
            "first_launch_price": 4799,
            "points": [
                dict(date="2025-11", price=3006, price_type="final_price", region="中国大陆", condition="全新", event="用户购入", origin="用户自述 / 未核实", observed_at=REVIEWED),
                dict(date="2026-07", price=None, price_type="unknown", region="中国大陆", condition="全新", event="口述提及此期间出现降价，无具体数字", origin="用户自述 / 未核实", observed_at=REVIEWED),
                dict(date="2026-11-11", price=3000, price_type="final_price", region="中国大陆", condition="全新", event="双 11", origin="用户自述 / 未核实", observed_at=REVIEWED),
            ],
            "lesson": "出了很多年的老机身仍在缓降，不存在『跌到底』；大促并未给出更低点",
            "date_uncertainty": "口述时间线有跳跃（部分年月表述不一），此处按口述相对顺序记录，不替用户补全日期",
        },
        {
            "item": "NIKKOR Z DX 50-250mm", "user_reported": True,
            "first_launch_price": None,
            "points": [
                dict(date="2025-03（口述，年份不确定）", price=1700, price_type="final_price", region="中国大陆", condition="全新", event="用户购入", origin="用户自述 / 未核实", observed_at=REVIEWED),
                dict(date="2026-03（口述）", price=1395, price_type="final_price", region="中国大陆", condition="全新", event="7/8 月前后降至 1395–1400", origin="用户自述 / 未核实", observed_at=REVIEWED),
                dict(date="2026-11-11", price=1400, price_type="final_price", region="中国大陆", condition="全新", event="双 11 未见明显变化", origin="用户自述 / 未核实", observed_at=REVIEWED),
            ],
            "lesson": "降幅发生在非大促月份；双 11 / 双 12 价格几乎不动",
            "date_uncertainty": "用户口述中出现「27 年三月份」等明显口误，年份以相对顺序推定并标注不确定",
        },
    ],
    "derived_metrics": ["holding_depreciation", "first_launch_premium", "relative_loss_reference_frame"],
    "relative_loss_note": "用户口述：一年机身加双套亏约 1000，但『冲首发那些人亏的更多』，所以『不算十分肉疼』——亏损感取决于参照系，引擎应同时给出绝对折旧与相对参照。",
}


# ---------------------------------------------------------------------------
# 5. v2 规则增量（P5 补偿 / P6 输出端 cap / P7 负重 / P8 第二用途 / P10 社交 / P11 画像）
# ---------------------------------------------------------------------------
V2_ADD = {
    "schema_version": "2.0",
    "v2_note": "本文件由 scripts/rebuild_data.py 生成。P1–P11 的方法论出处见 docs/方法论.md。",
    "compensations": {
        "_note": "P5：短板不是判决，是可被低成本/零成本手段补偿的量。gain 为有效分增益，cost 为代价。requires 对应问卷里的能力项。",
        "dynamic_range": [
            {"means": "拍 RAW 不拍 JPEG", "gain": 0.18, "cost_min": 5, "cost_money": 0, "requires": "can_raw", "note": "用户口述：RAW 可弥补动态范围不足"},
            {"means": "向右曝光（ETTR）", "gain": 0.10, "cost_min": 3, "cost_money": 0, "requires": "can_raw", "note": "用户口述：向右曝光压噪点"},
        ],
        "low_light_noise": [
            {"means": "锁 ISO 100 / 尽量低 ISO", "gain": 0.15, "cost_min": 1, "cost_money": 0, "requires": "can_raw", "note": "用户口述：强行锁 ISO 100"},
            {"means": "PS 降噪 / AI 降噪软件", "gain": 0.20, "cost_min": 15, "cost_money": 0, "requires": "willing_post", "note": "用户口述：后期 10–20 分钟可接近全幅效果"},
            {"means": "超分软件补像素", "gain": 0.12, "cost_min": 10, "cost_money": 0, "requires": "willing_post", "note": "只对静态照片、且输出端未 cap 时才有效"},
        ],
        "total_light": [
            {"means": "大光圈 F1.7 / F1.2 定焦（不用 F2.8 / F1.8）", "gain": 0.25, "cost_min": 0, "cost_money": 1500, "requires": "buy_fast_lens", "note": "用户口述：用 1.7、1.2 补总进光量；成本远低于换全幅"},
            {"means": "放慢快门 1/200 → 1/120 → 1/80", "gain": 0.10, "cost_min": 0, "cost_money": 0, "requires": "static_subject", "note": "只对静态题材成立，动态会糊"},
            {"means": "补常亮灯 / 手机手电筒", "gain": 0.08, "cost_min": 2, "cost_money": 0, "requires": "static_subject", "note": "用户口述：零成本补光"},
        ],
    },
    "output_caps": {
        "_note": "P6：收益由输出端决定。超过 cap 的属性按 over_cap_penalty 折损，天然产生『成本+80% 效果+8%』。",
        "wechat": {"label": "朋友圈 / 微信群（压到约 100–300KB）", "caps": {"megapixels_score": 0.25, "dynamic_range": 0.55, "bit_depth": 0.20, "ibis_stops": 0.40}, "over_cap_penalty": 0.15, "note": "10MB / 20MB 发出来都是 100 多 KB"},
        "douyin": {"label": "抖音 / 短视频（平台 1080P、手机屏 1080P）", "caps": {"megapixels_score": 0.20, "bit_depth": 0.35, "unlimited_record": 0.50}, "over_cap_penalty": 0.15, "note": "4K60 与 1080P60 在 1080P 屏上观感差距小；都是 60 帧；LUT 讨喜反而可能更赢"},
        "xiaohongshu": {"label": "小红书 / 图文", "caps": {"megapixels_score": 0.45, "dynamic_range": 0.70, "jpeg_skin_tone": 0.90}, "over_cap_penalty": 0.10, "note": "调色与直出观感权重上升"},
        "bilibili": {"label": "B 站 / 4K 交付", "caps": {"bit_depth": 0.95, "unlimited_record": 0.95, "log_lut_tools": 0.95}, "over_cap_penalty": 0.05, "note": "此时视频规格才真正值钱"},
        "print": {"label": "A3 以上打印 / 展览", "caps": {"megapixels_score": 1.0, "dynamic_range": 1.0}, "over_cap_penalty": 0.0, "note": "输出端不压缩，像素与动态范围收益不打折"},
        "commercial": {"label": "商业交付 / 客户要 RAW", "caps": {"megapixels_score": 1.0, "dynamic_range": 1.0, "bit_depth": 1.0}, "over_cap_penalty": 0.0, "note": "全流程不 cap，但成本与负重也要全额承担"},
    },
    "weight_policy": {
        "_note": "P7：重量是出勤率的代理变量，作乘性因子，不是普通加性小分。",
        "baseline_km": 5, "limit_at_20km_g": 700, "carry_exponent": 0.9,
        "hard_veto_total_g": 900,
        "hard_veto_when": "徒步 ≥ 15km 且 整套重量 > 900g",
        "total_weight_rule": "整套重量 = 机身重量 + 该卡口可配到的最轻镜头重量（不是固定标变），否则套机/轻定焦会被误判过重",
        "reason": "用户口述：爬山十几二十公里，塑料机身镜头轻才愿意带出去；金属合金很沉就不愿意拿；用多了手会得筋膜炎",
    },
    "ergonomics_profile": {
        "_note": "用户画像：个子高→三脚架要大；手小/劲儿小/年纪小→偏轻便。",
        "fields": ["hand_size", "grip_strength", "age_group", "height_cm", "tendinitis_concern"],
        "rules": [
            {"when": "height_cm >= 180", "advice": "三脚架工作高度建议 ≥ 160cm，否则长期弯腰"},
            {"when": "hand_size == small or grip_strength == low", "advice": "优先 small grip + 整机 ≤ 550g，避免单手长焦"},
            {"when": "tendinitis_concern", "advice": "负重上限下调 15%，并优先塑料机身 / 轻定焦"},
        ],
    },
    "secondary_use_offset": {
        "_note": "P8：有第二用途的机器换机时不必出二手，账面损失不落袋。",
        "per_use_offset": 0.06, "max_offset": 0.18,
        "reason": "用户口述：Z30 可作 vlog 机 / 直播副机位，退居二线，不存在因出二手造成的经济损失",
    },
    "social": {
        "_note": "P10：马斯洛除自我认同外还有社交；品牌文化与他人观感是真实需求，作为用户可调显式维度，不偷偷塞进品牌分。",
        "default_weight": 0.15, "min": 0.0, "max": 0.60,
        "label": "在意别人怎么看（品牌面子 / 社交认同）",
        "novice_mode": "小白不认识圈内大佬、不会判断谁恰饭，可信度判断由 AI 代做，界面不暴露权威加权表",
    },
    "source_types": SOURCE_TYPES,
    "profile_sections": ["主要矛盾", "次要矛盾", "不必纠结（不做全才）"],
    "expertise_levels": {
        "novice": {"label": "小白", "detail": "只给结论与主次矛盾，不列全部属性；可信度由 AI 代判"},
        "enthusiast": {"label": "爱好者", "detail": "给补偿清单与输出端 cap 说明"},
        "power": {"label": "发烧友", "detail": "全量逐条可复算打分 + MTF 档 + 来源五分类"},
    },
}

BANNED_ADD = [
    "任何品牌 / 口碑规则不带 as_of 与 status → 违反 P9，禁止入库",
    "把「曾经有过问题」直接写成「现在不行」→ 经验主义，违反 P9（应标 improved / 待复核）",
    "只在大促抓价 → 违反 P4，价格观测必须每日持续采样",
    "用裸参数直接加权、不考虑补偿与输出端 cap → 违反 P5/P6，等同照抄博主公式",
    "把重量当普通加性小分 → 违反 P7，必须是乘性出勤率因子",
    "把社交认同偷偷塞进品牌加分 → 违反 P10，必须是用户可调的显式维度",
]


# ---------------------------------------------------------------------------
# 执行
# ---------------------------------------------------------------------------
def build_bodies():
    base = load(os.path.join(DATA, "bodies.v1.json"))
    out = []
    for b in base["bodies"]:
        e = EXT.get(b["id"])
        if e:
            b.update(e)
        b.setdefault("role", "primary")
        b.setdefault("secondary_uses", [])
        b.setdefault("social_perception", 0.5)
        b.setdefault("first_launch_price", None)
        b.setdefault("user_reported", False)
        out.append(b)
    out.append(Z30)
    return {
        "schema_version": "2.0", "generated_at": REVIEWED, "notice": NOTICE,
        "v2_fields": {
            "weight_g": "整机含电池近似重量（示例归纳，未实测）",
            "material": "机身材质，关联 P7 负重与筋膜炎",
            "grip": "握持尺寸 small/medium/large，关联人体工学画像",
            "role": "primary | transitional（P3 过渡机策略）",
            "secondary_uses": "P8 第二用途，抵扣换机损失",
            "social_perception": "P10 社交认同示例分（0~1，用户可调权重）",
            "first_launch_price": "P4 首发价基线，用于算首发溢价与折旧",
            "user_reported": "true 表示来自用户自述、未核实，不参与真实推荐计算",
        },
        "bodies": out,
    }


def build_rules():
    r = load(os.path.join(DATA, "rules.v1.json"))
    r.update(V2_ADD)
    r["banned_rules"] = list(r.get("banned_rules", [])) + BANNED_ADD
    return r


def main():
    bodies = build_bodies()
    rules = build_rules()
    lenses = {
        "schema_version": "2.0", "generated_at": REVIEWED,
        "notice": "价格为示例 / 举证 / 未核实；mtf_grade 为示例分级、非实测、未核实，只用于演示边际曲线。",
        "brand_types": {"原厂": "机身厂商自有卡口镜头", "副厂": "腾龙 / 适马等独立镜头厂", "国产": "维卓仕 / 老蛙 / 七工匠等"},
        "mtf_note": "MTF 是镜头反差与分辨率的量化曲线；本库只给 A/A-/B+/B/C 示例档，真实选型须查实测 MTF 图，禁止把示例档当结论。",
        "lenses": LENSES,
    }
    reputation = {
        "schema_version": "2.0", "generated_at": REVIEWED,
        "notice": "每条口碑带来源类型 / 利益标注 / 观测日 / 状态 / 复核到期日；outdated 与 disputed 权重为 0，improved 只给低权重。",
        "status_def": {
            "current": "现行，按权重生效", "improved": "历史问题已改善，仅低权重，禁止照抄旧结论",
            "outdated": "已被现实推翻，权重 0", "disputed": "查不到足够证据，权重 0",
        },
        "source_types": SOURCE_TYPES,
        "reputation": REPUTATION,
        "cross_domain_lessons": {
            "notice": "手机品牌历史问题的教学条目，演示『曾经犯过错 ≠ 现在还在错』。**不参与相机打分**，均为用户口述 / 未核实。",
            "items": CROSS_DOMAIN,
        },
    }

    # 落到仓库 data/
    for name, obj in [("bodies.json", bodies), ("rules.json", rules),
                      ("lenses.json", lenses), ("reputation.json", reputation),
                      ("price_history.json", PRICE_HISTORY)]:
        dump(os.path.join(DATA, name), obj)

    # 同步到会话目录两处
    # 可移植性：clone 到别人机器上时，会话目录里的 06_MVP / 07_camera-advisor-skill
    # 不一定存在；只在父目录已存在时才同步，避免在仓库外乱建目录。
    targets = []
    for sub in ("06_MVP/data", "07_camera-advisor-skill/references"):
        p = os.path.join(SESSION, sub)
        if os.path.isdir(os.path.dirname(p)):
            targets.append(p)
    sync_names = ["bodies.json", "rules.json", "lenses.json", "reputation.json",
                  "price_history.json", "price_tiers.json", "freshness_policy.json",
                  "upstream_sources.json"]
    for t in targets:
        os.makedirs(t, exist_ok=True)
        for name in sync_names:
            shutil.copyfile(os.path.join(DATA, name), os.path.join(t, name))

    # 注入网页模板（模板与产物都在仓库里，clone 下来可直接开 app/index.html）
    tpl_path = os.path.join(SCRIPTS, "web_template.html")
    if os.path.exists(tpl_path):
        with open(tpl_path, encoding="utf-8") as f:
            tpl = f.read()
        embedded = {
            "bodies": bodies["bodies"],
            "rules": {
                "scene_labels": rules["scene_labels"],
                "attr_labels": rules["attr_labels"],
                "scene_to_attributes": rules["scene_to_attributes"],
                "priority_boost": rules["priority_boost"],
                "brand_bonus": rules["brand_bonus"],
                "evidence_levels": rules["evidence_levels"],
                "compensations": rules["compensations"],
                "output_caps": rules["output_caps"],
                "weight_policy": rules["weight_policy"],
                "ergonomics_profile": rules["ergonomics_profile"],
                "secondary_use_offset": rules["secondary_use_offset"],
                "social": rules["social"],
                "source_types": rules["source_types"],
                "banned_rules": rules["banned_rules"],
            },
            "lenses": lenses["lenses"],
            "reputation": reputation["reputation"],
            "price_history": PRICE_HISTORY["series"],
            "price_tiers": load(os.path.join(DATA, "price_tiers.json")).get("tiers", {}),
            "freshness_policy": load(os.path.join(DATA, "freshness_policy.json")),
            "upstream_sources": load(os.path.join(DATA, "upstream_sources.json")).get("sources", []),
        }
        js = "const DATA = " + json.dumps(embedded, ensure_ascii=False, separators=(",", ":")) + ";"
        html = tpl.replace("/*__DATA_V2__*/", js)
        for p in [os.path.join(ROOT, "app", "index.html"),
                  os.path.join(SESSION, "06_MVP", "index.html")]:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(html)
        print("网页注入完成：app/index.html + 06_MVP/index.html")
    else:
        print("⚠️ 未找到 web_template.html，跳过网页注入")

    print("v2 数据生成完成：机身 %d 台 / 镜头 %d 颗 / 口碑 %d 条 / 输出端 %d 种 / 价格序列 %d 组" % (
        len(bodies["bodies"]), len(LENSES), len(REPUTATION),
        len(rules["output_caps"]) - 1, len(PRICE_HISTORY["series"])))
    print("已同步到 06_MVP/data 与 07_camera-advisor-skill/references")


if __name__ == "__main__":
    main()
