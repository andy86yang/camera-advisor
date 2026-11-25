#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
camera-advisor v3 升级脚本（零外部依赖，可重复运行）

本轮回应三件事，全部落到**代码**而不是新写一堆 md：
  1. 用户：「开源项目我还没有加，你自己往里面加不行吗？」
     → 生成 UPSTREAM.md / data/upstream_sources.json / data/upstream/*，
       把通过 GitHub 接口亲自打开过的真实仓库与真实文件接进仓库。
  2. 用户：「不能实时联网，价格不就是错的吗？这部分怎么规避？」
     → 新增 data/price_tiers.json（慢变档位）与 data/freshness_policy.json；
       改 engine/scoring.py 与 scripts/web_template.html：
       预算硬过滤改用 tier（不依赖会过期的到手价）、每条价格运行期算 freshness、
       过期/未核实强制降级为「仅规则排序，不给到手价结论」。
  3. 用户：「先做成一个开源 GitHub 的 Skill 或项目就行，一步一步来」
     → 生成 skill/ 自包含目录，形态收敛为 GitHub 项目 + 可安装 Skill。

用法：
  python scripts/upgrade_v3.py            # 生成新文件 + 打补丁 + 建 skill/
  python scripts/upgrade_v3.py --sync     # 在 rebuild_data.py 之后跑：同步三处数据与引擎副本

改完必须按顺序跑：
  python scripts/upgrade_v3.py
  python scripts/rebuild_data.py
  python scripts/upgrade_v3.py --sync
  python engine/scoring.py --validate
"""
import datetime
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
SESSION = os.path.dirname(ROOT)
TODAY = "2026-11-26"


# ---------------------------------------------------------------------------
def W(rel, text):
    p = os.path.join(ROOT, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text.rstrip() + "\n")
    print("  + " + rel)


def dump(rel, obj):
    W(rel, json.dumps(obj, ensure_ascii=False, indent=2))


def append(rel, text):
    p = os.path.join(ROOT, rel)
    with open(p, "a", encoding="utf-8") as f:
        f.write("\n" + text.rstrip() + "\n")
    print("  ~ " + rel + " (追加)")


def patch(rel, pairs):
    """带断言的精确替换：锚点找不到就整脚本失败，绝不静默跳过。"""
    p = os.path.join(ROOT, rel)
    with open(p, encoding="utf-8") as f:
        s = f.read()
    for old, new in pairs:
        if old not in s:
            raise SystemExit("❌ %s 找不到锚点：\n%s" % (rel, old[:180]))
        s = s.replace(old, new, 1)
    with open(p, "w", encoding="utf-8") as f:
        f.write(s)
    print("  ~ %s (%d 处)" % (rel, len(pairs)))


# ---------------------------------------------------------------------------
# 1. 开源项目：真实核实过的仓库（2026-11-26 通过 GitHub 接口逐个打开）
# ---------------------------------------------------------------------------
SOURCES = [
    {
        "id": "lensfun", "full_name": "lensfun/lensfun",
        "url": "https://github.com/lensfun/lensfun",
        "stars": "未获取（未走 star 查询，只核实仓库与文件存在）",
        "license": "仓库根含 COPYING 与 COPYING.LESSER 两份许可文件（ GPL / LGPL 系）；未逐条读取条款，接入前须自查",
        "verified_how": "mcp__github__get_file_contents 亲自打开 / 与 /data/db 目录",
        "files_opened": ["/", "/data/db/lensfun-database.dtd", "/data/db/generic.xml"],
        "reused": "从 generic.xml 抽出真实卡口清单与 cropfactor，生成 data/upstream/lensfun_mounts.json；DTD 的 camera/lens/mount/cropfactor 字段结构作为我们数据契约的对照",
        "not_reused": "未复制其镜头校正 XML 数据体（体积大、许可需自查、且与本项目的选型打分不是同一用途）",
        "as_of": TODAY,
    },
    {
        "id": "gyroflow_lens_profiles", "full_name": "gyroflow/lens_profiles",
        "url": "https://github.com/gyroflow/lens_profiles",
        "stars": 106,
        "license": "仓库含 LICENSE 文件（未读取内容，接入前须自查）",
        "verified_how": "search_repositories 命中 + get_file_contents 亲自打开 / 与 /Nikon 目录",
        "files_opened": ["/", "/Nikon"],
        "reused": "从 /Nikon 真实文件名中筛出 Z30 与唯卓仕/七工匠/老蛙/铭匠/适马/腾龙的组合，生成 data/upstream/gyroflow_matched_lenses.json —— 用来证明「副厂国产镜头真实存在且被实际使用」，不是编的",
        "not_reused": "未复制 profile JSON（那是防抖畸变参数，不是价格或规格）",
        "as_of": TODAY,
    },
    {
        "id": "darktable", "full_name": "darktable-org/darktable",
        "url": "https://github.com/darktable-org/darktable",
        "stars": 13503,
        "license": "开源摄影工作流 / RAW 显影软件（许可证未读取，接入前须自查）",
        "verified_how": "search_repositories 命中（仓库 id 3791835）",
        "files_opened": ["（仅检索命中，未打开单个文件）"],
        "reused": "作为 P5「短板补偿」里 RAW 后期 / 降噪 / 超分的**开源可行工具**写进文档，替代只提 PS 的商业软件口径",
        "not_reused": "未编译、未集成其代码；本项目是选型工具不是修图工具",
        "as_of": TODAY,
    },
    {
        "id": "amazon_price_tracker", "full_name": "jakobowsky/AmazonPriceTracker",
        "url": "https://github.com/jakobowsky/AmazonPriceTracker",
        "stars": 126,
        "license": "未读取 LICENSE（仓库根目录未见 LICENSE 文件），接入前须自查",
        "verified_how": "search_repositories 命中 + get_file_contents 亲自打开 / 与 /simple_tracker.py",
        "files_opened": ["/", "/simple_tracker.py"],
        "reused": "借鉴其 GenerateReport 的「date / title / seller / price / url 落 JSON 报告 + 按 price 排序取 best_item」结构，在 scripts/fetch_prices.py 里实现 from_adapter_payload() 适配器契约",
        "not_reused": "**未复制其 Selenium 抓取代码**：依赖已废弃的 find_element_by_xpath、绑定单一电商站点、反爬与合规风险高，且抓的是挂牌价不是到手价",
        "as_of": TODAY,
    },
    {
        "id": "price_tracker_bot", "full_name": "chen-tf/price-tracker-bot",
        "url": "https://github.com/chen-tf/price-tracker-bot",
        "stars": 126,
        "license": "未读取，接入前须自查",
        "verified_how": "search_repositories 命中",
        "files_opened": ["（仅检索命中，未打开单个文件）"],
        "reused": "作为「每日定时采样 + 降价提醒」的成熟形态参考，对照我们的 .github/workflows/update-prices.yml",
        "not_reused": "未集成；它是中文电商 Telegram 机器人，口径与本项目的四元组到手价不同",
        "as_of": TODAY,
    },
]

# 真实读到的 lensfun generic.xml 里的卡口清单与 cropfactor（节选，逐字来自原文）
LENSFUN_MOUNTS = [
    "Canon EF", "Canon EF-M", "Canon EF-S", "Canon FD", "Fujifilm G", "Fujifilm X",
    "Leica L", "Leica M", "Micro 4/3 System", "Nikon CX", "Nikon F", "Nikon Z",
    "Pentax K", "Samsung NX", "Sigma SA", "Sony Alpha", "Sony E", "Tamron Adaptall", "4/3 System",
]
LENSFUN_CROP = [
    {"model": "Crop-factor 1.0 (Full Frame)", "cropfactor": 1.0},
    {"model": "Crop-factor 1.5 (APS-C)", "cropfactor": 1.53},
    {"model": "Crop-factor 1.6 (APS-C)", "cropfactor": 1.611},
    {"model": "Crop-factor 2.0 (Four-Thirds)", "cropfactor": 2.0},
]

# 真实读到的 gyroflow/lens_profiles/Nikon 目录里的文件名（节选）
GYROFLOW_FILES = [
    "Nikon_Z30_16-50 DX__1080p_16by9_1920x1080-59.94fps.json",
    "Nikon_Z30_DX 16-50__4k_16by9_3840x2160-29.97fps.json",
    "Nikon_Z30_Z50-250mm @ 50mm__4k_16by9_3840x2160-29.97fps.json",
    "Nikon_Z30_12-28mm @ 12mm__1080p_16by9_1920x1080-29.97fps.json",
    "Nikon_Z30_24mm 1.7__1080p_16by9_1920x1080-59.94fps.json",
    "Nikon_Z30_Viltrox 33mm__4k_16by9_3840x2160-29.97fps.json",
    "Nikon_Z30_Viltrox 33mm__4k_16by9_3840x2160-29.97fps - AHost7 - 2.json",
    "Nikon_Z30_viltrox 27mm f1.2__4k_16by9_3840x2160-29.97fps.json",
    "Nikon_Z30_TTArtisan AF 272.8__1080p_16by9_1920x1080-119.88fps.json",
    "Nikon_Z30_Sigma 30mm 1_1.4 DC DN__4k_16by9_3840x2160-29.97fps.json",
    "Nikon_Z30_Sigma 56mm_56mm_4k_16by9_3840x2160-29.97fps.json",
    "Nikon_Z30_SIGMA 18-35__4k_16by9_3840x2160-29.97fps.json",
    "Nikon_Z30_SIGMA 18-35__4k_16by9_3840x2160-29.97fps - zjy - 2.json",
    "Nikon_Z50_Laowa 9mm F2.8__4k_16by9_3840x2160-29.97fps.json",
    "Nikon_Z50_Viltrox 13mm f1.4 Z__4k_16by9_3840x2160-25.00fps.json",
    "Nikon_Z6ii_7Artizan 12mm T2.9__4k_16by9_3840x2160-25.00fps.json",
    "Nikon_D-750_Nikon 24-120 F4__1080p_16by9_1920x1080-59.94fps.json",
    "Nikon_D7500_TAMARON 10 24__4k_16by9_3840x2160-29.97fps.json",
]


def build_new_files():
    print("[1/5] 生成价格档位 / 新鲜度策略 / 开源上游文件")

    dump("data/price_tiers.json", {
        "schema_version": "1.0",
        "purpose": "慢变价格档位表。只回答「这套机器大概属于哪个价位段」，用于预算硬过滤；不用于展示到手价。",
        "why_it_exists": "静态网页不能联网，到手价必然过期。把会变的数字从决策链里摘出去：慢变档位管「买不买得起」，快变 spot 只管「显示给你看」。档位半年校准一次，不联网也不会错到离谱。",
        "tier_as_of": TODAY,
        "calibration": "档位为数量级标定，来源为示例归纳 + 用户自述，非报价、未核实；每半年人工校准一次并在 CHANGELOG 留痕。",
        "forbidden": "禁止把 tier 当到手价展示，禁止用于下单。",
        "tiers": {
            "nikon_z30":    {"tier": 3000,  "band": "3千档",  "note": "用户自述 Z30+16-50 套机，未核实"},
            "nikon_d750":   {"tier": 4000,  "band": "4千档",  "note": "二手全画幅老单反档位，示例归纳"},
            "nikon_z5ii":   {"tier": 8000,  "band": "8千档",  "note": "入门全画幅，示例归纳"},
            "sony_a7c2":    {"tier": 8500,  "band": "8.5千档", "note": "示例归纳（双11举证价 8091 属快变 spot）"},
            "canon_r7":     {"tier": 8500,  "band": "8.5千档", "note": "APS-C 高位，示例归纳"},
            "sony_a6700":   {"tier": 9000,  "band": "9千档",  "note": "示例归纳"},
            "canon_r8":     {"tier": 10000, "band": "1万档",  "note": "示例归纳"},
            "lumix_s5ii":   {"tier": 11000, "band": "1.1万档", "note": "示例归纳"},
            "fuji_x100vi":  {"tier": 11500, "band": "1.15万档", "note": "示例归纳"},
            "fuji_xt5":     {"tier": 12000, "band": "1.2万档", "note": "示例归纳"},
            "lumix_gh7":    {"tier": 13000, "band": "1.3万档", "note": "示例归纳"},
            "om1ii":        {"tier": 14000, "band": "1.4万档", "note": "示例归纳"},
        },
    })

    dump("data/freshness_policy.json", {
        "schema_version": "1.0",
        "as_of": TODAY,
        "default_ttl_days": 7,
        "ttl_days_by_type": {
            "final_price": 7, "used_ask": 3, "used_sold": 7, "trade_in_quote": 3,
            "coupon_price": 2, "list_price": 30, "msrp": 180,
        },
        "trusted_confidence": ["verified"],
        "status_def": {
            "fresh": "观测日在 TTL 内且 confidence=verified → 可展示到手价，仍须带观测日与来源",
            "stale": "观测日超 TTL → 禁止给到手价结论；排序与性价比改用慢变档位；界面标红「已过期 N 天」",
            "unverified": "无有效观测日 / 无来源 / confidence 非 verified → 禁止给到手价结论；改用慢变档位；界面标「未核实」",
        },
        "hard_filter_uses": "tier（data/price_tiers.json）",
        "display_uses": "spot（data/prices.json 的 observations / bodies.json 内嵌 price）",
        "on_all_stale": "当所有候选价格都不是 fresh，引擎在输出顶部打印：本结果仅为规则排序，不含任何实时到手价结论，请联网复核。",
        "answer_to": "用户 2026-11-26 提问：静态网页不能实时联网，价格不就是错的吗？怎么规避？",
        "answer": "不假装实时。三层：① 决策链只用慢变档位 tier，会过期的 spot 不参与预算硬过滤与排序；② 每条 spot 自带 observed_at + TTL，运行期算 freshness，过期/未核实强制降级并标红；③ 三条更新通道把 spot 刷新回来：skill 运行时联网查、GitHub Actions 每日抓价、用户报价格 issue。这样「价格错了」不会导致「推荐错了」，只会导致「标出来的数字被显式标为不可信」。",
    })

    dump("data/upstream_sources.json", {
        "schema_version": "1.0",
        "verified_at": TODAY,
        "verified_by": "通过已连接的 GitHub 接口真实调用 search_repositories / get_file_contents",
        "honesty": "stars 与许可证一律照抄检索返回，未获取就写「未获取」；只列亲自打开过或检索命中的仓库，绝不编造。",
        "sources": SOURCES,
    })

    dump("data/upstream/lensfun_mounts.json", {
        "schema_version": "1.0",
        "source": "lensfun/lensfun /data/db/generic.xml（2026-11-26 亲自打开，逐字摘录）",
        "source_url": "https://github.com/lensfun/lensfun/blob/master/data/db/generic.xml",
        "license_note": "上游含 COPYING / COPYING.LESSER，接入前须自查许可条款。此处仅作字段结构对照，不含校正数据体。",
        "notice": "这些是上游真实存在的卡口名与裁切系数，用来校准本项目 sensor/mount 字段；不是本项目自己编的参数。",
        "mounts": LENSFUN_MOUNTS,
        "crop_factors": LENSFUN_CROP,
    })

    dump("data/upstream/gyroflow_matched_lenses.json", {
        "schema_version": "1.0",
        "source": "gyroflow/lens_profiles /Nikon 目录（2026-11-26 亲自打开，文件名节选）",
        "source_url": "https://github.com/gyroflow/lens_profiles/tree/main/Nikon",
        "license_note": "上游含 LICENSE 文件，未读取内容，接入前须自查。",
        "notice": "文件名是真实存在的社区贡献记录，用于佐证「副厂/国产镜头 + 机身」组合并非编造；不代表画质结论，也不含防抖参数。",
        "sample_filenames": GYROFLOW_FILES,
        "observed_brands": ["Nikon", "Viltrox 唯卓仕", "TTArtisan 铭匠", "7Artizan 七工匠",
                            "Laowa 老蛙", "Sigma 适马", "Tamron 腾龙", "Samyang 森养"],
        "why_it_matters": "用户指出上一版漏了副厂与国产镜头。这里给出可点开的真实证据：这些组合在开源社区里被实际提交过 profile。",
    })

    W("data/upstream/README.md", """# data/upstream/ · 开源上游数据派生索引

本目录**不是**把别人的仓库整个搬进来，而是：通过 GitHub 接口亲自打开真实文件 →
抽出本项目用得上的字段/证据 → 落成可审计的派生索引。原始大数据体仍留在上游仓库。

| 文件 | 来自 | 用途 |
|---|---|---|
| `lensfun_mounts.json` | `lensfun/lensfun` 的 `data/db/generic.xml` | 真实卡口清单 + cropfactor，校准本项目 sensor/mount 字段 |
| `gyroflow_matched_lenses.json` | `gyroflow/lens_profiles` 的 `Nikon/` 目录 | 真实存在的 Z30 + 副厂/国产镜头组合文件名，佐证镜头库不是编的 |

完整来源、star、许可证、亲自打开过的文件清单见根目录 `UPSTREAM.md`
与 `data/upstream_sources.json`。

**重新抓取**：调用 GitHub 接口 `get_file_contents` 读上述路径，覆盖本目录 JSON 即可。
**合规**：每个上游仓库的许可证都要在真正把数据体合进来之前单独确认；
本项目目前只引用字段结构与「某组合真实存在」这一事实，不复制受许可约束的数据体。
""")

    W("UPSTREAM.md", """# 开源项目到底加没加进来 —— 这一版给个交代

上一版（`11_第一版评估_可取与不可取.md`）我如实写了：**没有把 GitHub 上的开源项目拼进来**，
只给了一张用官方 API 核过 star/许可证的清单。用户 2026-11-26 直接问「你自己往里面加不行吗，
GitHub 我都跟你连接了」。这一版动手了。

核实方式：**通过本会话已连接的 GitHub 接口**真实调用 `search_repositories` /
`get_file_contents`，逐个打开仓库与文件（日期 %s，账号 andy86yang）。
下面每个仓库都能点开；star、许可证、打开过的文件一律照抄返回，没拿到的就写「未获取」。

| 仓库 | star | 我亲自打开的文件 | 这一版真正复用了什么 | 明确没复用什么 |
|---|---|---|---|---|
| [lensfun/lensfun](https://github.com/lensfun/lensfun) | 未获取 | `/`, `/data/db`, `/data/db/lensfun-database.dtd`, `/data/db/generic.xml` | 真实卡口清单 + cropfactor → `data/upstream/lensfun_mounts.json`；DTD 的 `camera/lens/mount/cropfactor` 字段结构对照我们的数据契约 | 没复制镜头校正 XML 数据体（体积大、许可须自查、用途不同） |
| [gyroflow/lens_profiles](https://github.com/gyroflow/lens_profiles) | 106 | `/`, `/Nikon` | 真实文件名里筛出 Z30 + 唯卓仕/铭匠/七工匠/老蛙/适马/腾龙组合 → `data/upstream/gyroflow_matched_lenses.json` | 没复制防抖 profile JSON（不是选型参数） |
| [darktable-org/darktable](https://github.com/darktable-org/darktable) | 13503 | 仅检索命中 | 作为 P5「RAW 后期 / 降噪 / 超分」的**开源可行工具**写进方法论，替代只提 PS | 没编译、没集成代码 |
| [jakobowsky/AmazonPriceTracker](https://github.com/jakobowsky/AmazonPriceTracker) | 126 | `/`, `/simple_tracker.py` | 借鉴 `GenerateReport` 的 `date/title/seller/price/url` 落 JSON + 按价排序结构 → `scripts/fetch_prices.py` 的 `from_adapter_payload()` | **没复制 Selenium 抓取代码**：API 已废弃、绑定单一站点、反爬与合规风险高、抓的是挂牌价不是到手价 |
| [chen-tf/price-tracker-bot](https://github.com/chen-tf/price-tracker-bot) | 126 | 仅检索命中 | 「每日定时采样 + 降价提醒」的成熟形态，对照 `.github/workflows/update-prices.yml` | 没集成（Telegram 机器人，口径不同） |

另有检索命中但未采用的：`Den4200/amazon-price-tracker`(120)、`LenaBarinova/PriceTracker`(114)、
`seebk/GIMP-Lensfun`(50)、`gyroflow` 之外的镜头库搜索结果里大量是 MongoDB/ORM 的
「lens」命名噪音，已剔除，不凑数。

## 为什么是「引用 + 派生索引」，不是「clone 下来拼代码」

用户要的是可审计、口径统一、别人能复核的选型工具。直接把五个不同许可证、
不同语言、不同数据口径的仓库缝在一起，会同时带来：许可证污染、字段对不上、
抓价口径从「挂牌价」偷换成「到手价」、以及无法逐条复算。所以这一版的选择是：

- **数据契约 / 字段结构 / 真实存在的证据** → 接进来，落 `data/upstream/`，标来源与许可证提醒；
- **抓价代码骨架** → 借鉴成熟结构，但保留自己的四元组与「抓不到就返回空，绝不许造数」；
- **引擎、网页、skill、机器人** → 仍是本项目自写零依赖，保证 `engine/scoring.py` 与
  `app/index.html` 严格同源、每条分数可复算。

这条取舍写在这里，方便你交给第二个模型挑错时一并评估。
""" % TODAY)

    W("PRICE_FRESHNESS.md", """# 价格不能实时联网，那结论不就是错的吗？

这是 2026-11-26 用户指出的漏洞，而且**指得对**：静态网页双击就开、不联网，
`prices.json` 里全是 11-25 的示例价，过一个星期就拿不出手了。上一版只写了
「价格是示例、禁止下单」，但**没有在代码里拦住过期价参与计算** —— 那确实是漏洞。

## 结论先说

**不去假装实时，而是把会变的数字从决策链里摘出去。**
价格错了不该导致推荐错了；最多导致「显示出来的那个数字被显式标成不可信」。

## 三层机制（都已落到代码，不是写在文档里）

| 层 | 做法 | 代码位置 |
|---|---|---|
| ① 决策链只用慢变档位 | 新增 `data/price_tiers.json`：每台机器只标「3千档 / 8千档 / 1.2万档」。**预算硬过滤改用 tier**，不再用可能过期的整套到手价。档位半年校准一次，不联网也不会错到离谱 | `engine/scoring.py` 的 `tier_of()` + M1；网页 `compute()` 同源 |
| ② 展示层强制带保质期 | 每条 spot 带 `observed_at` + `confidence`；运行期按 `data/freshness_policy.json` 的 TTL 算 `fresh / stale / unverified`。非 fresh 时：禁止输出「到手价」结论、界面标红、性价比与持有成本改用 tier 计算 | `price_freshness()`；网页 `priceFreshness()`；结果区 `.meta` 与顶部横幅 |
| ③ 三条通道把 spot 刷新回来 | a) **skill 运行时联网查**（真·联网，查实时到手价 + 五类来源交叉）<br>b) **GitHub Actions 每日抓价**（`.github/workflows/update-prices.yml`，只追加不覆盖，Git 留下整条价格曲线）<br>c) **用户报价格 issue**（`.github/ISSUE_TEMPLATE/price-report.md`） | `scripts/fetch_prices.py`、`skill/SKILL.md` 第 1 步 |

当**所有**候选价格都不是 fresh，引擎在输出最顶部打印：
> 本结果仅为规则排序，不含任何实时到手价结论，请联网复核。

`--json` 输出里带 `price_freshness` 汇总，供 skill / 以后的后端直接消费。
`--no-strict-price` 可以关掉严格模式（不推荐，只用于对照实验）。

## 为什么「接个实时 API」不是完整答案

- 国内「到手价」本来就是**一道算式**：省份、国补资格、以旧换新、PLUS、直播间券、
  大促节奏各不一样，同一个人在不同条件下实付不同，没有单一数字可查；
- 公开可抓的源多是**发售价/挂牌价**，上一轮核查已确认这一点；
- 反爬、登录、cookie、服务条款都会让「自动实时」随时断；
- 就算断了，软件也不该给出错误的推荐 —— 所以**架构上必须假定价格永远可能过期**。

这也解释了为什么这一版把交付形态收敛成「GitHub 开源项目 + Skill」：
真联网由 Skill 在运行时完成，静态网页负责离线可跑、可审计、可导出。
带后端网站与微信小程序按用户要求**先不做**，等这套价格与口碑维护机制跑顺了再说。
""")


# ---------------------------------------------------------------------------
# 2. 打补丁：engine/scoring.py
# ---------------------------------------------------------------------------
def patch_engine():
    print("[2/5] 打补丁 engine/scoring.py（tier 硬过滤 + freshness 降级）")

    new_helpers = r'''

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
'''

    patch("engine/scoring.py", [
        ("import argparse\nimport json\nimport os\nimport sys\n",
         "import argparse\nimport datetime\nimport json\nimport os\nimport sys\n"),

        ('def money(n):\n    return "¥" + format(int(round(n)), ",")\n',
         'def money(n):\n    return "¥" + format(int(round(n)), ",")\n' + new_helpers),

        ('''def compute(q, b, rules, lenses, rep):
    """返回逐条可复算的结果字典。与网页 compute() 一致。"""
    d = {"name": b["name"], "body": b, "parts": [], "cap_items": [], "comp_items": [], "blocked": None}
    limit = weight_limit(q, rules["weight_policy"])
    kit = kit_of(b["price"])
''',
         '''def compute(q, b, rules, lenses, rep):
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
'''),

        ('''    elif kit > q["budget"]:
        d["blocked"] = "整套超出预算（买完机身没钱买头）"
''',
         '''    elif tier is not None and tier > q["budget"]:
        d["blocked"] = "价格档位 %s 超出预算（档位慢变，不依赖会过期的到手价）" % money(tier)
    elif tier is None and kit > q["budget"]:
        d["blocked"] = "整套超出预算（⚠️ 缺档位表，用示例价兜底，不可信）"
'''),

        ('''    # ---- M5 边际性价比 ------------------------------------------------------
    d["value_ratio"] = d["score"] / (kit / 1000.0)
''',
         '''    # ---- M5 边际性价比（v3：用 basis，不用可能过期的 spot）------------------
    d["value_ratio"] = d["score"] / (max(1, basis) / 1000.0)
'''),

        ('''    off = rules["secondary_use_offset"]
    offset = min(off["max_offset"], len(b.get("secondary_uses", [])) * off["per_use_offset"]) * kit
    dep = (max(0, b["first_launch_price"] - final_of(b["price"]))
           if b.get("first_launch_price") else round(kit * 0.22))
    resale = round(kit * 0.15) if "care_resale" in q["finance"] else 0
''',
         '''    off = rules["secondary_use_offset"]
    offset = min(off["max_offset"], len(b.get("secondary_uses", [])) * off["per_use_offset"]) * basis
    dep = (max(0, b["first_launch_price"] - basis)
           if b.get("first_launch_price") else round(basis * 0.22))
    resale = round(basis * 0.15) if "care_resale" in q["finance"] else 0
'''),

        ('''    "print": dict(budget=30000,''',
         '''    # 用户 2026-11-26 现场提问：总预算 10000，功能尽可能多，又拍风光又拍人像
    "allround_10k": dict(budget=10000, sensor="any", scenes="landscape,portrait,travel",
                         priorities="light,af", current_gear="phone_other", existing_kit="none",
                         trek_km=8, hand_size="medium", height=170, tendinitis=False,
                         output="xiaohongshu", expertise="enthusiast", social=0.15,
                         pains="wide,pixels,tele", constraints="money_scarce",
                         finance="transitional_ok", abilities="can_raw,willing_post,buy_fast_lens",
                         lens_groups="原厂,副厂,国产"),
    "print": dict(budget=30000,'''),

        ('''    ap.add_argument("--validate", action="store_true", help="只校验数据文件")
    return ap
''',
         '''    ap.add_argument("--validate", action="store_true", help="只校验数据文件")
    ap.add_argument("--no-strict-price", action="store_true",
                    help="关闭严格价格模式（不推荐，仅供对照实验）")
    ap.add_argument("--price-report", action="store_true", help="只打印价格新鲜度汇总")
    return ap
'''),

        ('''    rules = load("rules.json")
    bodies = load("bodies.json")["bodies"]
    lenses = load("lenses.json")["lenses"]
    rep = load("reputation.json")["reputation"]
    q = make_q(args)
''',
         '''    rules = load("rules.json")
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
'''),

        ('''    print("⚠️ 价格全部是示例 / 举证 / 用户自述未核实，禁止用于下单；所有系数为示例标定、未实证。")
''',
         '''    print("⚠️ 价格全部是示例 / 举证 / 用户自述未核实，禁止用于下单；所有系数为示例标定、未实证。")
    print("价格新鲜度：fresh %d / stale %d / unverified %d ｜ 观测基准日 %s" % (
        summary["fresh"], summary["stale"], summary["unverified"], today))
    if summary["all_stale"]:
        print("🚨 本结果仅为规则排序，不含任何实时到手价结论，请联网复核。")
        print("   预算硬过滤已改用慢变档位 data/price_tiers.json，不用会过期的到手价。")
'''),

        ('''        print("    观测日 %s ｜ 来源 %s ｜ 可信度 %s" % (p["observed_at"], p["origin"], p["confidence"]))
''',
         '''        print("    观测日 %s ｜ 来源 %s ｜ 可信度 %s ｜ 价格状态 %s（%s）" % (
            p["observed_at"], p["origin"], p["confidence"], d["price_status"], d["price_label"]))
        print("    决策用档位 %s ｜ 计算基准 %s ｜ 展示用整套示例价 %s（非实时）" % (
            money(d["price_tier"]) if d["price_tier"] else "缺失",
            d["price_basis"], money(d["kit"])))
'''),

        ('''    if args.json:
        out = {"schema_version": "2.0", "notice": "示例数据，非实时报价，禁止用于下单",
''',
         '''    if args.json:
        out = {"schema_version": "3.0", "notice": "示例数据，非实时报价，禁止用于下单",
               "price_freshness": summary,
'''),

        ('''                            "price_confidence": d["body"]["price"]["confidence"]}
''',
         '''                            "price_confidence": d["body"]["price"]["confidence"],
                            "price_status": d["price_status"], "price_label": d["price_label"],
                            "price_tier": d["price_tier"], "price_basis": d["price_basis"]}
'''),
    ])


# ---------------------------------------------------------------------------
# 3. 打补丁：网页（与引擎严格同源）
# ---------------------------------------------------------------------------
def patch_web():
    print("[3/5] 打补丁 scripts/web_template.html（网页同源）")

    helpers = r'''
/* ---- v3：价格新鲜度与慢变档位（与 engine/scoring.py 严格同源）---- */
function tierOf(b){const t=(DATA.price_tiers||{})[b.id];return t?t.tier:null}
function priceFreshness(p){
  const fp=DATA.freshness_policy||{default_ttl_days:7,trusted_confidence:["verified"],ttl_days_by_type:{}};
  const conf=p.confidence||"unverified";
  const obs=String(p.observed_at||"").slice(0,10);
  const d=new Date(obs+"T00:00:00");
  if(isNaN(d.getTime()))return {status:"unverified",age:null,ttl:null,label:"无有效观测日 → 未核实"};
  const age=Math.floor((new Date()-d)/86400000);
  const ttl=(fp.ttl_days_by_type||{})[p.price_type||"final_price"]||fp.default_ttl_days||7;
  if((fp.trusted_confidence||["verified"]).indexOf(conf)<0)
    return {status:"unverified",age:age,ttl:ttl,label:"来源未核实（confidence="+conf+"）"};
  if(age<0)return {status:"unverified",age:age,ttl:ttl,label:"观测日在未来，拒绝采信"};
  if(age>ttl)return {status:"stale",age:age,ttl:ttl,label:"已过期 "+age+" 天（TTL "+ttl+" 天）"};
  return {status:"fresh",age:age,ttl:ttl,label:"观测于 "+age+" 天前，未过期"};
}
function freshnessSummary(){
  const o={fresh:0,stale:0,unverified:0,asOf:new Date().toISOString().slice(0,10)};
  DATA.bodies.forEach(b=>o[priceFreshness(b.price).status]++);
  o.allStale=o.fresh===0;return o;
}
function initPriceBanner(){
  const el=document.getElementById("priceBanner");if(!el)return;
  const s=freshnessSummary();
  el.innerHTML="价格状态：fresh <b>"+s.fresh+"</b> / stale <b>"+s.stale+"</b> / unverified <b>"+s.unverified+
    "</b> ｜ 观测基准日 "+s.asOf+
    (s.allStale?"<br><b style='color:#b42318'>🚨 本结果仅为规则排序，不含任何实时到手价结论，请联网复核。预算硬过滤已改用慢变档位，不用会过期的到手价。</b>":"");
}
'''

    patch("scripts/web_template.html", [
        ('''<div class="banner">
  ⚠️ 价格全为【示例 / 举证 / 用户自述未核实】，不是实时报价，禁止用于下单。
  <small>本页是纯静态离线成品：所有计算在本机完成，<b>不联网</b>。真·联网调研（查实时到手价、复核口碑）由配套 skill 完成；网站部署与小程序路径见仓库 docs/形态与部署.md。</small>
