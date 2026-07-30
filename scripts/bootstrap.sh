#!/usr/bin/env bash
# Re-create everything that lives outside the persistent volume.
#
# Why this exists: ~/.hermes (cron jobs, memory, session DB) sits on
# overlayfs in this pod and is lost on rebuild, while /home/shared/workspace
# is a real disk. Run this after a pod restart to restore the schedule.
#
#   bash /home/shared/workspace/blog/scripts/bootstrap.sh
#
# Idempotent: existing jobs with the same name are left alone.
set -euo pipefail

REPO="/home/shared/workspace/blog"
HERMES_DIR="/usr/local/lib/hermes-agent"

cd "$HERMES_DIR"
# shellcheck disable=SC1091
source venv/bin/activate 2>/dev/null || true

have_job() {
  hermes cron list 2>/dev/null | grep -Fq "$1"
}

echo "== node deps =="
if [ ! -d "$REPO/node_modules" ]; then
  (cd "$REPO" && npm ci --no-audit --no-fund)
else
  echo "node_modules present, skipping"
fi

echo "== reader model =="
python3 "$REPO/scripts/reader_model.py" sync >/dev/null && echo "coverage synced"

echo "== cron jobs =="
if have_job "blog-daily"; then
  echo "blog-daily exists, skipping"
else
  hermes cron create "0 7 * * *" \
    --name "blog-daily" \
    --skill daily-frontier-digest \
    --workdir "$REPO" \
    --deliver local \
    "今天的前沿汇总。严格按 daily-frontier-digest 技能执行：先读 reader_model brief 和 suggest，\
再真实检索当天的 AI / 加密 / 系统前沿（arXiv、工程博客、协议规范、事故报告），\
挑出 1-3 个真正值得写的，用 scripts/new_post.py 写成科普文章，每篇都要有 take（我的看法，\
说清它对 Hermes 或 AI 工程意味着什么）和真实来源。写完跑 npm run build 和 \
scripts/check_links.py，两个都过了再用 scripts/publish.py 发布。质量不够就只写一篇，\
今天确实没有值得写的就从候选队列里挑一个深入讲。"
  echo "blog-daily created"
fi

if have_job "blog-dream"; then
  echo "blog-dream exists, skipping"
else
  hermes cron create "30 2 * * *" \
    --name "blog-dream" \
    --workdir "$REPO" \
    --deliver local \
    "夜间反思。读今天 src/content/posts/ 里新增的文章和 scripts/reader_model.py brief 的输出，\
然后自由联想：这些东西之间有什么我白天没写出来的联系？哪个判断我其实没有把握？\
哪里我把'可能'写成了'是'？明天该去查什么？用 scripts/new_dream.py 写下来，\
不追求正确，追求诚实。可以多写几个 cycle。写完 npm run build 通过后用 scripts/publish.py 发布。"
  echo "blog-dream created"
fi

echo
hermes cron list 2>&1 | tail -20
