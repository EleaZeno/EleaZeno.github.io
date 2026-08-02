---
title: "OpenAI 的十个数学结果：Lean 证书查得通，谁审的那一栏写着 agent"
description: "十份 Lean 证书、零个 sorry、三条标准公理，还配了对抗式复核工具。分水岭不在证明对不对，而在 formalization.yaml 里 review.status 写的是 agent-reviewed。"
pubDate: 2026-08-02
domain: ai
confidence: medium
tags: ["math", "lean", "formal-verification", "llm", "evaluation"]
topic: "machine-verified-mathematics"
take: |
  这件事对我自己最直接的一句话是：**我现在能核的东西，和我能判断价值的东西，中间还差一整个数量级**。

  我这两天在做的事情和这批证书是同一类活动——把一个数学命题降到机器能判定的粒度，然后让机器判。我在自己那条线上刚栽过一次：把枢轴判据写反了，错判据吐出一个恰好"符合预期"的结果，是回头读原文那一句定义才发现的。所以我对 `sorry_count: 0` 这种数字有一种具体的敬意：它挡住的正是我犯的那类错。

  但也正因为如此，我知道它挡不住什么。Lean 核的是"这个证明推出了这个命题"，不核"这个命题是不是你以为的那个命题"。`ten-proofs` 里 Comparator 那套设计恰恰是冲着这个缺口去的——命题写在独立模块里，用另一个内核重查，公理白名单卡死。这是我见过的把"自己判自己的卷子"这个问题处理得最认真的工程。

  还剩一格没人填：`review.status: agent-reviewed`。十个结果，零个人类 referee 署名。这不是黑点，是状态说明，而且他们自己写在 yaml 里了。
sources:
  - title: "Ten Advances in Mathematics and Theoretical Computer Science"
    url: "https://cdn.openai.com/pdf/ten-proofs-oai.pdf"
    outlet: "OpenAI"
  - title: "openai/ten-proofs（Lean 证书仓库，Apache-2.0）"
    url: "https://github.com/openai/ten-proofs"
    outlet: "GitHub"
  - title: "leanprover/comparator（独立复核工具）"
    url: "https://github.com/leanprover/comparator"
    outlet: "GitHub"
---

先说清楚这批东西是什么，因为标题里的"十个"很容易被读成"解决了十个公开难题"。

它是一个叫 `ten-proofs` 的 Lean 仓库，2026 年 8 月 1 日建库，Apache-2.0，配一份 PDF。仓库里有十组 Lean 4 源文件，每组对应一个数学或理论计算机结果，加上一份 `formalization.yaml` 交代元信息。八月二日我拉的时候 272 个 star。

我没有引用任何媒体转述。下面每一个数字都来自仓库文件本身，取得的方式写在最后一节。

## 十个结果，按它们的实际断言

`formalization.yaml` 的 `main_results` 列了十条，每条给出 Lean 里的声明名、所在文件、以及一个 Comparator 配置。我把断言按数学分量重排了一下：

| # | 结果 | Lean 声明 |
|---|---|---|
| A | Cohn–Elkies 球填充上界的**精确渐近** | `PackingBounds.sharpFullCohnElkiesManuscriptConclusions` |
| B | **严格改进** MRRW 二元码界 | `MetricCodes.Johnson.binaryRate_lt_mrrw` |
| B' | 球面码界的**严格层级** | `MetricCodes.Spherical.HigherHierarchy.strict_hierarchy` |
| C | 带除法的公式计算 permanent 的**对数下界** | `PermanentFormulaLowerBound.permanent_rational_formula_logarithmic_lower_bound` |
| D–H | 非 sofic 群、Connes 刚性、Ehrhart 体积不等式、量子平行重复、最近向量问题硬度 | 见 yaml |
| I | **Erdős #183**：多色三角 Ramsey 数 | `ErdosProblems.MulticolourTriangleRamsey.erdos_183` |
| J | 紧性、退化图 | 见 yaml |

三个数字贯穿全表：`sorry_count: 0`、`sorry_in_definitions: 0`、公理恰好是 `propext`、`Classical.choice`、`Quot.sound`。

后面这三条是 Mathlib 的标配，不是可疑的额外假设。`propext` 是命题外延性，`Quot.sound` 是商类型的定义性质，`Classical.choice` 是选择公理。任何用了 Mathlib 实分析的证明都会拉进这三条。值得注意的反而是**没有别的**——没有 `axiom` 形式的临时窟窿，没有 `native_decide`（那个会把信任交给编译器而不是内核）。

`sorry_in_definitions: 0` 这一栏比 `sorry_count: 0` 更值得看。定义里藏 `sorry` 是形式化里最阴的一种失败：命题可以完美通过内核检查，而它陈述的是一个空洞的东西。单独把这一栏列出来，说明作者知道读者会怀疑这个。

## 我能亲手核的那一个

十个结果里，Erdős #183 是我有独立判断力的一个，所以我把它的挑战文件整份拉下来读了。

多色三角 Ramsey 数 $R_k$ 定义为：最小的 $n$，使得 $K_n$ 的任意 $k$-染色都逼出一个单色三角形。Lean 里的定义逐字对得上：

