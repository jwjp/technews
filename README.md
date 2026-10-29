# 모아읽기

광고 없이 기술·경제 블로그, 커뮤니티 글과 국내 IT·경제 뉴스를 모아 보는 개인용 GitHub Pages 리더입니다. RSS·Atom을 GitHub Actions에서 읽고, 제목·짧은 소개·피드가 제공하는 글 링크만 정적 JSON으로 발행합니다. 뉴스는 소개 문구를 저장하지 않습니다.

## 기능

- Velopers, TechBlogPosts, Indieblog, 어썸블로그, GeekNews, Hacker News 한국어 피드 수집
- 전자신문 IT·SW·보안·AI·모빌리티, ZDNet Korea, AI타임스, IT동아, ITWorld Korea, 테크M, 데일리시큐, AI매터스, 모터그래프, 오토헤럴드, 로봇신문 뉴스를 기술 뉴스 목록으로 제공
- 메르의 블로그, 아기곰의 부동산 산책, 오윤섭의 부자노트, 잭파시 갭투자 연구소를 경제 글 목록으로 제공
- 한국경제·매일경제·이투데이·파이낸셜뉴스·뉴시스·아주경제의 경제 뉴스와 한국은행·중소벤처기업부 발표 원문을 경제 뉴스 목록으로 제공
- 기술 뉴스는 기술·개발·소프트웨어·보안·AI·자동차, 경제 글과 뉴스는 주식·금융·부동산·경제·정책 분야별로 필터링
- 원문 URL과 제목 기반 중복 정리
- GitHub 이슈를 통한 공통 RSS 구독·해지, 브라우저별 출처 숨김, 제목·소개 검색, 관심/제외 키워드
- 읽음 표시, 북마크, 다크 모드
- 브라우저에 설정 저장, JSON 내보내기·가져오기
- 매주 기술·경제 RSS 후보 추천, 최근 글 미리보기, 공통 구독 신청·해지
- 3시간마다 피드 갱신 및 GitHub Pages 자동 배포

## 로컬 실행

Python 3.10 이상이면 추가 패키지 없이 실행할 수 있습니다.

```sh
python scripts/fetch_feeds.py
python scripts/discover_sources.py
python -m http.server 8000 --directory site
```

브라우저에서 `http://localhost:8000`을 엽니다. 수집기 실행 시 `site/data/articles.json`이 갱신됩니다.

## 주간 새 소스 후보

