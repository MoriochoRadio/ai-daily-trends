<div align="center">

# 🤖 AI 데일리 트렌드

**매일 아침, 전 세계 AI 분야의 가장 뜨거운 이슈를 한 화면에 모아 보여주는 자동화 대시보드**

GitHub Trending · Hacker News · Reddit · 화제의 SNS를 자동 수집·정리하여 매일 06:00 KST에 갱신됩니다.

[![Daily AI Trends](https://github.com/MoriochoRadio/ai-daily-trends/actions/workflows/daily.yml/badge.svg)](https://github.com/MoriochoRadio/ai-daily-trends/actions/workflows/daily.yml)
[![Live Site](https://img.shields.io/badge/Live-moriochoradio.github.io-22C55E?logo=githubpages&logoColor=white)](https://moriochoradio.github.io/ai-daily-trends/)
[![License: MIT](https://img.shields.io/badge/License-MIT-334155.svg)](LICENSE)

### 👉 **[지금 바로 보기 — moriochoradio.github.io/ai-daily-trends](https://moriochoradio.github.io/ai-daily-trends/)**

</div>

---

## ✨ 특징

- **완전 자동화** — 사람 손 없이 매일 데이터를 수집하고 사이트를 빌드·배포합니다.
- **AI 특화 큐레이션** — 키워드 필터로 AI/LLM/에이전트 관련 콘텐츠만 골라냅니다.
- **4개 소스 통합** — GitHub·Hacker News·Reddit·X(트위터)의 화제글을 한 화면에서.
- **정적 사이트** — 빌드 결과물은 의존성 없는 단일 `index.html`. 빠르고, 무료로 호스팅됩니다.
- **반응형 + 접근성** — 모바일~데스크톱 대응, `prefers-reduced-motion`·키보드 포커스 등 준수.

## 📊 데이터 소스

| 소스 | 수집 방식 | 내용 |
|------|-----------|------|
| **GitHub Trending** | HTML 스크레이핑 (daily / python / jupyter) | 오늘 가장 많은 ★를 받은 AI 저장소 |
| **Hacker News** | [Algolia HN Search API](https://hn.algolia.com/api) | 프론트페이지의 AI 관련 핵심 논의 |
| **Reddit** | 공개 RSS 피드 (`r/LocalLLaMA`, `r/MachineLearning`) | 커뮤니티 화제글 |
| **화제의 SNS** | HN 내 X/Twitter 링크 추출 | 인플루언서·연구자의 화제 스레드 |

> **Reddit 참고:** Reddit이 비인증 JSON 엔드포인트와 CI 공유 IP를 차단(403/429)하므로, 브라우저 헤더 + 공개 RSS + 재시도/백오프로 안정화했습니다. 한 서브레딧이 막혀도 라운드로빈 병합으로 다른 소스가 빈 자리를 채웁니다.

## 🎨 디자인 시스템

디자인은 [**UI UX Pro Max**](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) 스킬이 이 제품(AI 트렌드 대시보드)에 맞춰 추론·생성한 디자인 시스템을 적용했습니다. 생성된 사양의 원본은 [`design-system/ai-daily-trends/MASTER.md`](design-system/ai-daily-trends/MASTER.md)에 있습니다.

| 항목 | 선택 |
|------|------|
| **패턴** | Bento Grid Showcase (대시보드형 모듈 카드 — 스킬이 "Best for Dashboards / WCAG AA"로 권장) |
| **스타일** | 다크 테크 (Exaggerated Minimalism) |
| **컬러** | 슬레이트 다크 배경 `#0F172A` + 상태 그린 액센트 `#22C55E` |
| **타이포** | `Space Grotesk` (제목) + `DM Sans` (본문) |

## 🏗️ 동작 구조

```
                    ┌─────────────────── GitHub Actions (매일 06:00 KST) ───────────────────┐
                    │                                                                       │
  collect.py  ───►  data/data.json  ───►  build.py  ───►  index.html  ───►  GitHub Pages 배포
 (4개 소스 수집)      (수집 데이터)        (렌더링)        (정적 사이트)        (자동 공개)
```

1. **`collect.py`** — 4개 소스에서 AI 관련 콘텐츠를 수집해 `data/data.json`으로 저장
2. **`build.py`** — `data.json`을 디자인 시스템이 적용된 `index.html`로 렌더링
3. **GitHub Actions** — 위 두 단계를 매일 실행하고 결과를 커밋 후 Pages로 배포

## 📁 프로젝트 구조

```
.
├── index.html                       # 빌드된 웹사이트 (자동 생성물)
├── data/data.json                   # 수집된 데이터
├── scripts/
│   ├── collect.py                   # 데이터 수집 (GitHub · HN · Reddit · SNS)
│   └── build.py                     # data.json → index.html 렌더링
├── design-system/
│   └── ai-daily-trends/MASTER.md    # 적용된 디자인 시스템 (스킬 생성물 · Source of Truth)
└── .github/workflows/daily.yml      # 매일 자동 수집 · 빌드 · 배포
```

## 💻 로컬 실행

> Python 3.x만 있으면 됩니다. 외부 라이브러리 의존성이 없습니다.

```bash
python3 scripts/collect.py   # 최신 데이터 수집 (인터넷 필요)
python3 scripts/build.py     # index.html 생성
# 생성된 index.html 을 브라우저로 열기
```

네트워크가 제한된 환경에서는 수집을 건너뛰고 기존 `data/data.json`으로 빌드만 실행하면 됩니다.

```bash
python3 scripts/build.py
```

## 🚀 배포 (이미 자동화됨)

이 저장소는 **GitHub Actions + GitHub Pages**로 이미 배포되어 있습니다.

- 매일 **06:00 KST**에 자동으로 데이터가 갱신되고 사이트가 재배포됩니다.
- 즉시 갱신하려면: **Actions 탭 → Daily AI Trends → Run workflow**

직접 포크해서 운영하려면:

1. 저장소를 포크/클론 후 본인 GitHub에 푸시
2. **Settings → Pages → Source** 를 **GitHub Actions** 로 설정
3. 끝 — 이후 매일 자동 갱신됩니다

## 🛠️ 기술 스택

- **언어:** Python 3 (표준 라이브러리만 사용 — `urllib`, `re`, `json`)
- **프런트엔드:** 순수 HTML/CSS (빌드 타임 생성, 런타임 JS 의존성 없음)
- **CI/CD:** GitHub Actions
- **호스팅:** GitHub Pages
- **디자인:** [UI UX Pro Max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) 스킬

> **참고:** UI UX Pro Max 스킬(`.claude/`)은 제3자 도구이므로 저장소에는 포함하지 않습니다(.gitignore). 디자인 시스템을 다시 생성하려면 `npm i -g uipro-cli && uipro init --ai claude` 후 스킬을 실행하세요. 적용된 결과 자체는 `design-system/`에 보존되어 있습니다.

## 📄 라이선스

[MIT](LICENSE) — 자유롭게 사용·수정·배포할 수 있습니다.

---

<div align="center">
<sub>매일 자동 갱신 · 데이터 출처: GitHub Trending, Hacker News, Reddit, X</sub>
</div>
