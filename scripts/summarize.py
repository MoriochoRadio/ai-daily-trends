#!/usr/bin/env python3
"""data/data.json 의 각 항목에 한국어 제목 번역(title_ko)과 핵심 요약(summary_ko)을 붙인다.

요약 엔진: Groq (무료 티어) — OpenAI 호환 엔드포인트, GROQ_API_KEY 로 인증.
  - 모델은 고정하지 않는다. 무료 모델은 몇 달 단위로 종료되므로(2026-08-16 llama-3.3-70b
    종료로 요약이 44일간 조용히 0건이었다) 실행할 때마다 Groq 모델 목록을 조회해
    선호 순서대로 살아 있는 모델을 고르고, 모델 오류가 나면 다음 후보로 넘어간다.
    특정 모델로 고정하려면 GROQ_MODEL 환경변수를 주면 된다(선택).
  - 추론 모델(gpt-oss 등)은 추론이 토큰 예산을 다 써서 json_validate_failed 가 나기 쉬워
    reasoning_effort 를 낮추고 예산을 넉넉히 준다. 모델이 거부하는 파라미터는 빼고 다시 보낸다.
  - (구) GitHub Models 는 2026-08 retirement brownout 으로 410 을 반환해 이전함.
설계 원칙: graceful — 키가 없거나 호출이 실패해도 예외 없이 원본을 그대로 두고 종료한다.
  따라서 이 단계가 실패해도 build.py 는 정상 동작한다(번역/요약만 비어 있음).
  대신 사람이 손봐야 하는 상황(키 거부, 쓸 모델 없음, 며칠 연속 요약 0건)은
  GITHUB_OUTPUT 의 alert 로 내보내고, 워크플로의 마지막 health 잡이 실패로 드러낸다.

다른 LLM(예: Anthropic Claude)으로 바꾸려면 _post() 한 함수만 교체하면 된다.
"""
import json, os, re, time, urllib.request, urllib.error, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
MODELS_URL = "https://api.groq.com/openai/v1/models"
# urllib 기본 UA(Python-urllib)는 Groq 앞단(Cloudflare)이 403으로 차단함
UA = "ai-daily-trends/1.0"
HEALTH_PATH = ROOT / "data" / "health.json"

# 선호 모델(앞일수록 우선). 목록에 없는 모델은 건너뛰고, 목록에만 있는 모델은 계열 순서로 뒤에 붙인다.
PREFERRED = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "moonshotai/kimi-k2-instruct",
             "llama-3.3-70b-versatile", "openai/gpt-oss-20b"]
FAMILIES = ["gpt-oss", "qwen", "kimi", "llama", "deepseek", "mistral", "gemma"]
# 채팅 요약에 맞지 않는 모델(음성·안전 분류기·에이전트 시스템 등)
EXCLUDE_WORDS = ("whisper", "tts", "guard", "safeguard", "compound", "playai", "orpheus",
                 "distil", "allam", "prompt")
ZERO_STREAK_ALERT = 3   # 일시 장애로 요약이 빈 날이 이만큼 이어지면 사람에게 알린다

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


class AuthError(Exception):
    """키가 거부됨 — 모델을 바꿔도 소용없으므로 이번 실행의 요약을 멈춘다."""


class ModelUnavailable(Exception):
    """시도할 모델이 더 이상 없음. transient=True 면 모델 문제가 아니라 서비스 일시 장애."""

    def __init__(self, msg, transient=False):
        super().__init__(msg)
        self.transient = transient


def get_token():
    return os.environ.get("GROQ_API_KEY") or None


def _request(url, token, payload=None, timeout=90):
    """(상태, 본문 텍스트, 헤더) 를 돌려준다. 네트워크 오류는 상태 0."""
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json", "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace"), r.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), e.headers
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return 0, str(e), {}


def rank_models(ids):
    """목록의 모델 id 를 선호 목록 → 계열 순서로 정렬하고, 요약에 안 맞는 모델은 뺀다."""
    usable = [i for i in ids if not any(w in i.lower() for w in EXCLUDE_WORDS)]

    def key(i):
        if i in PREFERRED:
            return (0, PREFERRED.index(i), i)
        fam = next((n for n, f in enumerate(FAMILIES) if f in i.lower()), len(FAMILIES))
        return (1, fam, i)
    return sorted(usable, key=key)


