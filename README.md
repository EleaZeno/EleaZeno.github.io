# 知识日拾

每天由 AI 生成一篇技术知识笔记，Astro 静态站点，GitHub Actions 定时跑，GitHub Pages 托管。

## 它是怎么跑的

```
daily.yml (cron 22:10 UTC = 06:10 CST)
  └─ scripts/generate_post.py
       ├─ 按日期从 topics.yml 轮换选题（跳过最近 14 篇用过的）
       ├─ 调用 OpenAI 兼容接口，要求返回 JSON
       └─ 写入 src/content/posts/YYYY-MM-DD-slug.md 并提交
            └─ push 触发 deploy.yml → 构建 → Pages
```

生成和部署是两条独立的 workflow。生成挂了站点照常在线，只是当天没有新文章。

## 首次配置

1. 仓库设为 **public**（GitHub Free 的 Pages 只支持公开仓库），Settings → Pages → Source 选 **GitHub Actions**。
2. Settings → Secrets and variables → Actions：
   - Secret `LLM_API_KEY` — 模型 API key（必填）
   - Variable `LLM_BASE_URL` — 默认 `https://api.deepseek.com`
   - Variable `LLM_MODEL` — 默认 `deepseek-chat`
3. 改 `src/site.config.ts` 里的站点标题、作者。
4. Actions → Daily post → Run workflow 手动跑一次，确认能出文章。

任何 OpenAI 兼容的 `/v1/chat/completions` 端点都可以，换供应商只改这两个变量。

## 本地开发

```bash
npm install
npm run dev                  # http://localhost:4321
npm run build                # 产物在 dist/
npx astro check              # 类型检查

python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
LLM_API_KEY=sk-xxx DRY_RUN=1 .venv/bin/python scripts/generate_post.py   # 只打印不写文件
```

生成脚本的环境变量：

| 变量 | 说明 |
| --- | --- |
| `LLM_API_KEY` | 必填 |
| `LLM_BASE_URL` | 默认 `https://api.deepseek.com` |
| `LLM_MODEL` | 默认 `deepseek-chat` |
| `POST_DATE` | `YYYY-MM-DD`，默认今天（Asia/Shanghai） |
| `TOPIC` | 覆盖轮换选题，写单篇用 |
| `DRY_RUN=1` | 打印到 stdout，不落盘 |

退出码：`0` 已写入 / `1` 失败 / `2` 当天已有文章（workflow 视为正常）。

## 写作方向

改 `topics.yml`：`topics` 是轮换池，`extra_instructions` 会拼进每次的 prompt，用来统一调性和深度。选题按日期确定性轮换，同一天重跑结果一致。

## 已知边界

- **公开仓库的定时任务在仓库 60 天无活动后会被自动停用。** 每天提交文章本身就算活动，但生成链路坏掉超过 60 天就需要去 Actions 页面手动恢复。
- GitHub 的 cron 是 best-effort，高峰期可能延迟十几分钟或跳过某次。
- Pages 软限制：站点 ≤1GB、流量 100GB/月。纯文本博客大概几十年都用不完。
- AI 生成内容可能有错。页脚已标注，重要结论自己核实。
