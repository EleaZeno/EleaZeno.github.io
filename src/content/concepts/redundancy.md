---
title: "冗余度"
aliases: ["冗余度", "冗余", "redundancy"]
oneLiner: "一段消息里本来就能猜到的那部分占多大比例：冗余度越高，能压掉的越多，抗噪能力也越强。"
domain: theory
level: core
prerequisites: ["entropy", "bit"]
related: ["entropy", "erasure-coding"]
sources:
  - title: "A Mathematical Theory of Communication"
    url: https://people.math.harvard.edu/~ctm/home/text/others/shannon/entropy/entropy.pdf
---

## 先看一个麻烦

把这句英文的元音全删掉：`Th qck brwn fx jmps vr th lzy dg.`

你大概仍能读出来。删掉了三分之一的字母，信息却没丢。

那么问题来了：那些能删掉还不影响理解的字母，本来算不算"信息"？

## 朴素办法：按字母数算

一段 100 个字母的英文，如果每个字母都算满 log₂27 ≈ 4.75 比特（26 字母加空格），总量是 475 比特。

但上面那个删元音的实验说明这个算法虚高了。字母之间不独立：`q` 后面几乎必然是 `u`，`th` 后面很可能是元音。这些约束意味着很多字母是**可以被猜出来**的，它们没有携带新信息。

## 机制：实际熵与最大熵的比值

香农的定义分两步。先定义相对熵：信源的实际熵，除以在同样符号集下它可能达到的最大熵。冗余度就是 1 减去这个比值。

$$
R = 1 - \frac{H_{\text{实际}}}{H_{\max}}
$$

代入英文：如果实际熵约 2.4 比特/字母，而最大是 4.75，那么相对熵约 0.5，冗余度也约 50%。这就是那个著名数字的来处：

> The redundancy of ordinary English, not considering statistical structure over greater distances than about eight letters, is roughly 50%.

> This means that when we write English half of what we write is determined by the structure of the language and half is chosen freely.

我们写英文时，一半由语言结构决定，一半是自由选择的。

## 回访：冗余是缺点还是优点，取决于你在干什么

同一个量，两个相反的用途。

**压缩**要消灭它。冗余度 50% 意味着理想情况下英文文本能压到一半。zip 之所以对文本有效、对已压缩的 JPEG 几乎无效，就是因为前者冗余大、后者冗余已被榨干。

**纠错**要制造它。刻意加入冗余，一部分符号损坏后仍能恢复原文——这正是纠删码和 RAID 的原理。删掉元音还能读，本质上和纠错码从损坏数据里恢复原文是同一件事。

所以通信系统在做一件看似矛盾的事：先用压缩去掉信源的**自然**冗余，再用纠错加上精心设计的**人工**冗余。前者的冗余是随机的、不可控的；后者是结构化的、按需分配的。

## 边界与常见误解

"英文冗余度 50%"这句话在转述里几乎总被说强了。原文写的是 roughly（大约），而且带一个很重的限定：**不考虑超过约八个字母距离的统计结构**。把更长距离的结构算进来，冗余度更高——香农 1951 年自己重做实验，把英文熵收紧到每字母 0.6–1.3 比特，对应冗余度远超 50%。
