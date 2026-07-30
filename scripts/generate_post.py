#!/usr/bin/env python3
"""Generate one daily knowledge post as a markdown file under src/content/posts/.

Reads config from topics.yml (rotation pool + prompt settings) and talks to an
OpenAI-compatible chat completions endpoint. Designed to run both locally and
inside GitHub Actions with zero extra dependencies beyond `requests`+`PyYAML`.

Environment:
  LLM_API_KEY   required. Bearer token for the endpoint.
  LLM_BASE_URL  optional. Default https://api.deepseek.com
  LLM_MODEL     optional. Default deepseek-chat
  POST_DATE     optional. YYYY-MM-DD, defaults to today in Asia/Shanghai.
  TOPIC         optional. Overrides topic rotation for a one-off post.
  DRY_RUN       optional. "1" prints the post to stdout instead of writing it.

Exit codes:
  0 wrote (or would write) a post
  1 hard failure (bad config, API error, unusable response)
  2 nothing to do (a post for POST_DATE already exists)
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "src" / "content" / "posts"
TOPICS_FILE = ROOT / "topics.yml"
CHINA_TZ = timezone(timedelta(hours=8))

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"
REQUEST_TIMEOUT = 300
MAX_ATTEMPTS = 3


class GenerationError(RuntimeError):
    """Raised when the model response cannot be turned into a post."""


def log(msg: str) -> None:
    print(f"[generate] {msg}", file=sys.stderr, flush=True)


# --------------------------------------------------------------------------- #
# config
# --------------------------------------------------------------------------- #

def load_topics() -> dict[str, Any]:
    if not TOPICS_FILE.exists():
        raise GenerationError(f"missing {TOPICS_FILE.name}")
    data = yaml.safe_load(TOPICS_FILE.read_text(encoding="utf-8")) or {}
    topics = data.get("topics") or []
    if not isinstance(topics, list) or not topics:
        raise GenerationError("topics.yml must define a non-empty `topics` list")
    data["topics"] = [str(t).strip() for t in topics if str(t).strip()]
    return data


def pick_topic(cfg: dict[str, Any], day: date) -> str:
    """Deterministic rotation: same date always maps to the same topic.

    Using the ordinal instead of random keeps reruns idempotent and makes the
    rotation auditable, while `recent` avoids repeating what we just covered.
    """
    override = os.environ.get("TOPIC", "").strip()
    if override:
        return override

    topics: list[str] = cfg["topics"]
    recent = recent_topics(limit=min(len(topics) - 1, 14))
    ordered = topics[day.toordinal() % len(topics):] + topics[: day.toordinal() % len(topics)]
    for topic in ordered:
        if topic not in recent:
            return topic
    return ordered[0]


def recent_topics(limit: int) -> set[str]:
    """Topics used by the most recent posts, read back from their frontmatter."""
    if limit <= 0 or not POSTS_DIR.exists():
        return set()
    files = sorted(POSTS_DIR.glob("*.md"), reverse=True)[:limit]
    found: set[str] = set()
    for path in files:
        meta, _ = split_frontmatter(path.read_text(encoding="utf-8"))
        topic = (meta or {}).get("topic")
        if topic:
            found.add(str(topic))
    return found


def split_frontmatter(text: str) -> tuple[dict[str, Any] | None, str]:
    if not text.startswith("---"):
        return None, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, text
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return None, text
    return (meta if isinstance(meta, dict) else None), parts[2]


# --------------------------------------------------------------------------- #
# model call
# --------------------------------------------------------------------------- #

SYSTEM_PROMPT = """你是一位资深工程师，为个人技术博客写每日知识笔记。

要求：
- 用简体中文写作，语气平实、直接，像同事间讲清一件事，不用营销腔和感叹号。
- 内容必须具体：给出真实存在的机制、命令、参数、代码或数字。不确定的事实要明确标注"存疑"，绝不编造 API、库名、版本号或性能数据。
- 结构：先给结论/要点，再展开细节。合理使用二级标题、列表和代码块。
- 篇幅 800-1500 字。宁可讲透一个点，不要泛泛罗列十个点。
- 不要写"引言""总结""希望这篇文章对你有帮助"这类套话，直接进入内容。

