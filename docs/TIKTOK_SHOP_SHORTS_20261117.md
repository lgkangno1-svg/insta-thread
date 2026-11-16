# TikTok 공개 게시물 다운로드: AVOCADOSS Downloader ↔ Shop Shorts

## 구조

- 원본 서비스: `lgkangno1-svg/insta-thread`, 운영 도메인 `download.avocadoss.co.kr` (MiniPC rootless FastAPI)
- UI/중계: `lgkangno1-svg/Kang-s-brain/projects/shop-shorts/site`, `th.avocadoss.co.kr/discovery.html`
- API: `POST /api/v1/analyze` → 분석 서명 토큰 → `POST /api/v1/jobs` → `GET /api/v1/jobs/{id}` → 파일 전송
- 인증·서명·디스크 용량·작업 큐·임시 파일 정리·속도 제한: 기존 엔진 구조 그대로 보존
- TikTok 공식 공개 경로: `tiktok.com/@{creator}/video/{id}`, `vm.tiktok.com`, `vt.tiktok.com`.
- 표준 `yt-dlp` TikTok extractor를 재사용하며 별도의 비공식 사이트·유료 API·비밀키를 사용하지 않음.
- 공용 로그인 쿠키를 TikTok 분석/단축 URL 처리에 전달하지 않음.
- 사용자 브라우저에 적용되는 UI는 Shop Shorts. 기존 다운로드 서비스의 다른 프런트엔드·다른 서비스는 수정하지 않음.

## 환경 진단 / 실제 파일 다운로드 검증

2026-11-17 MiniPC `tnfwod` 에서 공개 TikTok URL 한 건으로 다음을 확인했다.

- `yt-dlp` 2026.08.19 기본 User-Agent: `Unexpected response from webpage request`.
- `yt-dlp` 2026.10.26 기본 User-Agent: 같은 오류.
- 일반 브라우저 User-Agent (Chrome/140, 자격 증명 없음)로 두 버전의 공개 메타데이터 추출 성공: 포맷 9개.
- `yt_dlp_adapter.prepare_video`를 직접 실행: 451137바이트 MP4 생성 성공, `ffprobe`에서 비디오·오디오 및 7.081995초 확인.
- 테스트 파일은 독립 Kelvin 작업공간의 TemporaryDirectory에만 작성하고 종료 시 삭제.

이 결과는 테스트한 단일 공개 영상과 현재 MiniPC 네트워크 조건에 한정된다. 비공개·지역 제한·삭제·유료·DRM 자료가 재생 또는 추출 가능하다는 의미가 아니다. 틱톡의 HTML/추출기 동작이 변경되면 다시 실패할 수 있다.

## 배포 및 검증

1. 다른 작업자 파일과 현재 `origin/main`·`origin/production` 및 운영 SHA 확인.
2. MiniPC에서 `PYTHON=<existing test venv> bash scripts/ci-minipc-seo.sh`를 사용. GitHub Actions를 실행하지 않는다.
3. 테스트된 TikTok 커밋만 main에 PR 병합, production은 GitHub 원격 포인터를 빠른 전진으로만 갱신.
4. 기존 시스템 계정의 자동 배포/watchdog 상태를 먼저 확인하고 운영 프로세스·파일을 수동으로 건드리지 않는다.
5. `https://download.avocadoss.co.kr/build.txt`를 원격 production SHA와 비교.
6. 사용자 실제 브라우저에서 `th.avocadoss.co.kr/discovery.html` 공개 영상 분석·선택·다운로드 및 MiniPC 실제 파일 추출 검증.
7. 모든 단계가 검증되지 않으면 미완료로 보고.

## 주의

- TikTok 전용 표준 User-Agent는 공개 페이지 응답을 정상적으로 받기 위한 옵션일 뿐, CAPTCHA/로그인/DRM 우회나 비공개 데이터 접근을 제공하지 않는다.
- 원본 영상 권리 확인 없이 재배포하거나 서비스 업로드까지 자동 진행하지 않는다.
- 데이터 수집 API `/api/discovery/search`는 별도 이슈로 미연결(HTTP 501). 개별 게시물 URL 다운로드와 다른 기능이다.
