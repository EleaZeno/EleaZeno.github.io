---
title: "压缩率"
aliases: ["压缩率", "压缩比", "compression ratio", "相对熵", "relative entropy"]
oneLiner: "一份数据最多能压到多小，由它自身的熵决定；压过这条线就必然丢东西。"
domain: theory
level: core
prerequisites: ["entropy", "redundancy"]
related: ["entropy", "redundancy", "prefix-code"]
sources:
  - title: "A Mathematical Theory of Communication"
    url: https://people.math.harvard.edu/~ctm/home/text/others/shannon/entropy/entropy.pdf
---

## 先看一个麻烦

一个压缩软件宣称能把任何文件压到一半。听起来很美——但如果真的对**任何**文件都成立，那你可以反复压：1 GB 压到 512 MB，再压到 256 MB，一直压到 1 个字节。

显然荒谬。所以"能压多少"必须有个上限。这个上限由什么决定？

## 朴素办法：看文件里有多少重复

数重复的片段，把重复的替换成短记号。这是 zip 的基本思路，实际有效。

但它答不出**极限**在哪：换个更聪明的算法能不能再压一点？有没有一个数，说"到此为止，任何算法都过不去"？

## 机制：熵就是那个数

香农的答案是：一个信源每符号的熵 H，就是平均每符号所需的最少比特数。

原文定义了"相对熵"这个量——信源的熵与它在同一符号集下能取到的最大熵之比——然后直接点明：

> The ratio of the entropy of a source to the maximum value it could have while still restricted to the same symbols will be called its relative entropy. This is the maximum compression possible when we encode into the same alphabet.

这就是**可能的最大压缩**。1 减去相对熵就是冗余度（见冗余度）。

手算一个例子。四个符号，概率 1/2、1/4、1/8、1/8：

```
H = 0.5·1 + 0.25·2 + 0.125·3 + 0.125·3 = 1.75 比特/符号
```

等长编码要 2 比特/符号。所以最好的压缩率是 1.75/2 = 87.5%，冗余度 12.5%。而且这个 1.75 是**可以达到**的（用前缀码，见前缀码），不是遥不可及的理论值。

## 回访：为什么压缩过的文件压不动

已经压好的文件，冗余度接近零，熵接近最大值。再压一次没有可利用的结构，所以压不动——甚至会因为格式开销略微变大。

这也解释了开头那个悖论：不存在对所有输入都能压缩的算法。压缩靠的是**输入不是均匀随机的**这个事实；对真正随机的数据，H 已经等于最大值，压不了。

## 边界

这条线只管**无损**压缩。JPEG、MP3 那类有损压缩可以突破 H，因为它们不再要求精确还原——它们在丢弃人眼人耳不敏感的部分，属于另一套理论（率失真理论）。

另外 H 是对**特定信源模型**算的。把英文按单字母算熵得到约 4 比特，考虑到词和语法后降到 1 比特出头。模型越好，测出的 H 越低，可压的空间越大——现代大模型压缩文本效果好，本质就是它的英文模型比字母频率表准得多。