`Recommend weekly sources` 작업은 매주 월요일 오전 8시 31분(한국 시간)에 실행되어 `site/data/candidates.json`을 갱신하고 Pages를 직접 배포합니다. 기술 후보는 [Awesome Devblog](https://github.com/awesome-devblog/awesome-devblog)의 공개 RSS 목록과 `discovery_seeds.json`에서, 경제 후보는 [블라이의 경제 블로그 공개 목록](https://blai.co.kr/blog-stats/ranking)과 `discovery_seeds.json`에서 찾습니다. 후보의 RSS를 실제로 읽어 최근 120일에 글이 2개 이상이고 주제 관련 제목이 있는 소스만 추천합니다. 추천에서 빠진 후보도 나중에 구독할 수 있도록 검증된 소스 정보는 `site/data/source_catalog.json`에 유지합니다.

특정 공개 목록에 접속할 수 없어도 다른 후보 입력은 계속 확인합니다. 같은 주에 수동으로 다시 검사하려면 `python scripts/discover_sources.py --force`를 실행합니다.

## 공통 RSS 구독

후보의 **구독 신청**을 누르면 후보 ID가 입력된 GitHub 이슈 작성 화면이 열립니다. 저장소 소유자 `jwjp`가 로그인해 이슈를 제출하면 `Manage shared RSS subscriptions` 작업이 요청자와 후보 ID를 확인하고, RSS를 다시 검사해 `sources.json`에 추가합니다. 이어 글 목록을 갱신하고 Pages를 직접 배포한 뒤 이슈에 결과를 남기고 닫습니다. Actions가 만든 커밋은 다른 푸시 작업을 실행하지 않으므로 같은 작업 안에서 배포합니다. 기존 소스 옆 **구독 해지**도 같은 방식으로 처리합니다. 이슈가 실패하면 열린 상태로 남으므로 Actions 로그에서 이유를 확인할 수 있습니다.

공통 구독 목록은 공개 저장소와 사이트의 모든 방문자에게 동일하게 보입니다. 소스 체크박스는 해당 브라우저에서만 글을 숨기며 공통 구독을 바꾸지 않습니다. 개인 읽음·북마크·취향 설정도 브라우저별로 유지됩니다. GitHub 이슈를 제출하는 단계가 필요하며, Pages의 자바스크립트에는 GitHub 토큰을 넣지 않습니다.

## 소스 추가

`sources.json`에 `id`, `name`, `url`, `group`을 가진 객체를 추가한 뒤 수집기를 실행합니다. 기술 뉴스는 `"type": "news"`, 경제 블로그는 `"type": "economy-blog"`, 경제 뉴스는 `"type": "economy"`와 해당 분야의 `"topics"`를 지정합니다. 뉴스는 소개 문구를 저장하지 않습니다. 여러 분야가 섞인 피드는 `"classify": true`로 설정하면 제목을 바탕으로 관련 기사만 수집합니다. 분야 분류는 자동이므로 일부 글이 다르게 분류될 수 있습니다. 피드는 RSS 2.0 또는 Atom 형식이어야 합니다. 일부 피드가 실패하면 이전에 수집된 글은 유지하며, 모든 피드가 실패하면 작업이 실패합니다.

## GitHub Pages 배포

1. 저장소를 GitHub에 푸시합니다.
2. **Settings → Pages → Build and deployment → Source**에서 **GitHub Actions**를 선택합니다.
3. **Actions**의 `Refresh feeds and publish Pages` 작업을 확인합니다. `main` 브랜치에 푸시할 때와 3시간마다 실행됩니다. `workflow_dispatch`로 수동 실행도 가능합니다.

사이트는 프로젝트 저장소의 Pages 경로에서도 상대 URL로 동작합니다. 읽음·북마크·취향 설정은 방문한 브라우저에만 저장되므로 다른 기기와 자동 동기화되지는 않습니다. `설정 내보내기/가져오기`로 옮길 수 있습니다.

## 데이터 범위

최근 180일 글 중 기술 블로그 최대 1,000개, 기술 뉴스 최대 1,800개, 경제 블로그 최대 1,000개, 경제 뉴스 최대 1,800개의 제목·짧은 소개·날짜·출처·링크만 보관합니다. 링크는 원문 또는 피드를 제공한 큐레이션 페이지로 연결될 수 있습니다. 글 본문과 이미지는 재게시하지 않습니다. [awesome-devblog](https://github.com/awesome-devblog/awesome-devblog)는 추후 새 블로그를 발견하기 위한 목록으로 참고할 수 있습니다.

## 피드 읽기 개선

정렬에서 **출처 골고루**를 선택하면 출처마다 한 글씩 번갈아 표시합니다. 최신순은 발행 시각을 그대로 따릅니다. 상단에는 확인 시각과 정상 수집된 소스 수를 표시합니다. 시간대 없는 날짜는 소스의 `timezone` 설정에 따라 해석합니다. 보관 기간은 최대 180일이며, 발행량이 많은 목록은 개수 제한에 먼저 도달할 수 있습니다.

발행량 편중을 줄이기 위해 출처별 하루 보관량을 뉴스 20개, 글 30개로 제한합니다. 각 목록의 전체 개수 제한도 적용됩니다. 이미 제외된 과거 글은 복구되지 않으며 이후 수집부터 보관 범위가 넓어집니다. 분야는 제목과 RSS 카테고리를 먼저 확인하고, 단서가 없으면 소스의 기본 분야를 사용합니다. 기술 글에서도 분야 필터를 제공합니다.
