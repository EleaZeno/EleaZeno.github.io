# 学习阶梯改造合同

用户 2026-08-02 指令(整体批准):

> 你全部都做,而且我的目标不仅仅是让人记住,而是让一个没有基础的人把一个论文书籍之类逐渐搞懂,然后记住,然后会用。

四段阶梯: 看懂 -> 学会 -> 记住 -> 会用。每项必须有机械判据。

| # | 项 | 判据命令 | 状态 |
|---|---|---|---|
| 1 | 五篇 classics 译文 100% | check_translation_coverage.py | DONE 55/55 22/22 8/8 14/14 14/14 |
| 2 | 对比度达 WCAG AA | 手算 4.5:1 | DONE dark 4.86 light 4.50 |
| 3 | intro 层模板合规 | audit_template_coverage.py --require intro | DONE 24/24 |
| 4 | Apply 组件(会用) | grep class="apply" dist/ | DONE turing 2 处 |
| 5 | Apply 铺到其余四篇 | 每篇 >=2 个 Apply | DONE 12 个全站,dist 验证 12/12 渲染 |
| 6 | thesis 主旨句(全站 0) | grep -c 'class="thesis"' | TODO |
| 7 | core 层模板 16/35 | audit --require core | TODO |
| 8 | 术语覆盖(用了但没词条) | coverage-gates.md gate 2 | TODO |
| 9 | 前置声明不足 | coverage-gates.md gate 3 | TODO |
| 10 | 写进 new_post.py 模板 | grep Apply scripts/new_post.py | TODO |

不许把"已做完"写成叙事,只报比值。
