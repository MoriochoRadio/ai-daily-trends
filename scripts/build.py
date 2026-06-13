#!/usr/bin/env python3
"""data/data.json 을 읽어 다크 + Bento Grid 디자인의 index.html 을 생성한다.
각 항목에는 summarize.py 가 붙인 한국어 요약(summary_ko)이 있으면 함께 보여준다.
디자인 시스템 출처: ui-ux-pro-max-skill (Bento Grid Showcase / Space Grotesk + DM Sans)."""
import json, html, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = json.loads((ROOT / "data" / "data.json").read_text(encoding="utf-8"))

def esc(s):
    return html.escape(str(s), quote=True)

LANG_COLOR = {"Python": "#3776AB", "TypeScript": "#3178C6", "JavaScript": "#F7DF1E",
    "Shell": "#89E051", "Go": "#00ADD8", "Rust": "#DEA584", "Swift": "#F05138",
    "C": "#555555", "Jupyter Notebook": "#DA5B0B"}

def lang_dot(lang):
    if not lang:
        return ""
    c = LANG_COLOR.get(lang, "#94A3B8")
    return '<span class="lang"><span class="dot" style="background:%s"></span>%s</span>' % (c, esc(lang))

def stars_label(v):
    s = str(v).replace(",", "")
    return "{:,}".format(int(s)) if s.isdigit() else esc(v)

YT_SVG = ('<svg viewBox="0 0 24 24"><path fill="currentColor" d="M21.6 7.2a2.5 2.5 0 0 0-1.7-1.8'
          'C18.2 5 12 5 12 5s-6.2 0-7.9.4A2.5 2.5 0 0 0 2.4 7.2 26 26 0 0 0 2 12a26 26 0 0 0 .4 4.8'
          ' 2.5 2.5 0 0 0 1.7 1.8C5.8 19 12 19 12 19s6.2 0 7.9-.4a2.5 2.5 0 0 0 1.7-1.8A26 26 0 0 0 22 12'
          'a26 26 0 0 0-.4-4.8z"/><path fill="#272F42" d="M10 15.2V8.8L15.5 12z"/></svg>')

# ---------- GitHub Trending ----------
gh_rows = []
for i, r in enumerate(DATA["github_trending"], 1):
    desc = r.get("summary_ko") or r.get("desc", "")
    gh_rows.append(
        '<a class="repo" href="%s" target="_blank" rel="noopener">'
        '<div class="repo-rank">%02d</div><div class="repo-body">'
        '<div class="repo-name">%s<svg class="ext" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M7 17 17 7M9 7h8v8"/></svg></div>'
        '<div class="repo-desc">%s</div>'
        '<div class="repo-meta">%s<span class="stars"><svg viewBox="0 0 24 24" fill="currentColor"><path d="m12 2 2.9 6.3 6.8.6-5.1 4.5 1.5 6.7L12 17l-6 3.6 1.5-6.7L2.4 9.4l6.8-.6z"/></svg>%s/일</span></div>'
        '</div></a>'
        % (esc(r["url"]), i, esc(r["repo"]), esc(desc),
           lang_dot(r.get("lang", "")), stars_label(r.get("stars_today", ""))))

# ---------- Hacker News ----------
hn_rows = []
for r in DATA["hackernews"]:
    summ = r.get("summary_ko", "")
    hn_rows.append(
        '<a class="post" href="%s" target="_blank" rel="noopener">'
        '<div class="post-title">%s</div>'
        '%s'
        '<div class="post-meta"><span class="pts">&#9650; %s</span><span class="cmt">%s 댓글</span><span class="hn">HN</span></div>'
        '</a>' % (esc(r["url"]), esc(r["title"]),
                  ('<div class="post-summary">%s</div>' % esc(summ)) if summ else "",
                  r.get("points", 0), r.get("comments", 0)))

