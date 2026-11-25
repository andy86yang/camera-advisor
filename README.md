# 相机选购顾问 · camera-advisor

> 输入**你真实的处境**（现有装备、痛点、预算、负重、身体、片子发到哪、会不会后期、在不在意别人怎么看）
> → 输出**个人用户画像 + 可解释的 Top 3 方案**，每条写清「有效分怎么来的 / 短板怎么补 / 哪些钱是白花的 / 以后换机亏多少 / 出处与观测日」。

不收广告、不照抄博主口诀、不编价格。**所有结论可导出，交给第二个 AI 交叉论证。**

---

## 它跟「预算 X 买什么相机」的普通推荐有什么不一样

普通推荐算的是「哪台机器裸参数好」。这个项目算的是「**这个人在他的约束下，哪套方案最值、最愿意用、最不后悔**」。

设计来源是作者的一段真实经历：拿一英寸手机爬山 → 广角/像素不够 → 后期锐化+超分又麻烦又上限低 → 手机还要导航、上传轨迹、付费，电量是稀缺资源 → 预算一万买全幅机身就没钱买头 → 选了出了很多年的过渡机 → 却发现老机身还在降价、而且降幅不在双 11 → 于是用 RAW、锁 ISO 100、F1.7/F1.2 大光圈、慢快门、补灯、后期降噪超分把半画幅的短板补回来，换来「轻、愿意带出去、不得筋膜炎、还能退居二线当直播副机位」。

由此抽出 11 条第一性原理，见 [`docs/方法论.md`](docs/方法论.md)。核心几条：

| 原理 | 在代码里是什么 |
|---|---|
| 短板可被零/低成本手段补偿（田忌赛马） | `M2b` 补偿表：`RAW / 低ISO / 大光圈 / 后期` 让裸分变成**有效分** |
| 收益由**输出端**决定，不由拍摄端决定 | `M3` 输出端 cap：发朋友圈时 4000 万像素、4K60、10-bit 超出部分**折损**，「成本+80% 效果+8%」直接算给你看 |
| **愿意带出去** > 纸面画质 | `M4` 重量→出勤率，作**乘性因子**；徒步 20km 超重一票否决 |
| 退居二线 = 消除沉没成本 | `M6` 持有成本 = 折旧 + 二手折价 − **第二用途抵扣** |
| 口碑会过时，知识库要能自我革命 | `data/reputation.json` 带 `as_of / status / review_due`，`outdated`/`disputed` 权重恒 0，`improved` 只给低权重 |
| 价格是**时间序列**，不是大促快照 | `.github/workflows/update-prices.yml` **每日**采样、全历史留痕（因为真实降幅发生在 7/8 月，双 11 反而不动） |
| 官方不可全信、社交是真实需求 | 来源分**官方/媒体/消费者/圈外/实测**五类并标 bias；社交认同是**用户可调**显式维度 |
| 主次矛盾、不做全才 | 输出分「主要矛盾 / 次要矛盾 / 不必纠结」 |

---

## 快速开始（三种形态，都能用）

### 形态 A · 网页成品（最快，零依赖）
```bash
git clone <你的仓库地址>
cd camera-advisor
# 直接双击 app/index.html —— 离线、不用登录、不用 API Key、不用联网
```
或者推到 GitHub 后开 **GitHub Pages**，指向 `app/` 即可给别人用。

### 形态 B · 命令行引擎
```bash
python engine/scoring.py --preset hiker          # 作者口述原例 → 会推出 Z30+16-50
python engine/scoring.py --preset student        # 学生党 → 二手尼康老单反
python engine/scoring.py --validate              # 数据自检
python engine/scoring.py --preset hiker --json   # 机器可读，供后端/其他程序调用
```
零外部依赖，纯标准库，Python 3.8+。