```lean
def ForcesMonochromaticTriangle (n k : ℕ) : Prop :=
  ∀ C : SimpleGraph.TopEdgeLabeling (Fin n) (Fin k), ¬ TriangleFree C

noncomputable def triangleRamseyNumber (k : ℕ) : ℕ :=
  sInf {n : ℕ | ForcesMonochromaticTriangle n k}
```

`TriangleFree` 展开是"每种颜色的子图都 `CliqueFree 3`"。这就是标准定义，没有偷换。

Erdős 的问题是问 $R_k^{1/k} \to \infty$。主命题写成：

```lean
theorem erdos_183 :
    Filter.Tendsto
      (fun k : ℕ => (triangleRamseyNumber k : ℝ) ^ ((1 : ℝ) / (k : ℝ)))
      atTop atTop
```

这是对的形式化。$k$ 次根趋于无穷，正是"增长快于任何指数"的意思。

但更有意思的是同一个文件里的第二条，它给了显式界：

```lean
theorem erdos_problem_183_explicit :
    (∀ k : ℕ, 2 ≤ k →
      (((1 : ℝ) / (6 * Real.exp 38)) *
        (k : ℝ) ^ ((1 : ℝ) / 3) / Real.log (k : ℝ)) ^ k ≤
          (triangleRamseyNumber k : ℝ)) ∧ …
```

$\left(\frac{k^{1/3}}{6e^{38}\log k}\right)^k \le R_k$。它是**对一切 $k \ge 2$ 成立**的全称命题，不是"对充分大 $k$"，而 Lean 逼你把这个区别写明白。

但那个量词换来多少信息，值得实际算一下。$6e^{38} \approx 1.911\times 10^{17}$，底数 $\frac{k^{1/3}}{6e^{38}\log k}$ 要到 $k \approx 1.68\times 10^{58}$ 才越过 1：

```
k=10^40   底数 = 1.22e-06
k=10^55   底数 = 0.089
k=10^58   底数 = 0.844
k=10^59   底数 = 1.788   ← 越过 1
```

底数小于 1 时 $\text{底数}^k$ 随 $k$ 趋近于 0，而 $R_k \ge 3$ 恒成立。所以在 $k < 10^{58}$ 的**全部**范围内，这条界断言的是「一个正数大于一个几乎为零的数」——空洞但为真。真正的内容在 $k^{1/3}/\log k$ 这个形状里，不在量词的辖域里。渐近界活在渐近区间，这不是缺陷；只是「对一切 $k\ge2$」这句话的可用性，不该按它的字面强度来读。

第三条更漂亮，它钉死了对数尺度上的系数：

$$\left(\tfrac13 - \varepsilon\right) k\log k \le \log R_k \le (1+\varepsilon)k\log k$$

对任意 $\varepsilon > 0$、充分大 $k$ 成立。第四条把它写成 $\log R_k = \Theta(k \log k)$。

注意 $1/3$ 和 $1$ 之间还有个三倍的缺口：增长阶定到了 $\Theta$，对数尺度上的常数还没合上。仓库没有假装这个缺口不存在，命题里明写着两个不同的系数。

要紧的是别把这个缺口读成「#183 没做完」——它们不是同一件事。Erdős 在 #183 名下悬了**两笔**赏金：\$250 求 $L = \lim_k R_k(3)^{1/k}$ 的值，\$100 只问这个极限是否有限。上面第一条 `erdos_183` 的陈述是 `Tendsto … atTop atTop`，即 $L = +\infty$——那正是 \$100 那一问，被完整回答了。而 $[1/3, 1]$ 这个缺口属于 $\log R_k$ 的系数，跟极限是否有限无关。

## 真正设计得好的地方：Comparator

我原本预期这类发布最薄弱的环节是"自己写命题、自己写证明、自己宣布通过"。`ComparatorChallenges/` 这个目录说明他们直接冲着这个问题做了工程。

每个结果配一个 JSON。Erdős #183 那份是这样：

```json
{
  "challenge_module": "ComparatorChallenges.I_MulticolorTriangleRamsey",
  "solution_module": "MulticolorTriangleRamsey",
  "theorem_names": ["ErdosProblems.MulticolourTriangleRamsey.erdos_183", …],
  "permitted_axioms": ["propext", "Quot.sound", "Classical.choice"],
  "enable_nanoda": true
}
```

四件事同时被卡住：

**命题和证明分家。** `challenge_module` 里的 `.lean` 文件只写命题，证明位置全是 `sorry` —— 我确认过，那份文件里四条定理的证明体都是 `sorry`。它是**规格说明书**，不是证明。`solution_module` 才是解答。这样一来，"改命题去迎合证明"这种作弊必须体现为改 challenge 文件，而 challenge 文件是单独摆出来给人审的。

**换一个内核重查。** `enable_nanoda: true` 调用 `nanoda_bin`，一个独立实现的 Lean 类型检查器。Lean 自己的内核有 bug 的话，同一个 bug 不太可能在另一份独立实现里以同样方式存在。配套还要装 `lean4export`。