# ---------- Reddit ----------
rd_rows = []
for r in DATA.get("reddit", []):
    summ = r.get("summary_ko", "")
    if "score" in r:
        meta = '<span class="up">&#9650; %s</span><span>%s 댓글</span>' % (r.get("score", 0), r.get("comments", 0))
    else:
        author = esc(r.get("author", "")) if r.get("author") else "reddit"
        meta = '<span class="up">u/%s</span><span>커뮤니티 화제글</span>' % author
    rd_rows.append(
        '<a class="rd" href="%s" target="_blank" rel="noopener">'
        '<div class="rd-sub">r/%s</div><div class="rd-title">%s</div>'
        '%s'
        '<div class="rd-meta">%s</div></a>'
        % (esc(r["url"]), esc(r.get("sub", "")), esc(r["title"]),
           ('<div class="rd-summary">%s</div>' % esc(summ)) if summ else "", meta))

reddit_card = ""
if rd_rows:
    reddit_card = (
        '<div class="card col-social" id="reddit"><div class="card-head">'
        '<h2><svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="10"/></svg>Reddit · 커뮤니티 화제</h2>'
        '<span class="tag">r/LocalLLaMA · r/MachineLearning</span></div>'
        '<div class="social-grid">%s</div></div>' % "".join(rd_rows))

# ---------- YouTube ----------
yt_rows = []
for r in DATA.get("youtube", []):
    summ = r.get("summary_ko", "")
    yt_rows.append(
        '<a class="yt" href="%s" target="_blank" rel="noopener">'
        '<div class="yt-channel">%s%s</div>'
        '<div class="yt-title">%s</div>'
        '%s'
        '<div class="yt-date">%s</div></a>'
        % (esc(r["url"]), YT_SVG, esc(r["channel"]), esc(r["title"]),
           ('<div class="yt-summary">%s</div>' % esc(summ)) if summ else "",
           esc(r.get("published", ""))))

youtube_card = ""
if yt_rows:
    youtube_card = (
        '<div class="card col-social" id="youtube"><div class="card-head">'
        '<h2>%s화제의 AI 유튜브</h2>'
        '<span class="tag">AI · 테크 채널 새 영상</span></div>'
        '<div class="yt-grid">%s</div></div>' % (YT_SVG, "".join(yt_rows)))

# ---------- Social (X) ----------
soc_rows = []
for r in DATA["social"]:
    summ = r.get("summary_ko", "")
    soc_rows.append(
        '<a class="social" href="%s" target="_blank" rel="noopener">'
        '<div class="social-handle">%s</div><div class="social-title">%s</div>'
        '%s'
        '<div class="social-note">%s</div></a>'
        % (esc(r["url"]), esc(r["handle"]), esc(r["title"]),
           ('<div class="social-summary">%s</div>' % esc(summ)) if summ else "",
           esc(r.get("note", ""))))

total_repos = len(DATA["github_trending"])
total_hn = len(DATA["hackernews"])
total_yt = len(DATA.get("youtube", []))
star_vals = [int(str(r["stars_today"]).replace(",", "")) for r in DATA["github_trending"]
             if str(r["stars_today"]).replace(",", "").isdigit()]
top_stars = max(star_vals) if star_vals else 0

