# AVOCADOSS Download 검색·AI 검색 개선 기록 (2026-10-17)

## 서비스 및 정규 주소
- 사용자 입력 주소: https://insta.avocadoss.co.kr/
- HTTP 301 정규 주소: https://download.avocadoss.co.kr/instagram-reels-downloader
- 통합 사이트 정규 주소: https://download.avocadoss.co.kr/
- 주요 랜딩: /youtube-downloader, /instagram-reels-downloader, /threads-downloader
- 추가 지원: /douyin-downloader, /xiaohongshu-downloader
- 최종 검색 노출 대상은 별칭 호스트가 아닌 download.avocadoss.co.kr의 정규 페이지입니다.

## 적용한 점검 기준
- 참고: leopard627/fire-your-seo-agency (SEO, AEO, GEO, LLMO, NEO, 측정)
- 디자인: jakubkrehel/skills의 better-ui, better-layout, interface-review, better-accessibility 및 Superfuture/design-review 체크리스트
- 검색엔진 정책 위반 수법(키워드 반복 삽입, 허위 통계, 유료 백링크)은 사용하지 않습니다.

## 기술 검사 (MiniPC)
- HTML 자체에 제목, H1, 본문, FAQ, JSON-LD 존재 (JS 실행 불필요)
- robots.txt 및 sitemap.xml 존재, 정규 URL 유지
- 7개 색인 페이지의 고유 title/description, WebApplication/FAQPage/BreadcrumbList JSON-LD 확인
- FAQPage 질문과 답변이 실제 HTML FAQ와 동일한지 자동검사
- og-social.png (1200 × 630)와 OG 메타/공유 미리보기 확인
- 인스타 서브도메인의 301 정규 리다이렉트 정책 보존
- HEAD /indexable 페이지 200 검증 (SERVE_WEB=true 실행 별도 테스트)
- api/health/build.txt는 색인 금지, 원본 다운로더 엔진 동작은 기존 경로 유지
- GitHub Actions 대신 MiniPC에서 scripts/ci-minipc-seo.sh로 테스트

## GEO / AEO / 네이버
- 검색 질문형 설명/FAQ, 플랫폼별 최초 단락과 내부 링크를 강화
- llms.txt에 플랫폼별 지원 범위와 주의 사항 보강
- 브랜드명을 AVOCADOSS Download로 일관되게 사용
- 검색엔진과 생성형 검색이 지원 범위를 오해하지 않도록 비공개·DRM 제한 명시
- Bing/네이버/Google 도구에서 실제 인덱스 등록과 AI 답변 인용 여부를 확인해야 함. 코드 반영만으로 색인이나 노출은 보장하지 않음.
- GSC Wizard 앱이 사용기한/구독 문제로 연결된 속성 조회를 거부했습니다. Google Search Console에서 수동으로 사이트맵 제출 또는 계정 복구 필요.

## 14일 측정 제안
- 2026-10-17: 주요 3개 랜딩의 Google Search Console 노출수/클릭수/CTR/평균 게재순위 기준선 저장
- 2026-10-24: 색인 여부, 크롤링 오류, 검색어별 노출 확인
- 2026-10-31: 14일 구간과 이전 같은 길이 구간 비교. 유튜브 다운로더/인스타그램 다운로더/쓰레드 다운로더별 성과 기록
- 검색 결과뿐 아니라 ChatGPT/Perplexity/네이버 AI 브리핑의 실인용 여부를 별도로 관찰하며, 인용이 없으면 인용되었다고 기록하지 않음.

## 릴리스 검증
- commit SHA: git rev-parse HEAD
- 운영 SHA: curl https://download.avocadoss.co.kr/build.txt
- 두 값이 같고 실제 HTML에 메타·CSS·OG 이미지가 있을 때만 배포 완료로 기록
