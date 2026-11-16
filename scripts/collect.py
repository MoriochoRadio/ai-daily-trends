#!/usr/bin/env python3
"""매일 AI 트렌드를 수집해 data/data.json 으로 저장한다.
소스: GitHub Trending(스크레이핑), Hacker News(Algolia API), Reddit(공개 RSS),
YouTube(채널 공개 RSS), 화제의 SNS(HN의 X 링크).
GitHub Actions 러너처럼 외부 네트워크가 열린 환경에서 실행하는 것을 전제로 한다.
"""
import json, os, re, html as ih, urllib.request, urllib.error, time, datetime, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
UA = {"User-Agent": "Mozilla/5.0 (AI-Daily-Trends bot)"}
# Reddit 은 단순 봇 UA 의 JSON 엔드포인트를 403 으로 차단하므로, 브라우저 헤더 + 공개 RSS 를 사용한다.
RSS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/rss+xml,application/atom+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

AI_KEYWORDS = ["ai", "llm", "gpt", "gemini", "claude", "openai", "anthropic", "model",
               "neural", "agent", "ml ", "machine learning", "deep learning", "rag",
               "transformer", "diffusion", "inference", "fine-tun", "embedding", "mcp"]

def fetch(url, timeout=20):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout)

def fetch_text(url):
    return fetch(url).read().decode("utf-8", "replace")

def is_ai(text):
    t = (text or "").lower()
    return any(k in t for k in AI_KEYWORDS)

# ---------- GitHub Trending ----------
def github_trending(limit=15):
    rows, seen = [], set()
    sources = ["https://github.com/trending?since=daily",
               "https://github.com/trending/python?since=daily",
               "https://github.com/trending/jupyter-notebook?since=daily"]
    for url in sources:
        try:
            html_doc = fetch_text(url)
        except Exception:
            continue
        for art in re.split(r'<article class="Box-row', html_doc)[1:]:
            m = re.search(r'href="/([^"]+)/stargazers"', art)
            if not m:
                continue
            repo = m.group(1)
            if repo in seen:
                continue
            d = re.search(r'<p class="col-9 color-fg-muted my-1 pr-4">(.*?)</p>', art, re.S)
            desc = ih.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", d.group(1))).strip()) if d else ""
            st = re.search(r"(\d[\d,]*)\s*stars today", art)
            stars = int(st.group(1).replace(",", "")) if st else 0
            lg = re.search(r'itemprop="programmingLanguage">([^<]+)</span>', art)
            lang = lg.group(1).strip() if lg else ""
            # AI 우선: 키워드 매칭되면 가중치
            seen.add(repo)
            rows.append({"repo": repo, "url": f"https://github.com/{repo}", "desc": desc,
                         "stars_today": stars, "lang": lang, "_ai": is_ai(repo + " " + desc)})
    return pick_trending(rows, limit)

# 하루 별이 이보다 적으면 '트렌딩'이라 보기 어렵다 (언어별 페이지에는 하루 ★4 같은 저장소도 섞여 나온다)
MIN_STARS_TODAY = 20
# 다만 기준을 넘는 저장소가 너무 적은 날엔 빈 섹션이 되지 않도록 이만큼은 채운다
MIN_TRENDING = 8

def pick_trending(rows, limit):
    """AI 저장소만, 하루 별 순으로 고르되 기준 미만은 부족할 때만 채워 넣는다."""
    ai = sorted((r for r in rows if r["_ai"]), key=lambda r: -r["stars_today"])
    strong = [r for r in ai if r["stars_today"] >= MIN_STARS_TODAY]
    picked = strong if len(strong) >= MIN_TRENDING else ai[:MIN_TRENDING]
    picked = picked[:limit]
    for r in picked:
        r.pop("_ai", None)
    return picked

# ---------- Hacker News ----------
_HN_CACHE = None

