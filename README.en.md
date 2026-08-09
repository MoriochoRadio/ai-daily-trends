<div align="center">

# 🤖 AI Daily Trends

🇰🇷 [한국어](README.md) · 🇬🇧 English

**An automated dashboard that gathers the hottest topics in AI worldwide onto a single screen every morning, with Korean summaries**

It automatically collects from GitHub Trending, Hacker News, Reddit, AI YouTube channels, and trending social posts, adds a **one-line Korean summary** to each item, and refreshes daily at 06:00 KST (Korea Standard Time).

[![Daily AI Trends](https://github.com/MoriochoRadio/ai-daily-trends/actions/workflows/daily.yml/badge.svg)](https://github.com/MoriochoRadio/ai-daily-trends/actions/workflows/daily.yml)
[![Live Site](https://img.shields.io/badge/Live-moriochoradio.github.io-22C55E?logo=githubpages&logoColor=white)](https://moriochoradio.github.io/ai-daily-trends/)
[![License: MIT](https://img.shields.io/badge/License-MIT-334155.svg)](LICENSE)

### 👉 **[See it live — moriochoradio.github.io/ai-daily-trends](https://moriochoradio.github.io/ai-daily-trends/)**

</div>

---

## ✨ Features

- **Fully automated** — collects and summarizes data, then builds and deploys the site every day with no human involvement.
- **🇰🇷 Korean titles + key summaries** — each item's title is shown translated into Korean in large type (with the original alongside in smaller type), plus a one-sentence Korean summary of "what it is and why it matters". (Free LLM — GitHub Models)
- **AI-focused curation** — keyword filters keep only AI/LLM/agent-related content.
- **🔍 Search, source filters, theme toggle** — instantly search all items by keyword (press `/` to focus), filter by source (GitHub, HN, Reddit, YouTube, social), and switch between dark/light themes (saved in the browser). A highlight at the top features today's most-starred repository, and HN items link to the article and the discussion separately. These features are **progressive enhancement with lightweight vanilla JS** — with JS disabled, all content still displays.
- **5 sources in one place** — GitHub, Hacker News, Reddit, YouTube, and X (Twitter) on a single screen. No more visiting each site separately.
- **Static site** — the build output is a single dependency-free `index.html`. Fast, and hosted for free.
- **Responsive + accessible** — works from mobile to desktop; respects `prefers-reduced-motion`, keyboard focus, and more.

## 📊 Data Sources

| Source | Collection method | Content |
|------|-----------|------|
| **GitHub Trending** | HTML scraping (daily / python / jupyter) | Today's most-starred AI repositories |
| **Hacker News** | [Algolia HN Search API](https://hn.algolia.com/api) | Key AI discussions from the front page |
| **Reddit** | Public RSS feeds (`r/LocalLLaMA`, `r/MachineLearning`) | Trending community posts |
| **YouTube** | Channel RSS feeds (curated AI/tech channels) | Latest videos from international channels (Two Minute Papers, Lex Fridman, Karpathy, Fireship, etc.) plus Korean channels (Andeul Engineering, Jocoding, TeddyNote, Bbanghyung's Developing Country) |
| **Trending Social** | X/Twitter links extracted from HN | Trending threads from influencers and researchers |

> **Korean summaries:** Every collected item gets a one-sentence Korean summary generated with [GitHub Models](https://github.com/marketplace/models) (free, `gpt-4o-mini`). It runs on Actions' `GITHUB_TOKEN` alone with no API key, and if the summarization step fails, the site still builds normally with the original text (graceful).
>
> **Reddit note:** Reddit blocks unauthenticated JSON endpoints and shared CI IPs (403/429), so collection was stabilized with browser headers + public RSS + retries/backoff. If one subreddit is blocked, round-robin merging lets the other sources fill the gap.

## 🎨 Design System

The design applies a design system that the [**UI UX Pro Max**](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) skill inferred and generated for this product (an AI trends dashboard). The original generated spec lives at [`design-system/ai-daily-trends/MASTER.md`](design-system/ai-daily-trends/MASTER.md).

| Item | Choice |
|------|------|
| **Pattern** | Bento Grid Showcase (dashboard-style modular cards — recommended by the skill as "Best for Dashboards / WCAG AA") |
| **Style** | Dark tech (Exaggerated Minimalism) |
| **Colors** | Slate dark background `#0F172A` + status green accent `#22C55E` |
| **Typography** | `Space Grotesk` (headings) + `DM Sans` (body) |

## 🏗️ How It Works

```
            ┌────────────────────── GitHub Actions (daily at 06:00 KST) ──────────────────────┐
            │                                                                                  │
  collect.py ──► summarize.py ──► data/data.json ──► build.py ──► index.html ──► Pages deploy
 (5-source collection) (Korean summaries) (collected/summarized data) (rendering) (static site) (auto publish)
```

1. **`collect.py`** — collects AI-related content from the 5 sources and saves it to `data/data.json`
2. **`summarize.py`** — adds a Korean key summary (`summary_ko`) to each item via GitHub Models
3. **`build.py`** — renders `data.json` into an `index.html` styled with the design system
4. **GitHub Actions** — runs the steps above daily, commits the results, and deploys to Pages

## 🧭 Why It's Built This Way — Technical Choices Q&A

**Q. Why a serverless static site?**
A. For a dashboard whose data changes once a day, per-request rendering is waste. Producing a single finished `index.html` at build time means zero server/DB cost, instant loading, and effectively a single point of failure: GitHub Pages.

**Q. Why GitHub Actions?**
A. Cron scheduling, the execution environment, and deployment (Pages) are all handled in one place for free, and results are committed, so the data history is tracked too. Concurrency serializes runs in case a delayed scheduled run overlaps a manual one, and transient Pages outages are absorbed by deploy retries.

**Q. Why GitHub Models (gpt-4o-mini) as the summarization LLM?**
A. It can be called with just Actions' default `GITHUB_TOKEN` (with `models: read` permission), eliminating separate API key issuance, secret management, and cost entirely. A small model is plenty for one-sentence-per-item summaries, and the design is graceful: if it fails, the site still builds with the original text.

**Q. Why only the Python standard library?**
A. RSS/JSON parsing and HTML rendering are perfectly doable with `urllib`, `re`, and `json`. Removing dependencies eliminates the install step in CI, and locally you only need Python. For a pipeline that runs every day, fewer breakable parts is the right trade.

**Q. Why no frontend framework?**
A. The content is already complete at build time, so a runtime framework has nothing to do. Extras like search, filters, and themes are layered on as progressive enhancement with lightweight vanilla JS, so all content still displays with JS disabled.

**Q. Why RSS for Reddit instead of the API?**
A. Because Reddit blocks unauthenticated JSON endpoints and shared CI IPs (403/429). Collection was stabilized with public RSS + browser headers + retries/backoff, and if one subreddit is blocked, round-robin merging lets the other sources fill the gap.

## 📁 Project Structure

```
.
├── index.html                       # Built website (auto-generated)
├── data/data.json                   # Collected data
├── scripts/
│   ├── collect.py                   # Data collection (GitHub · HN · Reddit · YouTube · social)
│   ├── summarize.py                 # Adds Korean key summaries (GitHub Models)
│   └── build.py                     # Renders data.json → index.html
├── design-system/
│   └── ai-daily-trends/MASTER.md    # Applied design system (skill output · source of truth)
└── .github/workflows/daily.yml      # Daily automated collection · build · deploy
```

## 💻 Running Locally

> All you need is Python 3.x. There are no external library dependencies.

```bash
python3 scripts/collect.py     # Collect the latest data (requires internet)
python3 scripts/summarize.py   # Add Korean summaries (optional — needs a token, see below)
python3 scripts/build.py       # Generate index.html
# Open the generated index.html in a browser
```

- **The summarization step is optional.** Without a token it's skipped automatically and the build uses the original text. To see summaries locally, log in with the [GitHub CLI](https://cli.github.com) (`gh auth login`) — `summarize.py` uses `gh auth token` automatically. Alternatively, set the `GITHUB_TOKEN` environment variable directly.
- In a network-restricted environment, skip collection and just run `python3 scripts/build.py` against the existing `data/data.json`.

## 🚀 Deployment (Already Automated)

This repository is already deployed via **GitHub Actions + GitHub Pages**.

- Data refreshes and the site redeploys automatically every day at **06:00 KST**.
- To refresh immediately: **Actions tab → Daily AI Trends → Run workflow**

To run your own fork:

1. Fork/clone the repository and push it to your GitHub
2. Set **Settings → Pages → Source** to **GitHub Actions**
3. Done — it refreshes automatically every day from then on

## 🛠️ Tech Stack

- **Language:** Python 3 (standard library only — `urllib`, `re`, `json`)
- **Frontend:** Pure HTML/CSS + lightweight vanilla JS (generated at build time · no external runtime dependencies · search/filters/theme as progressive enhancement)
- **Summarization LLM:** [GitHub Models](https://github.com/marketplace/models) `gpt-4o-mini` (free, no key required)
- **CI/CD:** GitHub Actions
- **Hosting:** GitHub Pages
- **Design:** [UI UX Pro Max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) skill

> **Note:** The UI UX Pro Max skill (`.claude/`) is a third-party tool and is not included in the repository (.gitignore). To regenerate the design system, run `npm i -g uipro-cli && uipro init --ai claude` and then run the skill. The applied result itself is preserved in `design-system/`.

## 📄 License

[MIT](LICENSE) — free to use, modify, and distribute.

---

<div align="center">
<sub>Auto-refreshed daily · Data sources: GitHub Trending, Hacker News, Reddit, X</sub>
</div>
