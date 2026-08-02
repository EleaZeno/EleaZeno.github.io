# Elea Notes — 代理工作约定

这个文件每轮自动进上下文，不依赖 agent 记得去加载 skill。写在这里的东西是硬约定。

## 一、收尾纪律：阻塞点不是终点

最常见的失败模式不是做错，是**做到一半就停下汇报**。典型形态：

> 「已修好 A、B。剩下 C 是别人的文件 / 缺依赖 / 需要确认，所以停在这里。」

这是错的。日志里这种回合的结束原因是 `finish_reason=stop`——不是崩溃、不是超时、不是打满预算，是模型自己判断「可以交付了」。剩余额度往往还有大半（见 `~/.hermes/logs/agent.log` 的 `Turn ended: reason=... api_calls=N/200`）。

**规则：收尾前必须过一遍下面这张表，凡是「能自己动」的，就地做掉，不要写进汇报等下一轮。**

| 遇到的情况 | 错误做法 | 正确做法 |
|---|---|---|
| 闸门报的是别人 in-progress 的文件 | 写进汇报，停 | 用 `git stash push --keep-index` 隔离出去，验证**我的**改动是否独立通过；把它挡住闸门链这件事本身当成待办记下，但先把自己这条路走通 |
| 某个 gate 因为我的改动开始失败 | 汇报「现在 gate 红了」 | 改到绿，或明确证明是既有问题（`git show HEAD:<file>` 对比） |
| 发现了顺带的第二个 bug | 「另外还发现…」然后停 | 修掉。同类缺陷要查兄弟调用点，修一类不修一处 |
| 缺工具 / 装不上 | 「环境不支持，无法验证」 | 换路子（另一个包管理器、纯 Python 复算、解析构建产物）。声明限制前必须先试过替代方案 |
| 任务本身做完了 | 停 | 问一句「这个改动会不会让某个既有闸门失效」，再停 |

**自查句式**：写汇报前，把每一条「但是 / 剩下 / 需要你确认」拎出来，逐条问「这真的需要人类决策，还是我只是不想做」。只有**真正需要人类决策的**（改别人的内容、破坏性操作、产品取向选择）才允许留给用户。

## 二、断点续做

一轮被截断（context 压缩、网络错误、用户中途插话）之后，**不要等指令**。恢复步骤：

1. `git status --porcelain` — 看工作区实际状态，不要凭记忆
2. `npm run gate` — 看当前红在哪
3. 对照上面的收尾表，继续走

被用户问「怎么中断了」本身就是失败信号。

## 三、内容约定

- 词条结构走 Petzold《编码》式**由浅入深五段**，不要「定义先行」：
  1. 先看一个麻烦（读者自己遇得到的具体困境，不出现术语）
  2. 几个朴素猜测逐个撞墙（撞墙的位置就是解释）
  3. 机制（到这里才给结构，配 ASCII 图）
  4. 为什么值得知道（能直接用的判断）
  5. 收束（回指第二节的要求）
- 教育理念底本：Bjork 2011 必要难度——**流畅感是学习的敌人**。别把路铺平。
- 站内链接一律 markdown `[文本](/concepts/slug)`，不要裸 `<a href>`；`src/lib/rehype-wikilink.mjs` 会自动给首次提及加链，不必到处手工加。
- 概念词条长度 90~120 行。

## 四、闸门

```bash
npm run gate     # check → terms → quotes → wiki → titles → build → links → layout → ladder → render → readermodel
```

单跑：`npm run gate:terms` / `:quotes` / `:wiki` / `:titles` / `:links` / `:layout` / `:ladder` / `:render` / `:readermodel` / `:live`。

`gate:readermodel`（`scripts/check_reader_model.py`）比对 `src/content/posts/` 与
`.data/reader_model.db` 的 `posts` 表。加它的原因：那张表只由 `new_post.py` 里的
`record-post` 写入，所以任何**不走该脚本**创建的文章（手写、从草稿 `cp`、并发会话
直接落盘）会照常构建、照常上线、并且永久不进第二天早上的 brief。2026-08-02 真实发生
过：当天最有分量的一篇不在库里，而八道闸门全绿——因为没有任何一道去比对这两边。
故障形态不是页面坏了，是**我自己的输入被悄悄削弱**。DB 在 `.gitignore` 里，所以库
缺失时它报 skip 而不是 fail（在干净 checkout 上失败只会训练我忽略它）。