def _hn_front_page(retries=3):
    """HN front page 검색 결과(hacker_news·social_from_hn 공용, 1회만 호출).
    일시 장애면 백오프 재시도 후 빈 결과 — 실행 전체를 죽이지 않는다."""
    global _HN_CACHE
    if _HN_CACHE is None:
        for attempt in range(retries):
            try:
                _HN_CACHE = json.load(fetch(
                    "https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=60"))
                break
            except Exception:
                if attempt < retries - 1:
                    time.sleep(5 * (attempt + 1))
        else:
            _HN_CACHE = {}
    return _HN_CACHE

def hacker_news(limit=8):
    data = _hn_front_page()
    out = []
    for h in data.get("hits", []):
        title = h.get("title", "")
        if not is_ai(title):
            continue
        out.append({"title": title,
                    "url": h.get("url") or f"https://news.ycombinator.com/item?id={h['objectID']}",
                    "points": h.get("points", 0), "comments": h.get("num_comments", 0),
                    "hn_url": f"https://news.ycombinator.com/item?id={h['objectID']}"})
    out.sort(key=lambda x: -x["points"])
    return out[:limit]

# ---------- Reddit (공개 RSS) ----------
# RSS 에는 stickied 플래그가 없으므로, 반복되는 운영(모더레이터) 고정글을 제목·작성자로 걸러낸다.
REDDIT_NOISE = ["self-promotion", "who's hiring", "who is hiring", "monthly", "weekly",
                "simple questions", "discussion thread", "megathread", "rules of"]

def _is_reddit_noise(title, author):
    if author.lower().endswith("automoderator"):
        return True
    tl = title.lower()
    return any(k in tl for k in REDDIT_NOISE)