class ModelPicker:
    """이번 실행에서 쓸 모델 후보를 들고 있다가, 모델 오류가 나면 다음 후보로 넘긴다."""

    def __init__(self, token):
        pinned = os.environ.get("GROQ_MODEL", "").strip()
        status, body, _ = _request(MODELS_URL, token, timeout=30)
        if status in (401, 403):
            raise AuthError(f"모델 목록 조회 {status}: {body[:200]}")
        listed = []
        if status == 200:
            try:
                listed = [m["id"] for m in json.loads(body).get("data", [])
                          if m.get("active", True) and m.get("id")]
            except Exception:
                listed = []
        if listed:
            cands = rank_models(listed)
        else:  # 목록 조회가 일시적으로 안 되면 선호 목록을 그대로 시도한다
            print(f"  [모델] 목록 조회 실패({status}) — 선호 목록으로 진행")
            cands = list(PREFERRED)
        self.candidates = ([pinned] if pinned else []) + [c for c in cands if c != pinned]
        self.index = 0
        self.used = None
        self.transient_skips = 0   # 일시 오류만으로 연달아 넘긴 모델 수

    @property
    def model(self):
        if self.index >= len(self.candidates):
            raise ModelUnavailable("시도할 모델이 없음")
        return self.candidates[self.index]

    def next(self, reason, transient=False):
        print(f"  [모델] {self.model} 사용 불가({reason}) → 다음 후보")
        self.index += 1
        self.transient_skips = self.transient_skips + 1 if transient else 0
        # 두 모델 연속으로 429/5xx 만 난다면 모델이 아니라 Groq 쪽 장애 — 오늘은 접고 내일 다시 한다
        if self.transient_skips >= 2:
            raise ModelUnavailable("Groq 일시 장애로 보임", transient=True)


def _model_params(model):
    """모델 계열별 추론 설정 — 추론이 토큰을 다 써 JSON 이 잘리지 않게 한다."""
    m = model.lower()
    if "gpt-oss" in m:
        return {"reasoning_effort": "low"}
    if "qwen3" in m:
        return {"reasoning_effort": "none"}
    return {}


def _parse_content(content):
    try:
        return json.loads(content)
    except Exception:
        found = re.search(r"\{.*\}", content or "", re.S)
        if found:
            return json.loads(found.group(0))
        raise


def _post(picker, token, system, contexts, max_tokens):
    """현재 모델로 호출하고, 모델 문제면 다음 모델로, 일시 오류면 기다렸다 재시도한다."""
    user = "항목 목록(JSON):\n" + json.dumps(contexts, ensure_ascii=False)
    dropped = set()      # 모델이 거부한 파라미터
    budget_boost = 1
    transient_tries = 0
    while True:
        model = picker.model
        extra = _model_params(model)
        is_reasoning = bool(extra) and extra.get("reasoning_effort") != "none"
        payload = {
            "model": model,
            "temperature": 0.3,
            # gpt-oss 계열(추론 모델)은 max_tokens 를 400 으로 거부 — 신형 파라미터 사용
            "max_completion_tokens": (max_tokens + (1500 if is_reasoning else 0)) * budget_boost,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            **extra,
        }
        for p in dropped:
            payload.pop(p, None)
        status, body, headers = _request(ENDPOINT, token, payload)
        if status == 200:
            content = json.loads(body)["choices"][0]["message"]["content"]
            picker.used = model
            picker.transient_skips = 0
            return _parse_content(content)
        low = body.lower()
        print(f"  [api-error {status}] {model}: {body[:300]}")
        if status in (401, 403) and "model" not in low:
            raise AuthError(f"{status}: {body[:200]}")
        if status == 404 or "model_not_found" in low or "decommissioned" in low or "does not exist" in low:
            picker.next(status)
            dropped, budget_boost = set(), 1
            continue
        if status == 400:
            # 모델이 모르는 파라미터를 지목하면 그것만 빼고 다시 보낸다
            rejected = [p for p in ("reasoning_effort", "response_format", "temperature")
                        if p in low and p not in dropped]
            if rejected:
                dropped.add(rejected[0])
                continue
            if "json_validate_failed" in low and budget_boost == 1:
                budget_boost = 2   # 출력이 잘려 JSON 이 깨진 경우 — 예산을 늘려 한 번 더
                continue
            picker.next(status)
            dropped, budget_boost = set(), 1
            continue
        # 429·5xx·네트워크 — 잠시 쉬었다 같은 모델로 재시도, 계속되면 다음 모델
        transient_tries += 1
        if transient_tries >= 3:
            picker.next(f"{status} 반복", transient=True)
            transient_tries = 0
            continue
        wait = 10 * transient_tries
        try:
            wait = max(wait, min(65, int(float(headers.get("retry-after", 0)))))
        except (TypeError, ValueError):
            pass
        time.sleep(wait)


