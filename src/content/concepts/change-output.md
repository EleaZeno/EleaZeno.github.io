---
title: "找零"
aliases: ["找零", "change", "change output", "找零输出"]
oneLiner: "比特币的钱不能拆开花，所以付款时把整笔花掉，多的部分转回给自己——就像用整张钞票付账拿回零钱。"
domain: crypto
level: intro
prerequisites: ["utxo"]
related: ["utxo", "transaction-fee", "double-spending"]
sources:
  - title: "Bitcoin: A Peer-to-Peer Electronic Cash System"
    url: https://bitcoin.org/bitcoin.pdf
---

## 先看一个麻烦

你有一笔 10 元的钱，要付 3 元。

在银行账户模型里这很简单：余额从 10 变成 7。但比特币没有余额（见 UTXO），它只有一个个**不可分割的**钱包块。你手上那笔 10 元是一个整体，不能从中间切下 3 元。

## 朴素办法：让收款方退给我

付 10 元，请对方退 7 元回来？

这需要两笔交易、需要对方配合、对方不退你就没辙。而且对方要先有钱才能退。显然不行。

## 机制：一笔交易，两个输出

比特币的解法是：一笔交易可以有**多个输出**。

```
输入:  10 元（你的那一整块）
输出1:  3 元  -> 收款方
输出2:  7 元  -> 你自己的另一个地址   <- 这就是找零
```

那笔 10 元被整个消耗掉，同时生成两块新的钱：3 元归对方，7 元归你。你的"余额"从一块 10 元变成一块 7 元。

这和现金完全同构：你用一张 10 元的钞票买 3 元的东西，那张钞票交出去了，店员给你 7 元零钱。钞票不能撕，交易靠找零完成。

## 回访：为什么这让隐私变难

白皮书第 10 节明确承认了一个后果：

> Some linking is still unavoidable with multi-input transactions, which necessarily reveal that their inputs were owned by the same owner.

多输入交易必然暴露这些输入属于同一人。

找零把这个问题放大了。链上分析者看到一笔交易有两个输出，其中一个是"整数金额"（3 元）另一个是"奇怪的零头"（7 元），基本可以判定后者是找零、属于付款方。反复观察就能把一个人的多个地址聚成一簇。

这就是为什么白皮书说的是"keeping public keys anonymous"（保持公钥匿名）而不是承诺匿名——找零这个机制本身在持续泄露关联信息。

## 边界

白皮书正文里没有 `change` 这个词。第 9 节讨论了拆分与合并价值（Combining and Splitting Value），找零是这个机制的一个特例，名字是后来才有的。

现代钱包会做一些缓解：找零地址每次都换新的、把找零金额也做成整数、或用 CoinJoin 混合多人交易。但基本张力仍在。
