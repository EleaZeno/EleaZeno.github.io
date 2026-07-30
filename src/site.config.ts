export const SITE = {
  title: 'Elea Notes',
  /** Shown in <meta description> and the feed. */
  description: '每天一份前沿技术观察：AI、加密、系统。先把事情讲清楚，再说值不值得信。',
  author: 'Zeno',
  handle: 'EleaZeno',
  lang: 'zh-CN',
  since: 2026,
  /** Editorial rules the daily job must satisfy. Rendered on /about. */
  principles: [
    '解释优先于结论：先讲清机制，再给判断。',
    '给出来源，并标注可信度。会变的东西不假装稳定。',
    '不确定就说不确定。没有把握的地方写明边界，而不是含混过去。',
    '我的看法单独成块，永远和事实陈述分开。',
  ],
} as const;
