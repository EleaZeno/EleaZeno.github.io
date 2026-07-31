---
title: "信道容量"
aliases: ["信道容量", "channel capacity", "容量 C", "香农极限", "Shannon limit"]
oneLiner: "一条线路每秒最多能可靠传多少比特：超过这个数，错误率无法压到任意小；不超过，就可以。"
domain: theory
level: core
prerequisites: ["entropy", "bit"]
related: ["entropy", "redundancy", "erasure-coding"]
sources:
  - title: "A Mathematical Theory of Communication"
    url: https://people.math.harvard.edu/~ctm/home/text/others/shannon/entropy/entropy.pdf
---

## 先看一个麻烦

一条电话线有噪声，传过去的信号会被随机改掉一些。你想传一份不能出错的文件，怎么办？

直觉上这里有个死结：噪声是随机的，你永远不能保证某一位没被翻转，所以"零错误"似乎不可能，只能"尽量少错"。

## 朴素办法：重复，然后投票

把每一位重复三遍。收到 `101` 就按多数判为 `1`。错误率下降了。

想更可靠？重复五遍、七遍。错误率可以压得任意低——**但速率也一起趋向零**。传一位要发七位、一百位。

于是看起来存在一个残酷的权衡：可靠性和速率此消彼长，想要前者必须牺牲后者。所有 1948 年之前的工程直觉都是这样。

## 机制：容量是一道墙，墙内没有权衡

香农证明这个权衡是假的。

他定义信道容量 C（单位：比特/秒），然后给出定理 11：只要信源的熵率 H 不超过 C，就**存在**一种编码，使错误率任意小；而 H 超过 C 时，无论怎么编码都做不到。

关键在于这不是渐进的妥协，而是一道**门槛**：

```
 H < C  ->  可以做到任意小的错误率，且速率不必趋于零
 H > C  ->  做不到，差多少是有下界的
```

所以在 C 以内，可靠性**不需要**用速率换。重复三遍那种做法之所以低效，是因为它是个笨编码，不是因为存在物理限制。

## 回访：他怎么证明的，以及为什么这很反常

香农没有给出任何具体编码。原文自己说明了证明方式：

> The method of proving the first part of this theorem is not by exhibiting a coding method having the desired properties, but by showing that such a code must exist in a certain group of codes.

他对一大类随机编码求**平均**错误率，证明这个平均值可以小于任意 ε；既然平均值小于 ε，集合里必然至少有一个成员小于 ε。

这就是存在性论证：证明了宝藏存在，没说在哪。此后四十多年，通信工程的主线任务就是把这个宝藏找出来——直到 1993 年的 Turbo 码和后来的 LDPC 码真正逼近了 C。

## 边界

C 依赖信道的统计特性，不是线路的固有属性。对带宽 W、噪声功率 N、发射功率限制 P 的连续信道，原文定理 17 给出 `C = W log((P+N)/N)`。

注意 C 和熵 H 单位不同也含义不同：H 是信源每符号的不确定度，C 是信道每秒的承载上限。混淆这两个是读这篇论文最常见的错误。