def _get_feed(url, timeout=20):
    """피드 1회 요청 → (상태, 본문). 네트워크 오류·타임아웃은 상태 0."""
    try:
        req = urllib.request.Request(url, headers=RSS_HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return 0, ""

def _fetch_rss(url, retries=3):
    """429(rate limit)면 잠시 쉬었다가 재시도. 실패하면 빈 문자열."""
    for attempt in range(retries):
        status, body = _get_feed(url)
        if status == 200:
            return body
        if status == 429 and attempt < retries - 1:
            time.sleep(5 * (attempt + 1))
            continue
        return ""
    return ""

def _parse_reddit_feed(body, sub):
    items = []
    for ent in re.split(r"<entry>", body)[1:]:
        t = re.search(r"<title>(.*?)</title>", ent, re.S)
        l = re.search(r'<link[^>]*href="([^"]+)"', ent)
        a = re.search(r"<author>.*?<name>(.*?)</name>", ent, re.S)
        if not t or not l:
            continue
        title = ih.unescape(t.group(1).strip())
        # Atom author name 은 "/u/이름" 형식 → 접두어 제거해 순수 사용자명만 저장
        author = re.sub(r"^/?u/", "", ih.unescape(a.group(1).strip())) if a else ""
        if _is_reddit_noise(title, author):  # 고정 운영글 제외
            continue
        items.append({"title": title, "sub": sub, "author": author,
                      "url": ih.unescape(l.group(1).strip())})
    return items

def reddit(limit=6):
    """RSS hot 피드 사용. RSS 에는 점수·댓글 수가 없으므로 reddit 의 hot 순서를 인기순위로 쓴다.
    Reddit 은 CI 공유 IP 를 강하게 rate-limit 해서 일부 서브레딧이 막힐 수 있으므로,
    성공한 피드들을 라운드로빈으로 섞어 빈 슬롯을 채운다(한쪽만 살아도 limit 까지 채움)."""
    subs = ["LocalLLaMA", "MachineLearning"]
    per_sub_items = []
    for i, sub in enumerate(subs):
        if i:
            time.sleep(10)  # 연속 요청 시 429 회피 (RSS rate limit 이 엄격함)
        body = _fetch_rss(f"https://www.reddit.com/r/{sub}/hot/.rss?limit=12")
        if body:
            per_sub_items.append(_parse_reddit_feed(body, sub))
    # 라운드로빈 병합: [L0, M0, L1, M1, ...] — 한 서브가 비어도 다른 서브가 채움
    out = []
    for col in range(max((len(x) for x in per_sub_items), default=0)):
        for items in per_sub_items:
            if col < len(items):
                out.append(items[col])
                if len(out) >= limit:
                    return out
    return out

# ---------- YouTube (AI/테크 유명 채널 최신 영상, 공개 RSS) ----------
# (channel_id, 표시이름, @handle). 새 채널은 youtube.com/@handle 페이지의
# <link rel="canonical" href=".../channel/UC..."> 로 ID 를 확인해 추가한다.
# 2026-11-16 전수 확인: 처음 넣을 때(2026-06) 13개 중 8개가 엉뚱한 채널 ID 였다
# (Karpathy→3Blue1Brown, Fireship→Beyond Fireship, Lex Fridman→Lex Clips, sentdex→Jabrils,
#  ColdFusion→ColdFusion Music, Yannic→Yannic Out Of Distribution, 조코딩→멋쟁이사자처럼,
#  빵형의 개발도상국→AI프렌즈). 표시이름과 실제 채널이 어긋나지 않게 handle 을 함께 적어 둔다.
YT_CHANNELS = [
    # 해외 AI/테크 채널
    ("UCbfYPyITQ-7l4upoX8nvctg", "Two Minute Papers", "@TwoMinutePapers"),
    ("UCNJ1Ymd5yFuUPtn21xtRbbw", "AI Explained", "@aiexplained-official"),
    ("UCZHmQk67mSJgfCCTn7xBfew", "Yannic Kilcher", "@YannicKilcher"),
    ("UCXUPKJO5MZQN11PqgIvyuvQ", "Andrej Karpathy", "@AndrejKarpathy"),
    ("UCsBjURrPoezykLs9EqgamOA", "Fireship", "@Fireship"),
    ("UCSHZKyawb77ixDdsGog4iWA", "Lex Fridman", "@lexfridman"),
    ("UCfzlCWGWYyIQ0aLC5w48gBQ", "sentdex", "@sentdex"),
    ("UCIgnGlGkVRhd4qNFcEwLL4A", "AI Search", "@theAIsearch"),
    ("UC4QZ_LsYcvcq7qOsOhpAX4A", "ColdFusion", "@ColdFusion"),
    # 한국 AI/테크 채널
    ("UCeN2YeJcBCRJoXgzF_OU3qw", "안될공학", "@unrealtech"),
    ("UCQNE2JmbasNYbjGAcuBiRRg", "조코딩", "@jocoding"),
    ("UCt2wAAXgm87ACiQnDHQEW6Q", "테디노트", "@teddynote"),
    ("UC9PB9nKYqKEx_N3KM-JVTpg", "빵형의 개발도상국", "@bbanghyong"),
]

# YouTube 채널 RSS 는 멀쩡한 채널에도 404·5xx 를 자주 돌려준다(2026-10 말부터 심해짐 —
# 같은 피드가 200 → 404 → 200 으로 오간다). 그래서 실패한 채널만 모아 몇 번 더 돌린다.
# 라운드 사이를 벌려 YouTube 쪽 일시 장애가 지나가길 기다리고, 총 대기는 이 합계로 묶인다.
YT_RETRY_STATUSES = {0, 404, 429} | set(range(500, 600))   # 0 = 네트워크 오류/타임아웃
YT_ROUND_WAITS = (5, 15, 30, 45)   # 1차 시도 뒤 재시도 라운드마다 쉬는 초 (총 95초 이내)
YT_CARRY_DAYS = 7          # 오늘 못 받은 채널은 이 기간 안에 받아 둔 영상을 대신 싣는다
YT_ZERO_STREAK_ALERT = 3   # 모든 채널이 실패한 날이 이만큼 이어지면 사람에게 알린다(피드 형식·주소 변경 의심)

def _parse_yt_latest(body, cid, name, today):
    """채널 피드에서 최신 영상 1개. 형식이 달라 못 읽으면 None."""
    ent = re.split(r"<entry>", body)[1:2]  # 최신 1개
    if not ent:
        return None
    ent = ent[0]
    t = re.search(r"<title>(.*?)</title>", ent, re.S)
    l = re.search(r'<link[^>]*rel="alternate"[^>]*href="([^"]+)"', ent) or \
        re.search(r'<link[^>]*href="([^"]+)"', ent)
    p = re.search(r"<published>(.*?)</published>", ent)
    d = re.search(r"<media:description>(.*?)</media:description>", ent, re.S)
    if not t or not l:
        return None
    desc = ih.unescape(re.sub(r"\s+", " ", d.group(1)).strip())[:280] if d else ""
    return {"title": ih.unescape(t.group(1).strip()), "channel": name, "channel_id": cid,
            "url": ih.unescape(l.group(1).strip()),
            "published": p.group(1)[:10] if p else "", "desc": desc,
            "fetched": today}   # 실제로 받아 온 날 — 이월 기간 판단용

def _fetch_yt_channels(today, waits=YT_ROUND_WAITS):
    """채널마다 독립적으로 받아 온다 → ({channel_id: 영상}, {channel_id: 마지막 실패 사유}).
    1차로 전 채널을 돌고, 재시도할 만한 실패(404·429·5xx·네트워크)만 라운드마다 다시 시도한다."""
    got, why = {}, {}
    pending = [(cid, name) for cid, name, _ in YT_CHANNELS]
    for rnd in range(len(waits) + 1):
        if rnd:
            if not pending:
                break
            time.sleep(waits[rnd - 1])
        retry = []
        for cid, name in pending:
            status, body = _get_feed(f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}")
            if status == 200:
                vid = _parse_yt_latest(body, cid, name, today)
                if vid:
                    got[cid] = vid
                    why.pop(cid, None)
                else:
                    why[cid] = "형식"   # 200 인데 못 읽음 — 재시도해도 같으므로 접는다
                continue
            why[cid] = str(status or "네트워크")
            if status in YT_RETRY_STATUSES:
                retry.append((cid, name))
        pending = retry
    return got, why

def _days_between(a, b):
    try:
        return (datetime.date.fromisoformat(b) - datetime.date.fromisoformat(a)).days
    except (TypeError, ValueError):
        return None

def merge_youtube(got, prev, today, limit=9):
    """오늘 받은 영상 + 오늘 못 받은 채널의 이전 영상(carried 표시)을 합친다.
    - 이전 영상은 지금 설정된 channel_id 로 받아 둔 것만 쓴다(옛 엉뚱한 ID 영상은 버림).
    - 일부라도 받았으면 YT_CARRY_DAYS 안에 받아 둔 것만 이월하고,
      하나도 못 받은 날엔 기간과 무관하게 이전 영상을 그대로 지킨다(빈 섹션 대신)."""
    known = {cid for cid, _, _ in YT_CHANNELS}
    prev_by = {}
    for v in prev or []:
        cid = v.get("channel_id") if isinstance(v, dict) else None
        if cid in known and cid not in got and v.get("url"):
            if cid not in prev_by or v.get("published", "") > prev_by[cid].get("published", ""):
                prev_by[cid] = v
    carried = []
    for cid, v in prev_by.items():
        age = _days_between(v.get("fetched"), today)
        if got and (age is None or age > YT_CARRY_DAYS):
            continue
        carried.append({**v, "carried": True})
    vids = list(got.values()) + carried
    vids.sort(key=lambda v: v.get("published", ""), reverse=True)
    return vids[:limit]

def youtube(prev=None, today=None, limit=9):
    """각 채널의 최신 영상 1개씩 모아 게시일 기준 최신순으로 정렬해 상위 N개.
    → (영상 목록, 오늘 실제로 받아 온 채널 수)."""
    today = today or datetime.date.today().isoformat()
    got, why = _fetch_yt_channels(today)
    vids = merge_youtube(got, prev, today, limit)
    names = {cid: name for cid, name, _ in YT_CHANNELS}
    fails = ", ".join(f"{names[c]}({r})" for c, r in why.items())
    print(f"  [YouTube] 채널 {len(got)}/{len(YT_CHANNELS)} 수신"
          + (f" · 실패: {fails}" if fails else "")
          + f" · 이월 {sum(1 for v in vids if v.get('carried'))}건")
    return vids, len(got)

# ---------- Social (HN 내 X/Twitter 링크) ----------
def social_from_hn(limit=3):
    data = _hn_front_page()
    out = []
    for h in data.get("hits", []):
        url = h.get("url") or ""
        if ("twitter.com" in url or "x.com" in url) and h.get("points", 0) > 50:
            handle = re.search(r"(?:twitter|x)\.com/([^/]+)/", url + "/")
            out.append({"title": h.get("title", ""),
                        "handle": "@" + handle.group(1) if handle else "@x",
                        "url": url,
                        "note": f"HN {h.get('points',0)}pts · {h.get('num_comments',0)} 댓글"})
    return out[:limit]

DATA_PATH = ROOT / "data" / "data.json"
HEALTH_PATH = ROOT / "data" / "health.json"

def _load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def emit_alert(message):
    """워크플로의 health 잡이 읽도록 GITHUB_OUTPUT 에 기록한다 (로컬 실행 시엔 출력만)."""
    if not message:
        return
    print(f"alert={message}")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"alert={message}\n")

