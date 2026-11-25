# data/upstream/ · 开源上游数据派生索引

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
