# 开源项目到底加没加进来 —— 这一版给个交代

上一版（`11_第一版评估_可取与不可取.md`）我如实写了：**没有把 GitHub 上的开源项目拼进来**，
只给了一张用官方 API 核过 star/许可证的清单。用户 2026-11-26 直接问「你自己往里面加不行吗，
GitHub 我都跟你连接了」。这一版动手了。

核实方式：**通过本会话已连接的 GitHub 接口**真实调用 `search_repositories` /
`get_file_contents`，逐个打开仓库与文件（日期 2026-11-26，账号 andy86yang）。
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
