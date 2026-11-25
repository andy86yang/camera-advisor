# skill/ · 可直接安装的 WorkBuddy Skill

这个目录是**自包含**的：`SKILL.md` + `references/*.json` + `scripts/scoring.py`。

## 安装

```
git clone <本仓库>
把仓库里的 skill/ 整个目录复制到 C:\Users\<你的用户名>\.workbuddy\skills\camera-advisor\
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
