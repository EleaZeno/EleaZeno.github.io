---
title: "比特"
aliases: ["比特", "bit", "bits", "binary digit", "二进制位"]
oneLiner: "信息的单位：一个比特就是消除一半可能性所需的信息量，恰好是一个双稳态开关能存的量。"
domain: theory
level: intro
prerequisites: []
related: ["entropy", "hash-function"]
sources:
  - title: "A Mathematical Theory of Communication"
    url: https://people.math.harvard.edu/~ctm/home/text/others/shannon/entropy/entropy.pdf
---

## 先看一个麻烦

你想告诉朋友一个 1 到 8 之间的数，但只能回答他的是非问题。最少要问几个问题？

试试看。"大于 4 吗？"——不管答什么，剩下的可能性从 8 个变成 4 个。"大于 2 吗？"（假设答案落在 1–4）——剩 2 个。再一个问题，定了。

三个问题。而 8 = 2³。

## 朴素办法：拿可能性个数当单位

既然有 8 种可能，说这条消息"值 8 个信息"行不行？

不行，因为它不可加。两个这样的数合起来有 8 × 8 = 64 种可能，但你显然只需要问 3 + 3 = 6 个问题。信息量应该相加，可能性个数却在相乘。

取对数就对上了：log₂8 = 3，log₂64 = 6。这就是为什么信息的单位建立在对数上——它把乘法变成加法，匹配"两倍的存储装两倍的东西"这个直觉。

## 机制：一个开关，一个比特

香农 1948 年那篇论文给了这个单位一个名字和一个物理锚点：

> If the base 2 is used the resulting units may be called binary digits, or more briefly bits, a word suggested by J. W. Tukey.

以 2 为底得到的单位叫 binary digits，简称 **bits**。这是"比特"一词在文献里的首次露面，而且命名权被记在同事 Tukey 名下。

紧接着一句给了它形状：

> A device with two stable positions, such as a relay or a flip-flop circuit, can store one bit of information.

一个有两个稳定状态的装置——继电器或触发器——存一个比特。

这句话是全部要点。继电器是个啪嗒作响的机械开关，你能拿在手里。N 个开关能存 N 个比特，因为总状态数是 2^N，而 log₂2^N = N。抽象的量被钉在了具体的物件上。

## 回访：比特不等于"一个 0 或 1"

这是最值得记住的区别。

一枚正面概率 90% 的硬币，翻一次的结果仍然只需一个 0/1 来记录。但它携带的信息只有约 0.47 比特（见熵），因为你事先已经相当确定。

所以"一个比特"是**信息量的单位**，"一个二进制位"是**存储的格子**。一个格子最多装一个比特，但常常装得更少——这个缝隙就是压缩存在的理由。

英文里这个区别也被压扁了：bit 同时指两者。中文"位"和"比特"偶尔能分开用，但多数场合也混着。

## 边界

字节（byte）是 8 个比特，但这是约定而非必然，早期机器有 6 位、7 位、9 位的字节。网络速率里的 Kb/s（比特）和文件大小里的 KB（字节）差 8 倍，是最常见的混淆来源。
