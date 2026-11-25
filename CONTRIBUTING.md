# 怎么维护这个仓库（也就是「自我革命」的操作手册）

> 「不存在毕其功于一役……就跟党一样要不断的自我革命，就跟人一样活到老学到老。」
> 所以这个仓库的核心不是那套权重，是**让人能质疑、能改、机器能定时提醒复核**的机制。

---

## 1. 三条铁规矩

1. **别手改生成产物。** `data/*.json`、`app/index.html`、`06_MVP/index.html` 都是
   `scripts/rebuild_data.py` 生成的。改它的常量后重跑，三处自动一致。
2. **任何结论都要能追溯到「谁说的 + 哪天 + 有没有利益」。** 匿名进库的结论一律拒绝。
3. **查不到就写「未核实」，不许用常识补空。** 尤其是价格。

---

## 2. 改规则 / 改数据

| 想改什么 | 改哪里 | 重跑什么 |
|---|---|---|
| 机身规格、重量、第二用途、首发价 | `scripts/rebuild_data.py` → `EXT` / `Z30` | `python scripts/rebuild_data.py` |
| 加镜头（原厂 / 副厂 / 国产）、MTF 示例档 | `LENSES` | 同上 |
| 场景权重、补偿手段 gain、输出端 cap、负重策略 | `V2_ADD` | 同上 |
| 品牌口碑状态、来源分类、复核到期日 | `REPUTATION` / `SOURCE_TYPES` | 同上 |
| 价格序列采样策略 | `PRICE_HISTORY` | 同上 |
| 引擎算法（M1–M8） | `engine/scoring.py` **与** `scripts/web_template.html` 里的 `compute()` | 两边都要改，`--validate` + 语法检查 |
| 界面 | `scripts/web_template.html` | `rebuild_data.py` 重新注入 |

改完必跑：
```bash
python scripts/rebuild_data.py
python engine/scoring.py --validate
python engine/scoring.py --preset hiker      # 口述原例不能退化成「0 台通过」
python engine/scoring.py --preset student
```

⚠️ `engine/scoring.py` 与网页 JS 是**两套实现、同一套规则**，改算法时务必同步，否则网页和命令行会给出不同结论。

---

## 3. 口碑状态机（P9 反经验主义）

`data/reputation.json` 每条必须带 `as_of / status / source_type / bias / review_due / weight`。

| status | 含义 | 权重 |
|---|---|---|
| `current` | 现行，有来源支撑 | 按 `weight` |
| `improved` | **历史问题已改善**，只能低权重，禁止照抄旧结论 | ≤ 0.05 |
| `outdated` | 已被现实推翻 | **必须 0** |
| `disputed` | 查不到足够证据 / 来源互相打架 | **必须 0** |

**「曾经犯过错误」不等于「现在还在错」**：要质疑、要打疑问，但不能全盘否定。
典型误用：把某品牌早年的质量事件写进 `current` 去压分 → 会被 `--validate` 拦下并触发复核提醒。

`--validate` 会检查：`outdated`/`disputed` 权重必须为 0、`status` 合法、字段齐全、机身 v2 字段齐全、属性名都在 `attr_labels` 里。

---

## 4. 两种 issue（自我革命的入口）

- **报价格** → `.github/ISSUE_TEMPLATE/price-report.md`
  必须给：地域、观测日、价格类型（MSRP / 券后 / 到手 / 二手要价 / 成交）、成色、来源链接、截图。
  「券后价」不会被当成「到手价」。
- **质疑规则** → `.github/ISSUE_TEMPLATE/rule-dispute.md`
  说清哪条规则、你认为它什么时候失效、给了几个独立来源。**不需要你认识圈内大佬**——可信度由维护者 / AI 代判。

---

## 5. 定时任务

| workflow | 频率 | 干什么 |
|---|---|---|
| `update-prices.yml` | **每日**（也可手动触发） | 跑 `fetch_prices.py` 采样，有变化就自动 commit，Git 天然留下价格曲线 |
| `review-reputation.yml` | 每周一 | 扫描 `review_due` 到期的口碑条目，输出复核清单并自动开 issue |

**为什么是每日、不是只在 618/双 11 跑**：作者口述 50-250 镜头的最大降幅发生在 7/8 月，双 11 双 12 反而几乎没有变化。只盯大促会系统性漏掉真实低点。

---

## 6. 抓价适配器

`scripts/fetch_prices.py` 目前**未接任何真实数据源**，只有：
- `PriceSource` 适配器接口
- 四元组校验（地域 / 观测日 / 价格类型 / 成色，缺一即 `unverified`）
- 写回 `price_history.json` 与 `prices.json` 的逻辑
- `--dry-run`

接入真实源前请读 `docs/价格数据契约.md`，并自行确认：
目标站点的 robots / 服务条款、是否需要登录或 cookie、反爬与合规风险、更新频率、是否覆盖二手与港版。
**任何分支都不许让模型生成一个价格。抓不到就显示「价格未核实 / 已过期，请自行核对」。**

---

## 7. 系数标定（诚实留白）

`compensations.gain`、`output_caps`、`weight_policy.carry_exponent`、`secondary_use_offset`、
`social_perception` 都是**示例标定、未经实证**。它们决定排序，但目前没有实验数据支撑。

欢迎用 issue 提：你的实测对比（同一场景半幅 vs 全幅、RAW 补偿前后、发朋友圈 vs 打印的观感差）、
或者更合理的量纲。改系数时请同时更新 `docs/方法论.md` 第 5 节的口径声明，别悄悄改。

---

## 8. 不写进库的东西

口述里用于举例的**具体个人、婚恋私事、对具体 UP 主的水平褒贬**一律不采集、不核实、不写入任何数据文件、不在界面展示。
可泛化的部分已抽成「名气 ≠ 专业度」「口碑带时间戳」「语境适配 / 效率」三条机制，机制足够，不需要点名。