def record_youtube_health(channels_ok):
    """모든 YouTube 채널이 실패한 연속 일수를 data/health.json 에 남기고(다른 키는 보존),
    며칠째 이어지면 alert 문구를 돌려준다. 하루이틀 실패는 일시 장애로 보고 알리지 않는다."""
    health = _load_json(HEALTH_PATH)
    streak = 0 if channels_ok else int(health.get("youtube_zero_streak", 0)) + 1
    health["youtube_zero_streak"] = streak
    HEALTH_PATH.write_text(json.dumps(health, ensure_ascii=False, indent=2), encoding="utf-8")
    if streak >= YT_ZERO_STREAK_ALERT:
        return (f"YouTube RSS 가 {streak}일 연속 모든 채널 실패 — 피드 주소·형식 변경 의심, "
                "Actions 로그의 '[YouTube]' 줄과 collect.py YT_CHANNELS 확인 필요")
    return ""

def main():
    now = datetime.datetime.now(datetime.timezone.utc)
    kst = now + datetime.timedelta(hours=9)
    wd = ["월", "화", "수", "목", "금", "토", "일"][kst.weekday()]
    prev = _load_json(DATA_PATH)   # 덮어쓰기 전에 — 오늘 못 받은 YouTube 채널은 이전 영상으로 채운다
    yt, yt_ok = youtube(prev.get("youtube"), today=kst.date().isoformat())
    data = {
        "generated_at": now.isoformat(),
        "date_label": f"{kst.year}년 {kst.month}월 {kst.day}일 ({wd})",
        "github_trending": github_trending(),
        "hackernews": hacker_news(),
        "reddit": reddit(),
        "youtube": yt,
        "social": social_from_hn(),
    }
    (ROOT / "data").mkdir(exist_ok=True)
    DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"수집 완료: GitHub {len(data['github_trending'])} · "
          f"HN {len(data['hackernews'])} · Reddit {len(data['reddit'])} · "
          f"YouTube {len(data['youtube'])}(새로 받은 채널 {yt_ok}) · SNS {len(data['social'])}")
    emit_alert(record_youtube_health(yt_ok))

if __name__ == "__main__":
    main()
