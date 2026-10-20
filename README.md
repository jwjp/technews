# 모아읽기

광고 없이 기술·경제 블로그, 커뮤니티 글과 국내 IT·경제 뉴스를 모아 보는 개인용 GitHub Pages 리더입니다. RSS·Atom을 GitHub Actions에서 읽고, 제목·짧은 소개·피드가 제공하는 글 링크만 정적 JSON으로 발행합니다. 뉴스는 소개 문구를 저장하지 않습니다.

## 기능

- Velopers, TechBlogPosts, Indieblog, 어썸블로그, GeekNews, Hacker News 한국어 피드 수집
- 전자신문 IT·SW·보안·AI·모빌리티, ZDNet Korea, AI타임스, IT동아, ITWorld Korea, 테크M, 데일리시큐, AI매터스, 모터그래프, 오토헤럴드, 로봇신문 뉴스를 기술 뉴스 목록으로 제공
- 메르의 블로그, 아기곰의 부동산 산책, 오윤섭의 부자노트, 잭파시 갭투자 연구소를 경제 글 목록으로 제공
- 한국경제·매일경제·이투데이·파이낸셜뉴스·뉴시스·아주경제의 경제 뉴스와 한국은행·중소벤처기업부 발표 원문을 경제 뉴스 목록으로 제공
- 기술 뉴스는 기술·개발·소프트웨어·보안·AI·자동차, 경제 글과 뉴스는 주식·금융·부동산·경제·정책 분야별로 필터링
- 원문 URL과 제목 기반 중복 정리
- 출처 구독·숨김, 제목·소개 검색, 관심/제외 키워드
- 읽음 표시, 북마크, 다크 모드
- 브라우저에 설정 저장, JSON 내보내기·가져오기
- 3시간마다 피드 갱신 및 GitHub Pages 자동 배포

## 로컬 실행

Python 3.10 이상이면 추가 패키지 없이 실행할 수 있습니다.

```sh
python scripts/fetch_feeds.py
python -m http.server 8000 --directory site
```

브라우저에서 `http://localhost:8000`을 엽니다. 수집기 실행 시 `site/data/articles.json`이 갱신됩니다.

## 소스 추가

`sources.json`에 `id`, `name`, `url`, `group`을 가진 객체를 추가한 뒤 수집기를 실행합니다. 기술 뉴스는 `"type": "news"`, 경제 블로그는 `"type": "economy-blog"`, 경제 뉴스는 `"type": "economy"`와 해당 분야의 `"topics"`를 지정합니다. 뉴스는 소개 문구를 저장하지 않습니다. 여러 분야가 섞인 피드는 `"classify": true`로 설정하면 제목을 바탕으로 관련 기사만 수집합니다. 분야 분류는 자동이므로 일부 글이 다르게 분류될 수 있습니다. 피드는 RSS 2.0 또는 Atom 형식이어야 합니다. 일부 피드가 실패하면 이전에 수집된 글은 유지하며, 모든 피드가 실패하면 작업이 실패합니다.

## GitHub Pages 배포

1. 저장소를 GitHub에 푸시합니다.
2. **Settings → Pages → Build and deployment → Source**에서 **GitHub Actions**를 선택합니다.
3. **Actions**의 `Refresh feeds and publish Pages` 작업을 확인합니다. `main` 브랜치에 푸시할 때와 3시간마다 실행됩니다. `workflow_dispatch`로 수동 실행도 가능합니다.

사이트는 프로젝트 저장소의 Pages 경로에서도 상대 URL로 동작합니다. 읽음·북마크·취향 설정은 방문한 브라우저에만 저장되므로 다른 기기와 자동 동기화되지는 않습니다. `설정 내보내기/가져오기`로 옮길 수 있습니다.

## 데이터 범위

최근 180일 글 중 기술 블로그 최대 1,000개, 기술 뉴스 최대 1,800개, 경제 블로그 최대 1,000개, 경제 뉴스 최대 1,800개의 제목·짧은 소개·날짜·출처·링크만 보관합니다. 링크는 원문 또는 피드를 제공한 큐레이션 페이지로 연결될 수 있습니다. 글 본문과 이미지는 재게시하지 않습니다. [awesome-devblog](https://github.com/awesome-devblog/awesome-devblog)는 추후 새 블로그를 발견하기 위한 목록으로 참고할 수 있습니다.
