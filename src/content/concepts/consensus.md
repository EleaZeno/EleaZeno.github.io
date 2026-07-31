---
title: "共识"
aliases: ["共识", "consensus", "共识机制", "consensus mechanism", "达成一致"]
oneLiner: "一群互不信任、可能失联的参与者，最终对同一份记录取得一致——难点从来不是投票，而是不知道该问谁。"
domain: systems
level: core
prerequisites: ["byzantine-generals", "longest-chain"]
related: ["byzantine-generals", "longest-chain", "proof-of-work", "fork-orphan"]
sources:
  - title: "Bitcoin: A Peer-to-Peer Electronic Cash System"
    url: https://bitcoin.org/bitcoin.pdf
---

## 先看一个麻烦

十个人要决定明天几点开会。发消息投票就行——只要每个人都收到了所有票，大家算出的结果必然一样。

但如果消息会丢、会延迟、会重复，而且**你不知道总共有多少人**呢？你收到七票，不知道是只有七个人，还是有十个人而三票在路上。这时你没法判断自己算出的结果是不是最终结果。

## 朴素办法：过半数就算通过

设定"超过半数即通过"。

问题是分母未知。开放网络里任何人可以随时加入，也没有人有权发身份证，所以"半数"是多少票没人知道。更糟的是一个人可以伪装成一万个（见女巫攻击），投票这个动作本身就不可信。

## 机制：不投票，看谁烧了更多电

比特币的解法绕开了"清点参与者"这一步。

每个节点接受哪条链，取决于哪条链**累积的工作量最大**（见最长链规则）。而工作量无法伪造——你要么真的算了那么多哈希，要么没有。

于是共识的判据从"多数人同意"变成"多数算力同意"，而算力是物理量，不能靠伪造身份放大。原文这句话点出了这个转换：

> The proof-of-work also solves the problem of determining representation in majority decision making. If the majority were based on one-IP-address-one-vote, it could be subverted by anyone able to allocate many IPs. Proof-of-work is essentially one-CPU-one-vote.

一个 CPU 一票，而不是一个 IP 一票。

注意这里的共识是**概率性**的：没有一个时刻宣布"定了"，只是随着后续区块累积，被推翻的概率指数下降（第 11 节算的正是这个）。这和传统分布式共识（如 Paxos、PBFT）给出的确定性最终性不同。

## 回访：白皮书里这个词只出现一次

`consensus mechanism` 这个短语在白皮书里出现 **1** 次，而且不在讨论核心机制的地方。原文第 11 节前后讲的是概率和最长链，几乎不用"共识"这个词。

"共识机制"作为一个类别名（PoW / PoS / PBFT 并列）是后来行业造的框架。用这个框架回头读白皮书容易产生一个错觉：以为中本聪在设计一个"共识算法"。他实际在做的更具体——给交易排一个所有人最终会同意的顺序。

## 边界

比特币的共识不解决"信息是否真实"，只解决"顺序是否一致"。一笔交易在链上被确认，只说明网络同意它发生的位置，不说明背后的商业行为合法或诚实。

另外它需要同步性假设：如果网络分区持续足够久，两边会各自延长自己的链，重连时较短的一边被丢弃。这不是 bug，是设计里明确接受的代价。