</div>
''',
         '''<div class="banner">
  ⚠️ 价格全为【示例 / 举证 / 用户自述未核实】，不是实时报价，禁止用于下单。
  <div id="priceBanner" style="margin-top:6px;font-size:12px">价格状态加载中…</div>
  <small>本页是纯静态离线成品：所有计算在本机完成，<b>不联网</b>。价格过期不参与决策（详见 PRICE_FRESHNESS.md）；真·联网调研由配套 skill 完成。网站部署与小程序按用户要求先不做。</small>
</div>
'''),

        ('''        <option value="print">风光 / 打印 / 商业交付</option>''',
         '''        <option value="allround_10k">1 万预算 / 功能多 / 风光+人像（现场提问）</option>
        <option value="print">风光 / 打印 / 商业交付</option>'''),

        ('''const PRESETS={
  hiker:''',
         '''const PRESETS={
  allround_10k:{current_gear:"phone_other",existing_kit:"none",trek_km:"8",hand_size:"medium",height_cm:"170",tendinitis:"no",
    budget:10000,sensor:"any",region:"unknown",output_target:"xiaohongshu",expertise:"enthusiast",social_weight:"0.15",
    pains:["wide","pixels","tele"],constraints:["money_scarce"],finance:["transitional_ok"],
    abilities:["can_raw","willing_post","buy_fast_lens"],scenes:["landscape","portrait","travel"],priorities:["light","af"]},
  hiker:'''),

        ('''function finalOf(p){return Math.max(0,p.list_price-p.coupon-p.subsidy-p.trade_in+p.shipping)}
function kitOf(p){return finalOf(p)+p.lens+p.accessories}
''',
         '''function finalOf(p){return Math.max(0,p.list_price-p.coupon-p.subsidy-p.trade_in+p.shipping)}
function kitOf(p){return finalOf(p)+p.lens+p.accessories}
''' + helpers),

        ('''function compute(q,b){
  const d={name:b.name,b:b,parts:[],blocked:null,capItems:[],compItems:[],reputation:[]};
  const limit=weightLimit(q);
  const kit=kitOf(b.price);
''',
         '''function compute(q,b){
  const d={name:b.name,b:b,parts:[],blocked:null,capItems:[],compItems:[],reputation:[]};
  const limit=weightLimit(q);
  const kit=kitOf(b.price);
  /* v3：慢变档位管决策，快变 spot 只管展示；每条价格运行期算新鲜度 */
  const tier=tierOf(b), fresh=priceFreshness(b.price);
  const basis=(fresh.status!=="fresh"&&tier!=null)?tier:kit;
  d.priceTier=tier;d.priceStatus=fresh.status;d.priceLabel=fresh.label;
  d.priceBasis=basis;d.priceBasisNote=(fresh.status!=="fresh"&&tier!=null)?"tier（价格 "+fresh.status+"，已改用慢变档位）":"spot（价格 fresh）";
'''),

        ('''  else if(kit>q.budget) d.blocked="整套超出预算（买完机身没钱买头）";''',
         '''  else if(tier!=null && tier>q.budget) d.blocked="价格档位 "+fmt(tier)+" 超出预算（档位慢变，不依赖会过期的到手价）";
  else if(tier==null && kit>q.budget) d.blocked="整套超出预算（⚠️ 缺档位表，用示例价兜底，不可信）";'''),

        ('''  d.valueRatio=score/(kit/1000);''',
         '''  d.valueRatio=score/(Math.max(1,basis)/1000);'''),

        ('''  const offset=Math.min(off.max_offset,(b.secondary_uses||[]).length*off.per_use_offset)*kit;
  const dep=b.first_launch_price?Math.max(0,b.first_launch_price-finalOf(b.price)):Math.round(kit*0.22);
  const resale=q.finance.includes("care_resale")?Math.round(kit*0.15):0;
''',
         '''  const offset=Math.min(off.max_offset,(b.secondary_uses||[]).length*off.per_use_offset)*basis;
  const dep=b.first_launch_price?Math.max(0,b.first_launch_price-basis):Math.round(basis*0.22);
  const resale=q.finance.includes("care_resale")?Math.round(basis*0.15):0;
'''),

        ('''      h+='<div class="meta">观测日 '+p.observed_at+' ｜ 来源 '+p.origin+' ｜ 可信度 <b>'+p.confidence+
         '</b> ｜ <b>⚠️ 示例 / 非实时报价，禁止用于下单</b></div></div>';
''',
         '''      const ps=d.priceStatus,pl=d.priceLabel;
      const badge=ps==="fresh"?'<span class="badge A">fresh</span>':
                  ps==="stale"?'<span class="badge D">stale</span>':'<span class="badge C">unverified</span>';
      h+='<div class="meta">观测日 '+p.observed_at+' ｜ 来源 '+p.origin+' ｜ 可信度 <b>'+p.confidence+
         '</b> ｜ 价格状态 '+badge+' '+pl+
         ' ｜ 决策用档位 '+(d.priceTier?fmt(d.priceTier):'缺失')+' ｜ 计算基准 '+d.priceBasisNote+
         '<br><b>⚠️ 示例 / 非实时报价，禁止用于下单；本行数字只作展示，不参与排序</b></div></div>';
'''),

        ('''     '<li><b>不是</b>：实时报价系统。纯静态网页<b>不联网</b>，本页价格全是示例 / 举证 / 用户自述未核实。</li>'+
''',
         '''     '<li><b>不是</b>：实时报价系统。纯静态网页<b>不联网</b>，本页价格全是示例 / 举证 / 用户自述未核实。</li>'+
     '<li><b>价格过期怎么规避</b>：预算硬过滤改用 <code>data/price_tiers.json</code> 的<b>慢变档位</b>（半年校准一次），'+
     '会过期的到手价只作展示、不参与排序；每条价格按 <code>freshness_policy.json</code> 的 TTL 运行期判 '+
     '<b>fresh / stale / unverified</b>，非 fresh 一律标红且性价比/持有成本改用档位算。'+
     '刷新通道三条：skill 联网查、GitHub Actions 每日抓价、用户报价格 issue。详见 <code>PRICE_FRESHNESS.md</code>。</li>'+
'''),

        ('''  L.push("生成日期：2026-11-25 ｜ 数据性质：示例 / 举证 / 用户自述未核实，非实时报价");
''',
         '''  L.push("生成日期：2026-11-26（v3）｜ 数据性质：示例 / 举证 / 用户自述未核实，非实时报价");
  const fs=freshnessSummary();
  L.push("价格新鲜度：fresh "+fs.fresh+" / stale "+fs.stale+" / unverified "+fs.unverified+
         " ｜ 观测基准日 "+fs.asOf+(fs.allStale?" ｜ 全部非 fresh：本结果仅为规则排序，不含任何实时到手价结论":""));
  L.push("预算硬过滤使用 data/price_tiers.json 的慢变档位，不使用会过期的到手价；非 fresh 价格不参与性价比与持有成本。");
'''),

        ('''    L.push("  观测日 "+d.b.price.observed_at+" ｜ 来源 "+d.b.price.origin+" ｜ 可信度 "+d.b.price.confidence);
''',
         '''    L.push("  观测日 "+d.b.price.observed_at+" ｜ 来源 "+d.b.price.origin+" ｜ 可信度 "+d.b.price.confidence+
           " ｜ 价格状态 "+d.priceStatus+"（"+d.priceLabel+"）｜ 决策档位 "+d.priceTier+" ｜ 计算基准 "+d.priceBasisNote);
'''),

        ('''function copyExport(){
  const t=document.getElementById("exportText");t.select();document.execCommand("copy");
  document.getElementById("copyHint").textContent="已复制，去粘给另一个 AI 吧。";
}
</script>
''',
         '''function copyExport(){
  const t=document.getElementById("exportText");t.select();document.execCommand("copy");
  document.getElementById("copyHint").textContent="已复制，去粘给另一个 AI 吧。";
}
window.addEventListener("DOMContentLoaded",initPriceBanner);
</script>
'''),
    ])


# ---------------------------------------------------------------------------
# 4. 打补丁：rebuild_data.py / fetch_prices.py / README.md
# ---------------------------------------------------------------------------
def patch_rest():
    print("[4/5] 打补丁 rebuild_data.py / fetch_prices.py / README.md")

    patch("scripts/rebuild_data.py", [
        ('''            "price_history": PRICE_HISTORY["series"],
        }
''',
         '''            "price_history": PRICE_HISTORY["series"],
            "price_tiers": load(os.path.join(DATA, "price_tiers.json")).get("tiers", {}),
            "freshness_policy": load(os.path.join(DATA, "freshness_policy.json")),
            "upstream_sources": load(os.path.join(DATA, "upstream_sources.json")).get("sources", []),
        }
'''),
        ('''    targets = [os.path.join(SESSION, "06_MVP", "data"),
               os.path.join(SESSION, "07_camera-advisor-skill", "references")]
    for t in targets:
        os.makedirs(t, exist_ok=True)
        for name in ["bodies.json", "rules.json", "lenses.json", "reputation.json", "price_history.json"]:
            shutil.copyfile(os.path.join(DATA, name), os.path.join(t, name))
''',
         '''    # 可移植性：clone 到别人机器上时，会话目录里的 06_MVP / 07_camera-advisor-skill
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
'''),
    ])

    adapter = r'''
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

'''

    patch("scripts/fetch_prices.py", [
        ("class PriceSource:\n", adapter + "\nclass PriceSource:\n"),
        ('''    print("接入步骤：")
''',
         '''    print("v3 已接入的开源适配器契约（真实核实过，见 UPSTREAM.md）：")
    for a in UPSTREAM_ADAPTERS:
        print("  · %-34s 复用：%s ｜ 未复用：%s" % (a["repo"], a["reused"], a["not_reused"]))
    print("  · from_adapter_payload() 把上游记录映射成四元组 quote，缺字段直接返回 None，不许造数。")
    print()
    print("接入步骤：")
'''),
    ])

    append("README.md", """

---

## 价格不能实时联网，那结论不就错了吗？（2026-11-26 补）

这是用户指出的真漏洞，上一版只在文档里写了「价格是示例」，**没在代码里拦住过期价参与计算**。
这一版补上了，详见根目录 `PRICE_FRESHNESS.md`。三层：

1. **决策链只用慢变档位**：新增 `data/price_tiers.json`，预算硬过滤改用「3千档 / 8千档 / 1.2万档」
   这类半年校准一次的量级，不再用会过期的整套到手价。
2. **展示层强制带保质期**：`data/freshness_policy.json` 定义 TTL；引擎运行期判
   `fresh / stale / unverified`，非 fresh 一律标红、禁止给到手价结论、性价比与持有成本改用档位算。
   全部非 fresh 时输出顶部打印「本结果仅为规则排序，不含任何实时到手价结论」。
3. **三条刷新通道**：skill 运行时联网查 / `.github/workflows/update-prices.yml` 每日抓价 /
   `.github/ISSUE_TEMPLATE/price-report.md` 用户报价格。

结论：**价格错了不该导致推荐错了**。就算所有价签都过期，排序依然可用，只是数字被显式标成不可信。

## 这一版到底加了哪些开源项目

不再只给清单。见根目录 `UPSTREAM.md` 与 `data/upstream_sources.json`：
通过已连接的 GitHub 接口亲自打开过 `lensfun/lensfun`、`gyroflow/lens_profiles`、
`jakobowsky/AmazonPriceTracker` 等真实仓库与文件，把**真实卡口清单 + cropfactor**、
**真实存在的 Z30 + 唯卓仕/七工匠/老蛙/铭匠/适马/腾龙组合**、以及**抓价报告契约**
落进 `data/upstream/` 与 `scripts/fetch_prices.py`。每个都标了 URL、star、许可证提醒、
亲自打开过的文件、以及**明确没复用什么**。

## 形态收敛（按用户要求，一步一步来）

**当前交付 = 一个能推到 GitHub 的开源项目 + 一个能装的 Skill。**
带后端网站与微信小程序**先不做** —— 瓶颈是合法可持续的到手价数据源，不是界面。
等这套「档位决策 + TTL 降级 + 每日采样 + 口碑复核」跑顺了，再上后端和小程序会扎实得多。

- `app/index.html`：双击即跑的离线成品（不联网，价格状态如实标注）
- `engine/scoring.py`：零依赖可解释引擎，命令行 / 可导入 / `--json`
- `skill/`：自包含 Skill，clone 下来把整个目录复制到
  `C:\\Users\\<你>\\.workbuddy\\skills\\` 即可安装；运行时联网查实时到手价与口碑
- `.github/workflows/`：每日抓价、每周口碑复核；`ISSUE_TEMPLATE/` 报价格、争议规则

## 现场问题：1 万预算、功能尽量多、又拍风光又拍人像

```bash
python engine/scoring.py --preset allround_10k --top 3
```

网页里选「1 万预算 / 功能多 / 风光+人像（现场提问）」一键载入即可。
输出会同时给机身、镜头搭配（原厂/副厂/国产）、预算分配、以及**价格状态提示**。
""")


# ---------------------------------------------------------------------------
# 5. skill/ 自包含目录
# ---------------------------------------------------------------------------
def build_skill():
    print("[5/5] 生成 skill/ 自包含目录")
    src = os.path.join(SESSION, "07_camera-advisor-skill")
    dst = os.path.join(ROOT, "skill")
    os.makedirs(os.path.join(dst, "references"), exist_ok=True)
    os.makedirs(os.path.join(dst, "scripts"), exist_ok=True)

    sk = os.path.join(src, "SKILL.md")
    if os.path.exists(sk):
        with open(sk, encoding="utf-8") as f:
            t = f.read()
        t = t.replace("把整个 `07_camera-advisor-skill/` 复制到",
                      "把仓库里的整个 `skill/` 目录复制到")
        t = t.replace("仓库版见 `12_camera-advisor-repo/`（含 GitHub Actions 每日抓价机器人与 issue 模板）。",
                      "本目录就在这个开源仓库里，含每日抓价机器人与 issue 模板。")
        t = t.replace("version: 2.0.0", "version: 3.0.0")
        t += r'''

---

## v3 新增（2026-11-26）：价格过期不再污染结论

静态网页不能联网，价格必然过期。运行本 skill 时请按下面顺序做：

1. **先跑 `--price-report`** 看 `references/price_tiers.json` 与 `freshness_policy.json` 的状态汇总；
2. **第 1 步联网调研**里查到的实时到手价，写回 `references/prices.json` 对应的 observation，
   必须带 `region / observed_at / price_type / condition / source_url` 且 `confidence=verified`；
   抓不到就**不改**，保持 `unverified`，并在回答里明说「价格未核实」；
3. **绝不允许**用查到的挂牌价/券后价直接替换「到手价」字段；
4. 引擎默认严格模式：非 fresh 的价格不参与预算硬过滤、性价比与持有成本，
   改用 `price_tiers.json` 的慢变档位；`--json` 输出带 `price_freshness` 汇总；
5. 口碑复核时，顺手看 `references/upstream_sources.json`：里面列了本项目接进来的真实开源仓库，
   需要镜头组合或卡口字段时可回溯到上游核对。

完整机制见仓库根 `PRICE_FRESHNESS.md` 与 `UPSTREAM.md`。
'''
        W("skill/SKILL.md", t)
    else:
        W("skill/SKILL.md", "# camera-advisor skill\n\n缺少源 SKILL.md，请从 07_camera-advisor-skill/ 复制。")

    W("skill/README.md", """# skill/ · 可直接安装的 WorkBuddy Skill

这个目录是**自包含**的：`SKILL.md` + `references/*.json` + `scripts/scoring.py`。

## 安装

```
git clone <本仓库>
把仓库里的 skill/ 整个目录复制到 C:\\Users\\<你的用户名>\\.workbuddy\\skills\\camera-advisor\\
```

复制完在 WorkBuddy 里就能用。也可以本机直接跑：

```bash
python skill/scripts/scoring.py --preset allround_10k
python skill/scripts/scoring.py --price-report
python skill/scripts/scoring.py --validate
```

## 与仓库的关系

- `skill/scripts/scoring.py` 与 `engine/scoring.py` 是同一份代码（由 `scripts/upgrade_v3.py --sync` 同步）
- `skill/references/*.json` 与 `data/*.json` 是同一份数据
- 网页 `app/index.html` 与它们**严格同源**：同一套权重、同一套价格新鲜度判定

## 这一版收敛的形态

按用户要求「一步一步来」：先做成熟一个能开源、能装、能联网调研的 Skill，
带后端网站与微信小程序**暂不做**。真联网发生在 skill 运行时（第 1 步），
静态网页负责离线可跑、可审计、可导出。
""")


def sync():
    """在 rebuild_data.py 之后跑：同步三处数据 + 引擎副本。"""
    print("[sync] 同步 data/*.json 与 engine/scoring.py 到三处")
    names = ["bodies.json", "rules.json", "lenses.json", "reputation.json",
             "price_history.json", "prices.json", "price_tiers.json",
             "freshness_policy.json", "upstream_sources.json"]
    targets = [os.path.join(ROOT, "skill", "references")]
    for sub in ("06_MVP/data", "07_camera-advisor-skill/references"):
        p = os.path.join(SESSION, sub)
        if os.path.isdir(os.path.dirname(p)):
            targets.append(p)
    for t in targets:
        os.makedirs(t, exist_ok=True)
        for n in names:
            src = os.path.join(DATA, n)
            if os.path.exists(src):
                shutil.copyfile(src, os.path.join(t, n))
        print("  ✓ " + t)
    eng = os.path.join(ROOT, "engine", "scoring.py")
    for p in [os.path.join(ROOT, "skill", "scripts", "scoring.py"),
              os.path.join(SESSION, "07_camera-advisor-skill", "scripts", "scoring.py")]:
        if os.path.isdir(os.path.dirname(p)):
            shutil.copyfile(eng, p)
            print("  ✓ " + p)


def main():
    if "--sync" in sys.argv:
        sync()
        return
    print("=" * 70)
    print("camera-advisor v3 升级（可重复运行；已打过补丁会报锚点找不到，属正常保护）")
    print("=" * 70)
    build_new_files()
    patch_engine()
    patch_web()
    patch_rest()
    build_skill()
    print()
    print("完成。接下来按顺序跑：")
    print("  python scripts/rebuild_data.py")
    print("  python scripts/upgrade_v3.py --sync")
    print("  python engine/scoring.py --validate")


if __name__ == "__main__":
    main()
