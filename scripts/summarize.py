#!/usr/bin/env python3
"""data/data.json 의 각 항목에 한국어 제목 번역(title_ko)과 핵심 요약(summary_ko)을 붙인다.

요약 엔진: GitHub Models (무료) — OpenAI 호환 엔드포인트, GITHUB_TOKEN 으로 인증.
  - 모델: openai/gpt-4o-mini
  - 비용 0, 별도 API 키 불필요 (CI 에서는 permissions: models: read 필요)
설계 원칙: graceful — 토큰이 없거나 호출이 실패해도 예외 없이 원본을 그대로 두고 종료한다.
  따라서 이 단계가 실패해도 build.py 는 정상 동작한다(번역/요약만 비어 있음).

다른 LLM(예: Anthropic Claude)으로 바꾸려면 _post() 한 함수만 교체하면 된다.
"""
import json, os, subprocess, urllib.request, urllib.error, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
ENDPOINT = "https://models.github.ai/inference/chat/completions"
MODEL = "openai/gpt-4o-mini"

BASE = ("너는 한국인 개발자를 위한 AI·테크 뉴스 큐레이터다. "
        "과장·추측 없이 주어진 정보에 근거해 자연스러운 한국어로 답한다.")

# 제목 번역 + 요약을 함께 생성 (HN·Reddit·YouTube·SNS 처럼 '제목'이 있는 섹션)
SYSTEM_FULL = BASE + (
    ' 각 입력 항목에 대해 다음 두 가지를 만든다. '
    'title_ko: 항목의 title 을 자연스럽고 간결한 한국어 제목으로 번역한다(제품명·고유명사·약어는 살리고 직역투는 피한다. '
    '이미 한국어면 그대로 두거나 다듬는다). '
    'summary_ko: 그 항목이 무엇이고 왜 주목할 만한지 한국어 1문장(공백 포함 40~90자)으로 요약한다. '
    '반드시 JSON 객체 {"items": [{"title_ko": "...", "summary_ko": "..."}, ...]} 형식으로, '
    '입력과 같은 개수·순서로 답한다.')

# 요약만 생성 (GitHub 저장소처럼 제목이 식별자(repo 이름)라 번역이 무의미한 섹션)
SYSTEM_SUMMARY = BASE + (
    ' 각 항목이 무엇이고 왜 주목할 만한지 한국어 1문장(공백 포함 40~90자)으로 요약한다. '
    '반드시 JSON 객체 {"summaries": ["요약1", "요약2", ...]} 형식으로, 입력과 같은 개수·순서로 답한다.')


def get_token():
    for k in ("GITHUB_TOKEN", "GH_TOKEN", "MODELS_TOKEN"):
        if os.environ.get(k):
            return os.environ[k]
    try:  # 로컬 실행 편의: gh CLI 로그인 토큰 사용
        return subprocess.run(["gh", "auth", "token"], capture_output=True, text=True,
                              timeout=10).stdout.strip() or None
    except Exception:
        return None


def _post(token, system, contexts, max_tokens):
    payload = {
        "model": MODEL,
        "temperature": 0.3,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": "항목 목록(JSON):\n" +
             json.dumps(contexts, ensure_ascii=False)},
        ],
    }
    req = urllib.request.Request(
        ENDPOINT, data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        body = json.load(r)
    return json.loads(body["choices"][0]["message"]["content"])


def translate_and_summarize(token, items, context_fn, label):
    """제목 있는 섹션: title_ko + summary_ko 동시 부여."""
    if not items:
        return
    contexts = [context_fn(it) for it in items]
    try:
        parsed = _post(token, SYSTEM_FULL, contexts, 120 * len(items) + 300)
        arr = parsed.get("items") if isinstance(parsed, dict) else parsed
        if not isinstance(arr, list):
            raise ValueError("unexpected response shape")
    except Exception as e:
        print(f"  [{label}] 건너뜀: {type(e).__name__}: {e}")
        return
    for it, o in zip(items, arr):
        if isinstance(o, dict):
            if isinstance(o.get("title_ko"), str) and o["title_ko"].strip():
                it["title_ko"] = o["title_ko"].strip()
            if isinstance(o.get("summary_ko"), str) and o["summary_ko"].strip():
                it["summary_ko"] = o["summary_ko"].strip()
    done = sum(1 for it in items if it.get("title_ko"))
    print(f"  [{label}] {done}/{len(items)} 제목번역+요약 완료")


def summarize_only(token, items, context_fn, label):
    """제목이 식별자인 섹션(GitHub): summary_ko 만 부여."""
    if not items:
        return
    contexts = [context_fn(it) for it in items]
    try:
        parsed = _post(token, SYSTEM_SUMMARY, contexts, 60 * len(items) + 200)
        sums = parsed.get("summaries") if isinstance(parsed, dict) else parsed
        if not isinstance(sums, list):
            raise ValueError("unexpected response shape")
    except Exception as e:
        print(f"  [{label}] 건너뜀: {type(e).__name__}: {e}")
        return
    for it, s in zip(items, sums):
        if isinstance(s, str) and s.strip():
            it["summary_ko"] = s.strip()
    done = sum(1 for it in items if it.get("summary_ko"))
    print(f"  [{label}] {done}/{len(items)} 요약 완료")


def main():
    path = ROOT / "data" / "data.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    token = get_token()
    if not token:
        print("요약 건너뜀: 토큰 없음(GITHUB_TOKEN). 원본 그대로 빌드됩니다.")
        return

    summarize_only(token, data.get("github_trending", []),
                   lambda r: {"name": r["repo"], "desc": r.get("desc", "")}, "GitHub")
    translate_and_summarize(token, data.get("hackernews", []),
                            lambda r: {"title": r["title"], "info": "Hacker News 프론트페이지 글"}, "HN")
    translate_and_summarize(token, data.get("reddit", []),
                            lambda r: {"title": r["title"], "info": f"Reddit r/{r.get('sub','')} 글"}, "Reddit")
    translate_and_summarize(token, data.get("youtube", []),
                            lambda r: {"title": r["title"], "info": f"유튜브 채널 {r['channel']} 영상",
                                       "desc": r.get("desc", "")[:200]}, "YouTube")
    translate_and_summarize(token, data.get("social", []),
                            lambda r: {"title": r["title"], "info": f"{r.get('handle','')} 의 X(트위터) 화제 글"}, "SNS")

    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("번역·요약 반영 완료 → data/data.json")


if __name__ == "__main__":
    main()
