# AI 데일리 트렌드

매일 AI 분야의 핫한 이슈를 한 화면에 모아 보여주는 정적 웹사이트입니다.
GitHub Trending · Hacker News · Reddit · 화제의 SNS 글을 자동으로 수집해 정리합니다.

## 구성

```
.
├── index.html              # 빌드된 웹사이트 (자동 생성물)
├── data/data.json          # 수집된 데이터
├── scripts/
│   ├── collect.py          # 데이터 수집 (GitHub/HN/Reddit/SNS)
│   └── build.py            # data.json → index.html 렌더링
└── .github/workflows/
    └── daily.yml           # 매일 06:00 KST 자동 수집·빌드·배포
```

## 디자인

[UI UX Pro Max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) 스킬이
이 제품(AI 트렌드 대시보드)에 맞춰 추천한 디자인 시스템을 적용했습니다.

- 패턴: Bento Grid Showcase
- 스타일: 다크 테크 (Exaggerated Minimalism)
- 컬러: 슬레이트 다크 배경 + 상태 그린(#22C55E) 액센트
- 타이포: Space Grotesk (제목) + DM Sans (본문)

## 로컬 실행

```bash
python3 scripts/collect.py   # 최신 데이터 수집 (인터넷 필요)
python3 scripts/build.py     # index.html 생성
# index.html 을 브라우저로 열기
```

> 참고: `collect.py` 는 GitHub·Reddit·Hacker News 에 직접 접속합니다.
> 네트워크가 제한된 환경에서는 기존 `data/data.json` 으로 `build.py` 만 실행하세요.

## 자동 배포 (GitHub Pages)

1. 이 폴더를 GitHub 저장소로 푸시
2. 저장소 Settings → Pages → Source 를 **GitHub Actions** 로 설정
3. 매일 06:00 KST 에 자동으로 데이터가 갱신되고 사이트가 배포됩니다
   (Actions 탭에서 **Run workflow** 로 수동 실행도 가능)

## Git 시작하기 (내 PC에서)

> 만약 폴더에 비어 있는 `.git` 폴더가 남아 있다면 먼저 삭제한 뒤 진행하세요.

```bash
git init
git add -A
git commit -m "feat: AI 데일리 트렌드 사이트 초기 구성"

# GitHub 에서 새 저장소를 만든 뒤:
git remote add origin https://github.com/<사용자명>/<저장소명>.git
git branch -M main
git push -u origin main
```

이후 Settings → Pages → Source 를 **GitHub Actions** 로 지정하면 끝입니다.
