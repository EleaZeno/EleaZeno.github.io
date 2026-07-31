---
title: "币基交易"
aliases: ["币基交易", "coinbase", "coinbase transaction", "区块奖励", "block reward", "铸币交易"]
oneLiner: "每个区块的第一笔交易，没有输入、凭空造出新币归打包者——这是所有比特币唯一的诞生方式。"
domain: crypto
level: core
prerequisites: ["block", "utxo"]
related: ["transaction-fee", "block", "hashrate"]
sources:
  - title: "Bitcoin: A Peer-to-Peer Electronic Cash System"
    url: https://bitcoin.org/bitcoin.pdf
---

## 先看一个麻烦

维护这个网络要花真钱：电费、硬件、带宽。没有公司、没有股东、没人发工资，谁来干这个活？

而且更根本的问题：第一枚币从哪来？每笔交易都要求输入是"之前某笔交易的输出"（见 UTXO），那么最开始那笔的输入是什么？

## 朴素办法：预先造好，然后分发

先铸造全部货币，交给一个基金会，按贡献分给参与者。

这需要一个可信的分配方，也就重新引入了那个白皮书想拿掉的中心。而且"按贡献分配"要有人判断贡献，判断权就是权力。

## 机制：区块的第一笔交易可以没有输入

白皮书第 6 节的做法：

> By convention, the first transaction in a block is a special transaction that starts a new coin owned by the creator of the block.

按约定，区块的第一笔交易是一笔特殊交易，它**开启一枚新币**，归该区块的创建者所有。

这笔交易没有输入。它是唯一被允许无中生有的地方，而额度由协议写死，所有节点都会检查——多铸一分钱，区块就被全网拒绝。

于是两个问题一次解决：

- **激励**：干活有钱，不需要任何人发工资。
- **发行**：新币的唯一入口，而且发行速度由协议而非任何人决定。

原文给了个类比：

> The steady addition of a constant of amount of new coins is analogous to gold miners expending resources to add gold to circulation. In our case, it is CPU time and electricity that is expended.

持续加入固定数量的新币，类似金矿工消耗资源把黄金投入流通；这里消耗的是 CPU 时间和电力。

（`a constant of amount of` 是原文的语法错误，不是笔误转录。）

## 回访：这是"矿工"这个词唯一的来处

上面那句黄金类比里的 `gold miners`，是 `miners` 在整篇白皮书里**唯一**的一次出现，而且指的是真的金矿工。`mining` 作为独立单词在原文中出现 **0 次**。

论文全程管这些参与者叫 **node**（节点）。"矿工""挖矿"是社区后来造的词，它带来一个副作用：让人以为这些节点的主要职能是生产货币，而在白皮书的框架里它们的职能是**给交易排序**，新币只是报酬。

## 边界与常见误解

白皮书里**没有**这些东西，都是后来加的：

- `coinbase` 这个词：0 次。
- 21 million / 2100 万上限：0 次。原文只说 `a predetermined number of coins`（一个预定数量），没给数字。
- 减半（halving）：0 次。奖励递减的**方式**原文完全没规定。
- `reward` 这个词：0 次。

也就是说，比特币最著名的几个货币参数，一个都不在这篇论文里。它们写在代码里。