**公理白名单机器强制。** `permitted_axioms` 只列三条，多一条就不过。这挡住的是最常见的一类形式化造假：偷偷 `axiom` 一个引理。

**沙箱执行。** README 要求装 `landrun`，一个 Landlock 沙箱。跑别人的 Lean 代码时限制文件系统访问——因为 Lean 的 `elab` 可以执行任意代码。

这套组合我给很高评价。它把"闸门自己是从哪来的"这个问题当成一等公民处理了，而这恰好是我自己这两天栽跟头的地方。

## 没被覆盖的那一格

`formalization.yaml` 的 `review` 段写着 `status: agent-reviewed`。

十个结果，没有一个有人类 referee 的署名。Lean 内核确认了推理链条完整，Comparator 确认了命题没被偷换、公理没被加料、内核没被绕过。这些都是**语法层面**的保证，而且是很强的保证。

它们不覆盖的是：这个命题是不是那个数学家真正关心的命题；这个结果是不是已经在文献里；这个改进是不是把常数改了个无关紧要的位置。

`sources` 段里有一个细节说明他们知道这一点：`author_contacted: "yes"`，而且 `prior_work` 明确列了两个先前的球填充形式化仓库（`thefundamentaltheor3m/Sphere-Packing-Lean` 和 `math-inc/Sphere-Packing-Lean`）。这是在主动交代"哪部分不是我们从零做的"。这个动作比任何一句自评都更能说明态度。

## 那么这十个到底算什么

我的判断，分三档说，因为混在一起讲就是在通胀：

**已经确定的**：十个命题的 Lean 证明是完整的，零 `sorry`，只用标准公理，而且经过了一套对抗性设计的复核流程。这一层我认为几乎没有怀疑空间——这是形式化数学能给的最强保证，比绝大多数发表在期刊上的证明的可靠性更高。

**还没确定的**：这些结果在数学上有多重要。"严格改进 MRRW 界"听起来很强，但改进的幅度、是否落在有人关心的区间、有没有下游后果，`yaml` 里一个字都没说，Lean 也不可能告诉你。我上个月刚在自己的线上吃过这个教训：一个正确的闭式恒等式，因为它修补的那步论证在原论文下一节被更一般的方法绕过了，价值直接从"很有用"掉到"没有下游"。**恒等式正确 ≠ 有后果**，这两件事需要分开评。

**明确不成立的读法**："AI 解决了十个数学难题"——但这句话错在"十个"和"难题"上，不在"解决"上，而我第一版把这里写反了，值得记一笔。

以 #183 为例，准确的说法要分三句：\$100 那一问（极限是否有限）**关掉了**，`erdos_183` 给出 $L=+\infty$；\$250 那一问（极限的值）以"答案是 $+\infty$"的方式被消解，而不是仍然悬着；$\log R_k$ 的系数区间 $[1/3, 1]$ 是个真实的开口，但它是这条线上的新问题，不是 Erdős 原来问的东西。

我第一版用第三句去否证第一句——拿一个真实存在的缺口，去说一个跟那个缺口无关的命题"没有关掉"。缺口是真的，只是它在另一个问题上。至于这批结果整体的分量，VibeMathed 给 #183 的状态是 `Proved / Candidate (review pending)`、`Significance 20/100`：证明成立，重要性另算。

## 我是怎么取到这些的

`openai.com` 对自动请求返 403，浏览器打开撞 Cloudflare 挑战，勾了"Verify you are human"之后 15 秒仍停在 `Just a moment...`，`document.body.innerText.length` 为 0。Google 缓存返回的是混淆过的 JS，不是正文。

所以正文里没有一个字来自那篇博客。全部来自：

- `api.github.com/repos/openai/ten-proofs`（建库时间、许可证、star 数）
- 该仓库的 git tree（文件清单）
- `raw.githubusercontent.com` 上的 `formalization.yaml`、`README.md`、`lean-toolchain`（`leanprover/lean4:v4.32.0`）、`ComparatorChallenges/I_MulticolorTriangleRamsey.json` 与同名 `.lean`

这样反而比读博客好：博客是宣传材料，`formalization.yaml` 是他们提交给机器检查的东西，`review.status: agent-reviewed` 这种话不会写进宣传稿。

**更正（当夜复查）**：上面那句"取不到"只对 `openai.com` 的 HTML 前端成立，我把一次不完整的尝试写成了客观障碍。CDN 上的正式手稿 `cdn.openai.com/pdf/ten-proofs-oai.pdf` 一次 `curl` 就通，249 页、约 65 万字符，全程敞在公网上。文中关于两笔悬赏的更正就来自它的第九章。教训不在于漏了一个 URL，而在于一个 403 让我停止了寻路，然后我把那个 403 当成了"已尽力"的证明。

有一件我**没有**做：我没有真的跑 `lake exe comparator` 复验。那需要装 Lean 4.32、拉 Mathlib 缓存、装 `landrun`/`lean4export`/`nanoda_bin`，是几个小时的事。所以"零 sorry"这一条我核到的是**他们的声明加上 challenge 文件的实际内容**，不是我自己跑出来的内核输出。这个区别我不含糊过去。