def translate_and_summarize(picker, token, items, context_fn, label):
    """제목 있는 섹션: title_ko + summary_ko 동시 부여."""
    if not items:
        return
    contexts = [context_fn(it) for it in items]
    try:
        parsed = _post(picker, token, SYSTEM_FULL, contexts, 120 * len(items) + 300)
        arr = parsed.get("items") if isinstance(parsed, dict) else parsed
        if not isinstance(arr, list):
            raise ValueError("unexpected response shape")
    except (AuthError, ModelUnavailable):
        raise
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


def summarize_only(picker, token, items, context_fn, label):
    """제목이 식별자인 섹션(GitHub): summary_ko 만 부여."""
    if not items:
        return
    contexts = [context_fn(it) for it in items]
    try:
        parsed = _post(picker, token, SYSTEM_SUMMARY, contexts, 60 * len(items) + 200)
        sums = parsed.get("summaries") if isinstance(parsed, dict) else parsed
        if not isinstance(sums, list):
            raise ValueError("unexpected response shape")
    except (AuthError, ModelUnavailable):
        raise
    except Exception as e:
        print(f"  [{label}] 건너뜀: {type(e).__name__}: {e}")
        return
    for it, s in zip(items, sums):
        if isinstance(s, str) and s.strip():
            it["summary_ko"] = s.strip()
    done = sum(1 for it in items if it.get("summary_ko"))
    print(f"  [{label}] {done}/{len(items)} 요약 완료")


SECTIONS = ("github_trending", "hackernews", "reddit", "youtube", "social")


def emit_alert(message):
    """워크플로의 health 잡이 읽도록 GITHUB_OUTPUT 에 기록한다 (로컬 실행 시엔 출력만)."""
    print(f"alert={message}")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"alert={message}\n")


def record_health(summarized, problem, model):
    """요약 0건 연속 일수를 data/health.json 에 남기고, 사람이 볼 일이면 alert 를 낸다."""
    try:
        prev = json.loads(HEALTH_PATH.read_text(encoding="utf-8"))
    except Exception:
        prev = {}
    streak = 0 if summarized else int(prev.get("summary_zero_streak", 0)) + 1
    HEALTH_PATH.write_text(json.dumps({
        "summary_zero_streak": streak,
        "last_model": model or prev.get("last_model"),
        "last_problem": problem,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    if problem == "auth":
        return "Groq 키가 거부됨 — console.groq.com 에서 키를 새로 만들어 GROQ_API_KEY 시크릿을 교체하세요"
    if problem == "no_model":
        return "Groq 에서 쓸 수 있는 모델을 찾지 못함 — summarize.py 의 PREFERRED/EXCLUDE_WORDS 확인 필요"
    if streak >= ZERO_STREAK_ALERT:
        return f"한국어 요약이 {streak}일 연속 0건 (마지막 원인: {problem or '알 수 없음'}) — Actions 로그 확인 필요"
    return ""


def main():
    path = ROOT / "data" / "data.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    token = get_token()
    if not token:
        print("요약 건너뜀: 키 없음(GROQ_API_KEY). 원본 그대로 빌드됩니다.")
        return

    problem, picker = None, None
    try:
        picker = ModelPicker(token)
        print(f"  [모델] 후보: {', '.join(picker.candidates[:5])}")
        summarize_only(picker, token, data.get("github_trending", []),
                       lambda r: {"name": r["repo"], "desc": r.get("desc", "")}, "GitHub")
        translate_and_summarize(picker, token, data.get("hackernews", []),
                                lambda r: {"title": r["title"], "info": "Hacker News 프론트페이지 글"}, "HN")
        translate_and_summarize(picker, token, data.get("reddit", []),
                                lambda r: {"title": r["title"], "info": f"Reddit r/{r.get('sub','')} 글"}, "Reddit")
        translate_and_summarize(picker, token, data.get("youtube", []),
                                lambda r: {"title": r["title"], "info": f"유튜브 채널 {r['channel']} 영상",
                                           "desc": r.get("desc", "")[:200]}, "YouTube")
        translate_and_summarize(picker, token, data.get("social", []),
                                lambda r: {"title": r["title"], "info": f"{r.get('handle','')} 의 X(트위터) 화제 글"}, "SNS")
    except AuthError as e:
        print(f"요약 중단: 키 거부 — {e}")
        problem = "auth"
    except ModelUnavailable as e:
        print(f"요약 중단: {e}")
        problem = "transient" if e.transient else "no_model"

    model = picker.used if picker else None
    data["summary_model"] = model
    summarized = sum(1 for s in SECTIONS for it in data.get(s, []) if it.get("summary_ko"))
    if not summarized and not problem:
        problem = "transient"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"번역·요약 반영 완료 → data/data.json (요약 {summarized}건, 모델 {model or '없음'})")
    emit_alert(record_health(summarized, problem, model))


if __name__ == "__main__":
    main()