CSS = """
:root{--bg:#0F172A;--surface:#1E293B;--muted:#272F42;--border:#334155;--fg:#F8FAFC;--fg-dim:#94A3B8;--accent:#22C55E;--accent-soft:rgba(34,197,94,.12);--radius:20px}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{background:var(--bg);color:var(--fg);font-family:'DM Sans',system-ui,sans-serif;line-height:1.5;-webkit-font-smoothing:antialiased;background-image:radial-gradient(900px 500px at 85% -10%,rgba(34,197,94,.10),transparent 60%),radial-gradient(700px 500px at 0% 0%,rgba(56,116,182,.10),transparent 55%);background-attachment:fixed}
h1,h2,h3{font-family:'Space Grotesk',sans-serif}
a{color:inherit;text-decoration:none;cursor:pointer}
.wrap{max-width:1180px;margin:0 auto;padding:0 24px}
header{position:sticky;top:0;z-index:20;backdrop-filter:blur(12px);background:rgba(15,23,42,.72);border-bottom:1px solid var(--border)}
.nav{display:flex;align-items:center;justify-content:space-between;height:64px}
.brand{display:flex;align-items:center;gap:10px;font-family:'Space Grotesk';font-weight:700;letter-spacing:-.02em}
.brand .mark{width:30px;height:30px;border-radius:9px;background:var(--accent);display:grid;place-items:center;color:#06140A;box-shadow:0 0 24px rgba(34,197,94,.5)}
.brand .mark svg{width:18px;height:18px}
.nav-links{display:flex;gap:24px;font-size:14px;color:var(--fg-dim)}
.nav-links a{transition:color .2s}
.nav-links a:hover{color:var(--accent)}
@media(max-width:780px){.nav-links{display:none}}
.hero{padding:88px 0 56px}
.badge{display:inline-flex;align-items:center;gap:8px;font-size:13px;color:var(--accent);background:var(--accent-soft);border:1px solid rgba(34,197,94,.35);padding:6px 14px;border-radius:999px;font-weight:500}
.badge .live{width:8px;height:8px;border-radius:50%;background:var(--accent);animation:pulse 2s infinite}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(34,197,94,.6)}70%{box-shadow:0 0 0 10px rgba(34,197,94,0)}100%{box-shadow:0 0 0 0 rgba(34,197,94,0)}}
.hero h1{font-size:clamp(2.8rem,8vw,6.2rem);font-weight:700;letter-spacing:-.045em;line-height:.98;margin:26px 0 18px}
.hero h1 .g{background:linear-gradient(120deg,#22C55E,#7DD3FC);-webkit-background-clip:text;background-clip:text;color:transparent}
.hero p{font-size:clamp(1rem,2.2vw,1.2rem);color:var(--fg-dim);max-width:600px}
.hero-stats{display:flex;gap:34px;margin-top:38px;flex-wrap:wrap}
.stat .n{font-family:'Space Grotesk';font-size:2.1rem;font-weight:700;letter-spacing:-.03em}
.stat .l{font-size:13px;color:var(--fg-dim)}
.stat .n .accent{color:var(--accent)}
.bento{display:grid;grid-template-columns:repeat(12,1fr);gap:18px;padding-bottom:80px}
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:26px;overflow:hidden;transition:border-color .25s}
.card:hover{border-color:rgba(34,197,94,.4)}
.card-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:18px;gap:10px}
.card-head h2{font-size:1.15rem;font-weight:600;letter-spacing:-.01em;display:flex;align-items:center;gap:10px}
.card-head h2 svg{width:20px;height:20px;color:var(--accent)}
.tag{font-size:11px;color:var(--fg-dim);border:1px solid var(--border);padding:3px 9px;border-radius:999px;white-space:nowrap}
.col-github{grid-column:span 7}
.col-side{grid-column:span 5}
.col-social{grid-column:span 12}
@media(max-width:880px){.col-github,.col-side,.col-social{grid-column:span 12}}
.repo{display:flex;gap:16px;padding:15px 12px;border-radius:14px;transition:background .2s;align-items:flex-start}
.repo:hover{background:var(--muted)}
.repo:hover .repo-name{color:var(--accent)}
.repo+.repo{border-top:1px solid rgba(51,65,85,.5)}
.repo-rank{font-family:'Space Grotesk';font-weight:700;color:var(--fg-dim);font-size:.95rem;min-width:26px;padding-top:2px}
.repo-body{flex:1;min-width:0}
.repo-name{font-family:'Space Grotesk';font-weight:600;display:flex;align-items:center;gap:6px;transition:color .2s}
.repo-name .ext{width:13px;height:13px;opacity:0;transition:opacity .2s;color:var(--accent)}
.repo:hover .repo-name .ext{opacity:1}
.repo-desc{font-size:13.5px;color:var(--fg-dim);margin:5px 0 9px;line-height:1.55}
.repo-meta{display:flex;align-items:center;gap:16px;font-size:12.5px;color:var(--fg-dim)}
.lang{display:inline-flex;align-items:center;gap:6px}
.lang .dot{width:10px;height:10px;border-radius:50%}
.stars{display:inline-flex;align-items:center;gap:5px;color:var(--accent);font-weight:500}
.stars svg{width:13px;height:13px}
.post{display:block;padding:14px 12px;border-radius:14px;transition:background .2s}
.post:hover{background:var(--muted)}
.post:hover .post-title{color:var(--accent)}
.post+.post{border-top:1px solid rgba(51,65,85,.5)}
.post-title{font-weight:500;font-size:14.5px;transition:color .2s;line-height:1.4}
.post-summary{font-size:12.5px;color:var(--fg-dim);margin-top:6px;line-height:1.5}
.post-meta{display:flex;gap:14px;font-size:12px;color:var(--fg-dim);margin-top:8px}
.post-meta .pts{color:#FB923C;font-weight:500}
.post-meta .hn{margin-left:auto;color:#FB923C;border:1px solid rgba(251,146,60,.4);border-radius:6px;padding:0 7px}
.social-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
@media(max-width:760px){.social-grid{grid-template-columns:1fr}}
.social,.rd{display:block;background:var(--muted);border:1px solid var(--border);border-radius:16px;padding:20px;transition:transform .25s,border-color .25s}
.social:hover,.rd:hover{transform:translateY(-4px);border-color:rgba(34,197,94,.45)}
.social:hover .social-title,.rd:hover .rd-title{color:var(--accent)}
.social-handle{color:var(--accent);font-weight:600;font-family:'Space Grotesk';font-size:14px}
.social-title{font-weight:500;margin:10px 0 8px;line-height:1.35;transition:color .2s}
.social-summary{font-size:12.5px;color:var(--fg-dim);line-height:1.5;margin-bottom:8px}
.social-note{font-size:12px;color:var(--fg-dim);opacity:.85}
.rd-sub{color:#FB923C;font-weight:600;font-family:'Space Grotesk';font-size:13px}
.rd-title{font-weight:500;margin:9px 0 8px;line-height:1.35;font-size:14.5px;transition:color .2s}
.rd-summary{font-size:12.5px;color:var(--fg-dim);line-height:1.5;margin-bottom:10px}
.rd-meta{display:flex;gap:14px;font-size:12px;color:var(--fg-dim)}
.rd-meta .up{color:var(--accent);font-weight:500}
.yt-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
@media(max-width:760px){.yt-grid{grid-template-columns:1fr}}
.yt{display:block;background:var(--muted);border:1px solid var(--border);border-radius:16px;padding:20px;transition:transform .25s,border-color .25s}
.yt:hover{transform:translateY(-4px);border-color:rgba(248,44,54,.5)}
.yt:hover .yt-title{color:#FB6168}
.yt-channel{display:inline-flex;align-items:center;gap:7px;color:#FB2C36;font-weight:600;font-family:'Space Grotesk';font-size:13px}
.yt-channel svg{width:18px;height:18px}
.yt-title{font-weight:600;margin:11px 0 8px;line-height:1.35;font-size:14.5px;transition:color .2s}
.yt-summary{font-size:12.5px;color:var(--fg-dim);line-height:1.5;margin-bottom:11px}
.yt-date{font-size:11.5px;color:var(--fg-dim);font-family:'Space Grotesk'}
.card-head h2 .yt-h{width:22px;height:22px;color:#FB2C36}
footer{border-top:1px solid var(--border);padding:34px 0 60px;color:var(--fg-dim);font-size:13.5px}
footer .wrap{display:flex;justify-content:space-between;gap:18px;flex-wrap:wrap;align-items:center}
footer a{color:var(--accent)}
@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
"""

HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI 데일리 트렌드 · __DATE__</title>
<meta name="description" content="매일 자동 업데이트되는 AI/IT 브리핑 — GitHub Trending, Hacker News, Reddit, AI 유튜브, 화제의 SNS를 한국어 요약과 함께 한눈에.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>__CSS__</style>
</head>
<body>
<header><div class="wrap nav">
  <div class="brand"><span class="mark"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M12 3v18M3 12h18M6 6l12 12M18 6 6 18"/></svg></span>AI 데일리 트렌드</div>
  <nav class="nav-links"><a href="#github">GitHub</a><a href="#hn">Hacker News</a><a href="#reddit">Reddit</a><a href="#youtube">YouTube</a><a href="#social">SNS</a></nav>
</div></header>
<main class="wrap">
  <section class="hero">
    <span class="badge"><span class="live"></span>매일 자동 업데이트 · __DATE__</span>
    <h1>오늘의 <span class="g">AI 트렌드</span><br>한 화면에서.</h1>
    <p>GitHub에서 가장 뜨거운 저장소, Hacker News·Reddit의 핵심 논의, AI 유튜버들의 새 영상, 화제가 된 SNS 글까지 — 매일 자동으로 모아 <strong style="color:var(--fg)">한국어 핵심 요약</strong>과 함께 정리합니다. 따로 찾아다니지 않아도 AI·IT 흐름이 한눈에.</p>
    <div class="hero-stats">
      <div class="stat"><div class="n">__NREPOS__<span class="accent">+</span></div><div class="l">트렌딩 저장소</div></div>
      <div class="stat"><div class="n">__NHN__</div><div class="l">HN 핵심 글</div></div>
      <div class="stat"><div class="n">__NYT__</div><div class="l">새 유튜브 영상</div></div>
      <div class="stat"><div class="n accent">__TOPSTARS__</div><div class="l">최다 일일 ★</div></div>
    </div>
  </section>
  <section class="bento">
    <div class="card col-github" id="github"><div class="card-head">
      <h2><svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2a10 10 0 0 0-3.16 19.49c.5.09.68-.22.68-.48v-1.7c-2.78.6-3.37-1.34-3.37-1.34-.45-1.16-1.1-1.47-1.1-1.47-.9-.62.07-.6.07-.6 1 .07 1.53 1.03 1.53 1.03.9 1.52 2.34 1.08 2.91.83.09-.65.35-1.09.63-1.34-2.22-.25-4.55-1.11-4.55-4.94 0-1.09.39-1.98 1.03-2.68-.1-.25-.45-1.27.1-2.65 0 0 .84-.27 2.75 1.02a9.5 9.5 0 0 1 5 0c1.91-1.29 2.75-1.02 2.75-1.02.55 1.38.2 2.4.1 2.65.64.7 1.03 1.59 1.03 2.68 0 3.84-2.34 4.69-4.57 4.94.36.31.68.92.68 1.85v2.74c0 .27.18.58.69.48A10 10 0 0 0 12 2z"/></svg>GitHub Trending</h2>
      <span class="tag">AI · ML · 에이전트</span></div>
      <div class="repo-list">__GH__</div>
    </div>
    <div class="card col-side" id="hn"><div class="card-head">
      <h2><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 5h18M3 12h18M3 19h12"/></svg>Hacker News</h2>
      <span class="tag">프론트페이지</span></div>
      <div class="post-list">__HN__</div>
    </div>
    __REDDIT__
    __YOUTUBE__
    <div class="card col-social" id="social"><div class="card-head">
      <h2><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 11.5a8.38 8.38 0 0 1-9 8.5 8.5 8.5 0 0 1-3.8-.9L3 21l1.9-5.2A8.5 8.5 0 0 1 21 11.5z"/></svg>화제의 SNS · 인플루언서</h2>
      <span class="tag">X / 커뮤니티</span></div>
      <div class="social-grid">__SOCIAL__</div>
    </div>
  </section>
</main>
<footer><div class="wrap">
  <div>마지막 업데이트: __DATE__ · 데이터: GitHub, Hacker News, Reddit, YouTube, X · 요약: GitHub Models</div>
  <div>디자인 시스템: <a href="https://github.com/nextlevelbuilder/ui-ux-pro-max-skill" target="_blank" rel="noopener">UI UX Pro Max</a> · 매일 자동 갱신</div>
</div></footer>
</body>
</html>"""

out_html = HTML
for k, v in [("__CSS__", CSS), ("__DATE__", esc(DATA["date_label"])),
             ("__NREPOS__", str(total_repos)), ("__NHN__", str(total_hn)),
             ("__NYT__", str(total_yt)), ("__TOPSTARS__", "{:,}".format(top_stars)),
             ("__GH__", "".join(gh_rows)), ("__HN__", "".join(hn_rows)),
             ("__REDDIT__", reddit_card), ("__YOUTUBE__", youtube_card),
             ("__SOCIAL__", "".join(soc_rows))]:
    out_html = out_html.replace(k, v)

(ROOT / "index.html").write_text(out_html, encoding="utf-8")
print("Built index.html (%d bytes)" % len(out_html))