### 形态 C · 可安装 Skill（**真·联网 + 深度思考**）
把 `07_camera-advisor-skill/`（本仓库外的会话目录里，或复制一份进来）放进
`C:\Users\<你>\.workbuddy\skills\`，对 AI 说「按我的情况帮我选相机」即可。
skill 会**实际联网**：查实时到手价、按五类来源交叉、复核口碑有没有过时、查镜头 MTF 实测，再调同一套引擎。
> 静态网页**不联网**（本仓库如实标注）。联网调研由 skill 形态完成，这是分工，不是缺口。

网站部署 / 小程序 / PWA 的成熟路径与合规边界见 [`docs/形态与部署.md`](docs/形态与部署.md)。

---

## 改数据 / 重新生成

**不要手改 `data/*.json` 和 `app/index.html`**——它们是生成产物。改 [`scripts/rebuild_data.py`](scripts/rebuild_data.py) 里的常量后重跑：

```bash
python scripts/rebuild_data.py     # 重建 5 个 JSON + 把数据注入网页模板，生成两份 index.html
python engine/scoring.py --validate
python scripts/fetch_prices.py --dry-run   # 抓价骨架（当前未接真实源，见下）
```

数据分三处同步（`data/` ↔ `06_MVP/data/` ↔ `07_camera-advisor-skill/references/`），脚本保证一致。

---

## 目录

```
camera-advisor/
├── app/index.html                  # 单文件成品，双击即开（由模板注入生成）
├── engine/scoring.py               # v2 可解释引擎（零依赖，CLI + 可导入）
├── scripts/
│   ├── web_template.html           # 网页模板，含 /*__DATA_V2__*/ 占位
│   ├── rebuild_data.py             # 数据重建 + 网页注入（改数据请改这里）
│   └── fetch_prices.py             # 抓价适配器骨架 + 四元组校验
├── data/
│   ├── bodies.json                 # 12 台机身（含重量/人体工学/第二用途/首发价/角色）
│   ├── lenses.json                 # 18 颗：原厂 / 腾龙·适马 / 维卓仕·老蛙·七工匠
│   ├── rules.json                  # 场景权重 + 补偿表 + 输出端 cap + 负重策略 + 五类来源
│   ├── reputation.json             # 口碑带 as_of / status / bias / review_due
│   ├── prices.json                 # 价格契约（四元组、七种价格类型）
│   └── price_history.json          # 时间序列（含用户自述价格点，标未核实）
├── docs/                           # 方法论 / 价格契约 / 规则证据 / 形态与部署 / 交叉论证
├── .github/workflows/              # 每日抓价 + 每周口碑复核（自我革命）
├── .github/ISSUE_TEMPLATE/         # 报价格 / 质疑规则
├── CONTRIBUTING.md · CHANGELOG.md · LICENSE
```

---

## 防幻觉声明（请务必读）

- ⚠️ **本仓库所有价格都是示例 / 举证 / 用户自述未核实，禁止用于下单。** 每条都带 `observed_at`、`origin`、`confidence`。
- ⚠️ **镜头 `mtf_grade` 是示例分级、非实测**；`weight_g`、`social_perception` 是示例归纳。真实选型须查实测 MTF 图。
- ⚠️ **引擎里所有系数（补偿 gain、输出端 cap、携带意愿指数、第二用途抵扣）都是示例标定、未经实证**，界面与导出包均如实标注；欢迎通过 issue 提标定依据。
- ⚠️ `scripts/fetch_prices.py` **当前未接任何真实数据源**，只有适配器接口与校验逻辑。按 `docs/价格数据契约.md` 接入你自己的合法数据源后才会产生真实价格；**任何情况下都不许让模型编一个价格**。
- ⚠️ v1 已核实的 42 条来源与「亲自打开复核」标记见 `09_来源与核实记录.md`；**优先复查只有子代理检索、未亲自打开的那部分**。
- ⚠️ 口述里涉及具体个人的褒贬、私事一律**不入库**，只保留可泛化机制（见方法论第 4 节）。

---

## 交叉论证

网页点「一键导出」会生成一份自包含记录（全部输入 + 每步计算 + 结果 + 出处 + 未核实留白），粘给至少两个不同家的模型互挑。
仓库内另附 [`docs/交叉论证档案.md`](docs/交叉论证档案.md) 与可直接复制的大白话吩咐。

---

## 许可证

MIT，见 [LICENSE](LICENSE)。作者不商用，纯粹想做一个自己用、也能帮到别人的东西。

复核日期：2026-11-25 ｜ 版本 v2 ｜ **下一版必须重走一遍方法论第 0 节（自我革命）**。



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
  `C:\Users\<你>\.workbuddy\skills\` 即可安装；运行时联网查实时到手价与口碑
- `.github/workflows/`：每日抓价、每周口碑复核；`ISSUE_TEMPLATE/` 报价格、争议规则

## 现场问题：1 万预算、功能尽量多、又拍风光又拍人像

```bash
python engine/scoring.py --preset allround_10k --top 3
```

网页里选「1 万预算 / 功能多 / 风光+人像（现场提问）」一键载入即可。
输出会同时给机身、镜头搭配（原厂/副厂/国产）、预算分配、以及**价格状态提示**。
