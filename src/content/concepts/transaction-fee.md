---
title: "手续费"
aliases: ["手续费", "交易费", "transaction fee", "transaction fees", "矿工费"]
oneLiner: "交易输入比输出多出来的那部分，谁把这笔交易打包进区块就归谁——不是协议规定的价格，是竞价。"
domain: crypto
level: core
prerequisites: ["utxo", "block"]
related: ["utxo", "coinbase-transaction", "change-output"]
sources:
  - title: "Bitcoin: A Peer-to-Peer Electronic Cash System"
    url: https://bitcoin.org/bitcoin.pdf
---

## 先看一个麻烦

区块有大小上限，每十分钟只能装那么多交易。想进区块的交易多于位置时，谁先进？

按先来后到排队？那么恶意发送方可以用海量小额交易把队伍堵死，反正不要钱。

## 朴素办法：协议规定一个价格

写死"每笔交易收 1 分钱"。

问题是这个数字定不下来。定低了挡不住垃圾交易，定高了小额支付没法用。而且网络拥堵程度每天都在变，一个写死的数字必然在多数时候是错的。更麻烦的是：改这个数字需要全网升级。

## 机制：不定价，让差额自己说话

白皮书第 6 节的做法极简：

> The incentive can also be funded with transaction fees. If the output value of a transaction is less than its input value, the difference is a transaction fee that is added to the incentive value of the block containing the transaction.

如果一笔交易的**输出总额小于输入总额**，差额就是手续费，归打包这笔交易的区块所有。

举例：输入 10 元，输出 3 元给对方 + 6.99 元找零给自己。少的那 0.01 元没有指定收款人，它自动归打包者。

注意这里没有"手续费字段"。手续费不是被声明的，是被**算出来的**——它就是那部分你没有指定去向的钱。协议不需要知道价格是多少，它只需要做减法。

于是排队规则自然浮现：打包者当然优先选差额大的交易。拥堵时想快就多留一点，不急就少留。价格由供需现场决定，不需要任何人拍板。

## 回访：这个设计是为了三十年后

白皮书紧接着说了一句话，指向很远：

> Once a predetermined number of coins have entered circulation, the incentive can transition entirely to transaction fees and be completely inflation free.

一旦预定数量的币全部进入流通，激励可以**完全转为手续费**，从而彻底无通胀。

这句话的意思是：新币奖励（见币基交易）会递减到零，那时手续费是维持网络安全的唯一收入。整个系统的长期存续押在这个机制上。

有意思的是白皮书**没有**说这一定行得通。后来有严肃论文（Carlsten 等，2016）论证过：只靠手续费时，挖矿激励可能变得不稳定，因为区块收入随交易池波动而剧烈起伏。这是原文留下的一个真实的开放问题。

## 边界与常见误解

白皮书用的是 `can also be funded`（也可以由手续费资助），不是必须。原文里手续费是**补充**，不是主角。

也没有"gas"这个概念——按计算量计价是以太坊的设计。比特币的手续费只和交易的**字节大小**与竞争程度相关，与它做了多少计算无关。
