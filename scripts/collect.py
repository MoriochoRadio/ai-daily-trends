#!/usr/bin/env python3
"""매일 AI 트렌드를 수집해 data/data.json 으로 저장한다.
소스: GitHub Trending(스크레이핑), Hacker News(Algolia API), Reddit(공개 RSS), 화제의 SNS(HN의 X 링크).
GitHub Actions 러너처럼 외부 네트워크가 열린 환경에서 실행하는 것을 전제로 한다.
"""
import json, re, html as ih, urllib.request, urllib.error, time, datetime, pathlib

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
    rows.sort(key=lambda r: (not r["_ai"], -r["stars_today"]))
    for r in rows:
        r.pop("_ai", None)
    return rows[:limit]

# ---------- Hacker News ----------
def hacker_news(limit=8):
    data = json.load(fetch("https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=60"))
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

def _fetch_rss(url, retries=3):
    """429(rate limit)면 잠시 쉬었다가 재시도. 실패하면 빈 문자열."""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=RSS_HEADERS)
            return urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                time.sleep(5 * (attempt + 1))
                continue
            return ""
        except Exception:
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
# 채널 ID 는 youtube.com/@handle 페이지에서 확인. 새 채널을 넣으려면 (channel_id, 표시이름) 추가.
YT_CHANNELS = [
    # 해외 AI/테크 채널
    ("UCbfYPyITQ-7l4upoX8nvctg", "Two Minute Papers"),
    ("UCNJ1Ymd5yFuUPtn21xtRbbw", "AI Explained"),
    ("UCHmD-oSpV0sNfAUnpYpj8KA", "Yannic Kilcher"),
    ("UCYO_jab_esuFRV4b17AJtAw", "Andrej Karpathy"),
    ("UC2Xd-TjJByJyK2w1zNwY0zQ", "Fireship"),
    ("UCJIfeSCssxSC_Dhc5s7woww", "Lex Fridman"),
    ("UCQALLeQPoZdZC4JNUboVEUg", "sentdex"),
    ("UCIgnGlGkVRhd4qNFcEwLL4A", "AI Search"),
    ("UCGkpFfEMF0eMJlh9xXj2lMw", "ColdFusion"),
    # 한국 AI/테크 채널
    ("UCeN2YeJcBCRJoXgzF_OU3qw", "안될공학"),
    ("UCYaDkwVaOhuoe_LuFr3lWkA", "조코딩"),
    ("UCt2wAAXgm87ACiQnDHQEW6Q", "테디노트"),
    ("UC2L1DgDMD5pJ-35G47Objfw", "빵형의 개발도상국"),
]

def youtube(limit=9):
    """각 채널의 최신 영상 1개씩 모아 게시일 기준 최신순으로 정렬해 상위 N개."""
    vids = []
    for cid, name in YT_CHANNELS:
        body = _fetch_rss(f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}")
        if not body:
            continue
        ent = re.split(r"<entry>", body)[1:2]  # 최신 1개
        if not ent:
            continue
        ent = ent[0]
        t = re.search(r"<title>(.*?)</title>", ent, re.S)
        l = re.search(r'<link[^>]*rel="alternate"[^>]*href="([^"]+)"', ent) or \
            re.search(r'<link[^>]*href="([^"]+)"', ent)
        p = re.search(r"<published>(.*?)</published>", ent)
        d = re.search(r"<media:description>(.*?)</media:description>", ent, re.S)
        if not t or not l:
            continue
        desc = ih.unescape(re.sub(r"\s+", " ", d.group(1)).strip())[:280] if d else ""
        vids.append({"title": ih.unescape(t.group(1).strip()), "channel": name,
                     "url": ih.unescape(l.group(1).strip()),
                     "published": p.group(1)[:10] if p else "", "desc": desc})
    vids.sort(key=lambda v: v["published"], reverse=True)
    return vids[:limit]

# ---------- Social (HN 내 X/Twitter 링크) ----------
def social_from_hn(limit=3):
    data = json.load(fetch("https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=60"))
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

def main():
    now = datetime.datetime.now(datetime.timezone.utc)
    kst = now + datetime.timedelta(hours=9)
    wd = ["월", "화", "수", "목", "금", "토", "일"][kst.weekday()]
    data = {
        "generated_at": now.isoformat(),
        "date_label": f"{kst.year}년 {kst.month}월 {kst.day}일 ({wd})",
        "github_trending": github_trending(),
        "hackernews": hacker_news(),
        "reddit": reddit(),
        "youtube": youtube(),
        "social": social_from_hn(),
    }
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "data.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"수집 완료: GitHub {len(data['github_trending'])} · "
          f"HN {len(data['hackernews'])} · Reddit {len(data['reddit'])} · "
          f"YouTube {len(data['youtube'])} · SNS {len(data['social'])}")

if __name__ == "__main__":
    main()