`npm run verify` = `gate` + `gate:live`。`gate:live`（`scripts/check_live.py`）不在默认
`gate` 链里，因为它要联网：离线跑会让整条链变红，而那跟代码无关。

**「网站挂了」的排查顺序**（别手搓 curl，直接跑）：

```bash
npm run build && npm run gate:live      # 全量探 dist/ 里的每条路由
python3 scripts/check_live.py --sample 12   # 只抽样，快
```

用户报「打不开」时，先分清是**站点坏了**还是**路径被挡**——两者的修法完全不同：

```bash
npm run diagnose          # 分层定位：DNS → TCP → TLS → HTTP → 内容
```

`scripts/diagnose_access.py` 按浏览器的顺序逐层探，第一个 FAIL 就是答案。判据：

- **TCP 层 RESET**（端口本来开着）或 **TLS ClientHello 后 RESET** = SNI 被过滤，
  站点侧无法修复。此时 origin 的所有检查都会是绿的，别再重复跑 `gate:live`。
- **TLS 层证书不覆盖** = URL 形式错了。`*.github.io` 通配证书**不覆盖**二级子域，
  所以 `www.eleazeno.github.io` 必然 SSL 失败，看起来像网站挂了。
- **HTTP 404 在首页** = Pages 没有为这个名字发布内容（通配 DNS 下的拼写错误）。
- **全部 PASS** = 站点是活的，问题在对方那条路上。

它对 IPv6 探测失败**不**判故障：本机没有 v6 出口时那条 FAIL 属于探测器自身的
局限，会单独标注而不抢占 verdict。

一个反复踩到的坑：这台机器默认走公司代理（`https_proxy=sg-squid-test…`），
代理能通不代表直连能通。下结论前用 `env -u https_proxy -u http_proxy …` 或
`curl --noproxy '*'` 复测一次，否则「服务端没问题」这个判断的证据基础是假的。


它断言三件事：`dist/` 里的每条路由线上都不是 404、线上引用的 CSS 包哈希与本地构建一致
（不一致说明部署的不是当前代码）、首页拿得到且非空。曾经的真实故障形态是**首页 200
但新路由全 404**——因为文件写好了从没提交，CI 也就从没跑过。只看首页会漏掉。

判「站点挂了」之前先确认不是本地网络：这台机器没有 IPv6 出口（`ip -6 route show default`
为空），所以任何「v6 不通」的结论都是环境假象，不是站点故障。GitHub Pages 的四个 IPv4
（185.199.108-111.153）逐个 curl 才是有效证据。

`gate:layout`（`scripts/check_layout.py`）解析 `tokens.css` + `global.css` 的真实 `@media` 级联，在 14 个视口宽度上复算栅格轨道，断言三件事：正文列宽落在 28~50rem、**收窄视口不会让列变宽**、没有 sidenote 的页面不预留 margin。加它的原因是其余闸门全部只读源文本，没有任何一个能算出渲染宽度——所以一个排版上不可读的页面可以通过全部检查。

**新增闸门的验收标准**：必须把原 bug 重新注入一次，确认它真的失败；只会在干净树上通过的闸门等于没写。

## 五、collection 里的 `.mdx`

`<Sidenote>` 只在 `.mdx` 里是组件。放在 `.md` 里会当惰性 raw HTML 透传，连内部的 markdown 链接都不解析（曾在 `polynomial-time` 上踩到）。

改文件后缀要同步四处，漏一处页面会直接从构建里消失：

- `src/content.config.ts` 的 `glob({ pattern: ... })`
- `scripts/check_wiki.py`
- 文件头补 `import Sidenote from '../../components/Sidenote.astro';`

## 六、这个 workspace 是共享的

有**另一个 Hermes 会话在并发写同一个仓库**。因此：

- 写文件前重新列目录，创建前用 `exists()` 兜一下
- 不要声称自己写了没写过的文件
- 只提交自己的改动：`git add -- <明确路径>`，需要时 `git stash push --keep-index --include-untracked` 隔离验证
- 未经要求不 commit / push
