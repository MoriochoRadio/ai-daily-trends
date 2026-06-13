#!/usr/bin/env python3
"""매일 AI 트렌드를 수집해 data/data.json 으로 저장한다.
소스: GitHub Trending(스크레이핑), Hacker News(Algolia API), Reddit(공개 JSON), 화제의 SNS(HN의 X 링크).
GitHub Actions 러너처럼 외부 네트워크가 열린 환경에서 실행하는 것을 전제로 한다.
"""
import json, re, html as ih, urllib.request, datetime, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
UA = {"User-Agent": "Mozilla/5.0 (AI-Daily-Trends bot)"}

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

# ---------- Reddit ----------
def reddit(limit=6):
    out = []
    for sub in ["LocalLLaMA", "MachineLearning"]:
        try:
            d = json.load(fetch(f"https://www.reddit.com/r/{sub}/hot.json?limit=10"))
        except Exception:
            continue
        for c in d["data"]["children"]:
            p = c["data"]
            if p.get("stickied"):
                continue
            out.append({"title": p["title"], "sub": sub, "score": p.get("score", 0),
                        "comments": p.get("num_comments", 0),
                        "url": "https://www.reddit.com" + p["permalink"]})
    out.sort(key=lambda x: -x["score"])
    return out[:limit]

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
        "social": social_from_hn(),
    }
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "data.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"수집 완료: GitHub {len(data['github_trending'])} · "
          f"HN {len(data['hackernews'])} · Reddit {len(data['reddit'])} · SNS {len(data['social'])}")

if __name__ == "__main__":
    main()
