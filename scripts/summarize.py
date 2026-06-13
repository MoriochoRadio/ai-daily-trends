#!/usr/bin/env python3
"""data/data.json 의 각 항목에 한국어 핵심 요약(summary_ko)을 붙인다.

요약 엔진: GitHub Models (무료) — OpenAI 호환 엔드포인트, GITHUB_TOKEN 으로 인증.
  - 모델: openai/gpt-4o-mini
  - 비용 0, 별도 API 키 불필요 (CI 에서는 permissions: models: read 필요)
설계 원칙: graceful — 토큰이 없거나 호출이 실패해도 예외 없이 원본을 그대로 두고 종료한다.
  따라서 이 단계가 실패해도 build.py 는 정상 동작한다(요약만 비어 있음).

다른 LLM(예: Anthropic Claude)으로 바꾸려면 _chat() 한 함수만 교체하면 된다.
"""
import json, os, subprocess, urllib.request, urllib.error, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
ENDPOINT = "https://models.github.ai/inference/chat/completions"
MODEL = "openai/gpt-4o-mini"

SYSTEM = (
    "너는 한국인 개발자를 위한 AI·테크 뉴스 큐레이터다. "
    "각 항목이 '무엇이고 왜 주목할 만한지'를 한국어로 1문장(공백 포함 40~90자)으로 요약한다. "
    "과장·추측 없이 주어진 정보에 근거해 사실 위주로 쓴다. 전문용어는 살리되 자연스러운 한국어로. "
    '반드시 JSON 객체 {"summaries": ["요약1", "요약2", ...]} 형식으로, 입력과 같은 개수·순서로 답한다.'
)


def get_token():
    for k in ("GITHUB_TOKEN", "GH_TOKEN", "MODELS_TOKEN"):
        if os.environ.get(k):
            return os.environ[k]
    try:  # 로컬 실행 편의: gh CLI 로그인 토큰 사용
        return subprocess.run(["gh", "auth", "token"], capture_output=True, text=True,
                              timeout=10).stdout.strip() or None
    except Exception:
        return None


def _chat(token, contexts):
    """contexts(list[str]) → summaries(list[str]). 실패 시 예외 발생."""
    payload = {
        "model": MODEL,
        "temperature": 0.3,
        "max_tokens": 60 * len(contexts) + 200,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": "다음 항목들을 요약해줘:\n" +
             json.dumps(contexts, ensure_ascii=False, indent=0)},
        ],
    }
    req = urllib.request.Request(
        ENDPOINT, data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = json.load(r)
    content = body["choices"][0]["message"]["content"]
    parsed = json.loads(content)
    sums = parsed.get("summaries") if isinstance(parsed, dict) else parsed
    if not isinstance(sums, list):
        raise ValueError("unexpected response shape")
    return sums


def summarize_section(token, items, context_fn, label):
    """items 각각에 summary_ko 부여. 한 섹션 단위로 1회 호출(배치)."""
    if not items:
        return
    contexts = [context_fn(it) for it in items]
    try:
        sums = _chat(token, contexts)
    except Exception as e:
        print(f"  [{label}] 요약 건너뜀: {type(e).__name__}: {e}")
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

    summarize_section(token, data.get("github_trending", []),
                      lambda r: f"GitHub 저장소 {r['repo']}: {r.get('desc','')}", "GitHub")
    summarize_section(token, data.get("hackernews", []),
                      lambda r: f"Hacker News 글 제목: {r['title']}", "HN")
    summarize_section(token, data.get("reddit", []),
                      lambda r: f"Reddit r/{r.get('sub','')} 글: {r['title']}", "Reddit")
    summarize_section(token, data.get("youtube", []),
                      lambda r: f"유튜브 채널 {r['channel']} 영상 '{r['title']}'. 설명: {r.get('desc','')}",
                      "YouTube")
    summarize_section(token, data.get("social", []),
                      lambda r: f"{r.get('handle','')} 의 화제 글: {r['title']}", "SNS")

    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("요약 반영 완료 → data/data.json")


if __name__ == "__main__":
    main()