严格只输出一个 JSON 对象，不要包在 markdown 代码块里，字段如下：
{
  "title": "不超过 40 字的标题，不要用冒号堆砌",
  "description": "一句话摘要，60-110 字，用于首页和 RSS",
  "tags": ["2-4 个小写英文或中文短标签"],
  "body": "markdown 正文，不含 H1 标题，不含 frontmatter"
}"""


def build_user_prompt(topic: str, cfg: dict[str, Any], day: date) -> str:
    extra = str(cfg.get("extra_instructions") or "").strip()
    avoid = sorted(recent_titles(limit=20))
    lines = [f"今天是 {day.isoformat()}。请围绕这个主题写一篇：{topic}"]
    if avoid:
        lines.append(
            "以下标题最近已经写过，请换角度、换具体切入点，不要重复：\n"
            + "\n".join(f"- {t}" for t in avoid)
        )
    if extra:
        lines.append(f"额外要求：{extra}")
    return "\n\n".join(lines)


def recent_titles(limit: int) -> set[str]:
    if not POSTS_DIR.exists():
        return set()
    titles: set[str] = set()
    for path in sorted(POSTS_DIR.glob("*.md"), reverse=True)[:limit]:
        meta, _ = split_frontmatter(path.read_text(encoding="utf-8"))
        title = (meta or {}).get("title")
        if title:
            titles.add(str(title))
    return titles


def call_model(system: str, user: str) -> str:
    api_key = os.environ.get("LLM_API_KEY", "").strip()
    if not api_key:
        raise GenerationError("LLM_API_KEY is not set")
    base_url = os.environ.get("LLM_BASE_URL", DEFAULT_BASE_URL).strip().rstrip("/")
    model = os.environ.get("LLM_MODEL", DEFAULT_MODEL).strip()

    url = f"{base_url}/v1/chat/completions" if not base_url.endswith("/v1") else f"{base_url}/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.7,
        # A 1500-word Chinese post plus JSON escaping runs well past 4k tokens,
        # and reasoning models spend budget before emitting any content.
        "max_tokens": 16384,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            log(f"calling {model} (attempt {attempt}/{MAX_ATTEMPTS})")
            resp = requests.post(url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT)
            if resp.status_code >= 400:
                # 4xx other than 429 will not fix themselves; fail fast.
                if resp.status_code != 429 and resp.status_code < 500:
                    raise GenerationError(f"HTTP {resp.status_code}: {resp.text[:400]}")
                raise requests.HTTPError(f"HTTP {resp.status_code}: {resp.text[:200]}")
            choice = resp.json()["choices"][0]
            content = choice["message"]["content"]
            if not content or not content.strip():
                raise requests.HTTPError("empty completion")
            # A cut-off response yields unparseable JSON further down; say why.
            if choice.get("finish_reason") == "length":
                raise requests.HTTPError(
                    "completion hit max_tokens and was truncated; raise max_tokens "
                    "or ask for a shorter post"
                )
            return content
        except GenerationError:
            raise
        except Exception as exc:  # noqa: BLE001 - retry on any transport/shape error
            last_error = exc
            log(f"attempt {attempt} failed: {type(exc).__name__}: {exc}")
            if attempt < MAX_ATTEMPTS:
                time.sleep(5 * attempt)
    raise GenerationError(f"model call failed after {MAX_ATTEMPTS} attempts: {last_error}")


def strip_outer_fence(text: str) -> str:
    """Remove a code fence that wraps the *whole* payload.

    Must not use a greedy/lazy search over the full text: the JSON `body` field
    contains markdown code fences of its own, and matching those would extract a
    fragment from inside the post instead of the JSON object.
    """
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if len(lines) < 2:
        return text
    closing = next((i for i in range(len(lines) - 1, 0, -1) if lines[i].strip() == "```"), None)
    if closing is None:
        return "\n".join(lines[1:]).strip()
    return "\n".join(lines[1:closing]).strip()


def parse_response(raw: str) -> dict[str, Any]:
    """Extract the JSON object, tolerating an outer code fence and stray prose."""
    text = strip_outer_fence(raw.strip())
    if not text.startswith("{"):
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise GenerationError(f"no JSON object in response: {raw[:300]}")
        text = text[start : end + 1]

    try:
        data = json.loads(text, strict=False)
    except json.JSONDecodeError as exc:
        raise GenerationError(f"invalid JSON: {exc}; head={text[:300]}") from exc
    if not isinstance(data, dict):
        raise GenerationError("response JSON is not an object")

    title = str(data.get("title") or "").strip()
    description = str(data.get("description") or "").strip()
    body = str(data.get("body") or "").strip()
    if not title or not body:
        raise GenerationError("response missing title or body")
    if len(body) < 200:
        raise GenerationError(f"body too short ({len(body)} chars) — likely a refusal or truncation")

    tags = data.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    clean_tags = [str(t).strip() for t in tags if str(t).strip()][:4]

    return {
        "title": title,
        "description": description or title,
        "tags": clean_tags,
        "body": strip_leading_h1(body),
    }


def strip_leading_h1(body: str) -> str:
    """The layout renders its own H1; drop a duplicate one from the model."""
    lines = body.lstrip().splitlines()
    if lines and lines[0].startswith("# "):
        return "\n".join(lines[1:]).lstrip()
    return body


# --------------------------------------------------------------------------- #
# output
# --------------------------------------------------------------------------- #

def slugify(text: str, fallback: str) -> str:
    """ASCII slug; Chinese titles collapse to empty so we fall back to the date."""
    norm = unicodedata.normalize("NFKD", text)
    ascii_only = norm.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_only).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)[:60].strip("-")
    return slug or fallback


def yaml_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def render_markdown(post: dict[str, Any], topic: str, day: date, model: str) -> str:
    tags = ", ".join(yaml_quote(t) for t in post["tags"])
    front = [
        "---",
        f"title: {yaml_quote(post['title'])}",
        f"description: {yaml_quote(post['description'])}",
        f"pubDate: {day.isoformat()}",
        f"tags: [{tags}]",
        f"topic: {yaml_quote(topic)}",
        f"generatedBy: {yaml_quote(model)}",
        "---",
        "",
    ]
    return "\n".join(front) + post["body"].rstrip() + "\n"


def resolve_day() -> date:
    raw = os.environ.get("POST_DATE", "").strip()
    if raw:
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError as exc:
            raise GenerationError(f"POST_DATE must be YYYY-MM-DD, got {raw!r}") from exc
    return datetime.now(CHINA_TZ).date()


def main() -> int:
    try:
        cfg = load_topics()
        day = resolve_day()
        POSTS_DIR.mkdir(parents=True, exist_ok=True)

        existing = list(POSTS_DIR.glob(f"{day.isoformat()}-*.md"))
        if existing and os.environ.get("DRY_RUN") != "1":
            log(f"post for {day} already exists: {existing[0].name}")
            return 2

        topic = pick_topic(cfg, day)
        log(f"date={day} topic={topic}")

        raw = call_model(SYSTEM_PROMPT, build_user_prompt(topic, cfg, day))
        post = parse_response(raw)
        model = os.environ.get("LLM_MODEL", DEFAULT_MODEL)
        markdown = render_markdown(post, topic, day, model)

        if os.environ.get("DRY_RUN") == "1":
            print(markdown)
            log("DRY_RUN=1, nothing written")
            return 0

        name = f"{day.isoformat()}-{slugify(post['title'], day.isoformat())}.md"
        target = POSTS_DIR / name
        target.write_text(markdown, encoding="utf-8")
        log(f"wrote {target.relative_to(ROOT)} ({len(markdown)} chars)")

        # Surface the path/title to the workflow for the commit message.
        summary = os.environ.get("GITHUB_OUTPUT")
        if summary:
            with open(summary, "a", encoding="utf-8") as fh:
                fh.write(f"post_path={target.relative_to(ROOT)}\n")
                fh.write(f"post_title={post['title']}\n")
        return 0
    except GenerationError as exc:
        log(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
