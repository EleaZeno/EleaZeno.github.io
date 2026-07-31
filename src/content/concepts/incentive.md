---
title: "激励"
aliases: ["激励", "incentive", "经济激励", "激励相容"]
oneLiner: "让诚实比作恶更赚钱，于是不需要惩罚机制也没人想作恶。"
domain: crypto
level: core
prerequisites: ["coinbase-transaction", "hashrate"]
related: ["coinbase-transaction", "transaction-fee", "fifty-one-percent-attack"]
sources:
  - title: "Bitcoin: A Peer-to-Peer Electronic Cash System"
    url: https://bitcoin.org/bitcoin.pdf
---

## 先看一个麻烦

一个没有警察的系统里，怎么让人守规矩？

传统答案是抓和罚。但在一个匿名、开放、任何人可随时进出的网络里，你既查不出作恶者是谁，也没法执行处罚——他换个身份就回来了（见女巫攻击）。

## 朴素办法：靠道德或声誉

指望参与者出于共同利益自觉维护网络？规模一大就失效，因为搭便车总是更划算。

声誉系统呢？需要稳定身份，而稳定身份在匿名网络里正是不存在的东西。

## 机制：让作恶在算术上不划算

白皮书第 6 节的做法不是阻止作恶，而是让作恶**变成一桩亏本生意**。

拥有多数算力的攻击者面临一个选择：

- 用这些算力**诚实挖矿**：稳定拿到新币和手续费。
- 用这些算力**攻击网络**：可能双花成功一次。

原文的论证：

> He ought to find it more profitable to play by the rules, such rules that favour him with more new coins than everyone else combined, than to undermine the system and the validity of his own wealth.

他应当发现按规则行事更有利可图——这些规则给他的新币比其他所有人加起来还多——而不是去破坏这个系统以及他自己财富的有效性。

最后半句是这个设计的关键：攻击者持有的币，其价值依赖于这个系统被信任。攻击成功也就砸了自己的资产。他的利益和网络的健康被**绑在一起**了。

## 回访：这是全篇唯一不靠数学的论证

白皮书大部分内容可以形式化验证：哈希、签名、第 11 节的概率。但激励这一节是**经济学论证**，它依赖于攻击者理性、且在意自己持币的价值。

这是原文最脆弱的一环，而它的脆弱是有据可查的：

- 自私挖矿（Eyal & Sirer, 2014）证明存在一种策略，让算力不足半数的矿池也能拿到超额收益——即偏离协议**可以**更赚钱。
- 手续费市场的不稳定性（Carlsten 等, 2016）证明当新币奖励归零后，只靠手续费的激励可能不稳。

这两篇都不是推翻，而是划出了原文论证的适用边界。

## 边界与常见误解

白皮书里 `reward` 这个词出现 **0** 次。"区块奖励"是后来的说法，原文用的是 incentive（激励）。

也要注意：激励机制**不保证**安全，它只是让攻击不划算。一个不在乎亏钱的攻击者（比如敌对国家）不受这个论证约束。原文的前提是攻击者追求利润。
