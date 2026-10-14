# EVE 웹 프로젝트

기존 `eve_project`와 분리된 로컬 프론트엔드·Django 백엔드 프로젝트입니다.

## 로컬 실행 (PowerShell, 저장소 최상위)

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\.venv\Scripts\python.exe backend\manage.py migrate
.\.venv\Scripts\python.exe backend\manage.py runserver
```

이미 가상환경·패키지·DB를 준비했다면 마지막 `runserver` 명령만 실행합니다. 가상환경 활성화 스크립트는 필요하지 않습니다.

- 사이트: http://127.0.0.1:8000/
- 관리자: http://127.0.0.1:8000/admin/

관리자 계정이 없다면 `createsuperuser` 명령으로 해당 PC에서 별도 생성합니다. DB와 계정은 GitHub에 저장되지 않습니다.

`dist/index.html`을 파일로 직접 열어 화면을 볼 수도 있지만, 실제 회원 기능은 개발 서버 주소에서만 동작합니다.

## 회원 기능

- 아이디·닉네임·비밀번호·비밀번호 확인으로 회원가입
- 중복 아이디, 약한 비밀번호, 비밀번호 불일치 검증
- 가입 후 자동 로그인, 일반 로그인, 로그아웃
- Django 세션 쿠키로 새로고침 후 로그인 유지
- 상단 닉네임 표시와 입력 오류 안내
- Django 비밀번호 해시 저장 및 CSRF 보호

닉네임은 필수 입력이며 최대 30자입니다. 닉네임 중복은 허용됩니다. 비밀번호 찾기, 이메일 인증, 가입 승인, 로그인 시도 제한, 운영 배포는 아직 구현하지 않았습니다.

API는 `/api/accounts/session/` (GET), `signup/`, `login/`, `logout/` (POST)입니다. POST 입력은 form-urlencoded이며 CSRF 토큰이 필요합니다.

## 화면 기능

메뉴·바로가기, 프로모션 전환, 게임 검색·필터·상세, 이벤트 목록·상세, 카지노 필터, 스포츠 샘플 검색·선택 목록, 뒤로가기·새로고침을 지원합니다. 경기·배당·점수·카지노 분류는 화면 확인용 샘플입니다. 게임 API, 실제 게임 실행, 입출금·베팅·정산은 연결되지 않았습니다.

## 설정·검증

Python 3.14 / Django 6.1.2 / SQLite를 사용합니다. 관리자 언어는 한국어, 서버 시간대는 UTC이며 화면 시계는 서울 시간입니다.

비밀키는 `DJANGO_SECRET_KEY` 환경변수 또는 Git에서 제외한 `backend/.local-secret`에 보관합니다. 로컬 비밀키 파일이 없으면 개발 시 자동 생성합니다. `.venv`, DB, 비밀키는 커밋하지 않습니다.

```powershell
.\.venv\Scripts\python.exe backend\manage.py check
.\.venv\Scripts\python.exe backend\manage.py test accounts
```

회원 테스트는 별도 임시 DB를 사용합니다. 로컬 정적 파일 제공은 DEBUG 모드용입니다. 운영 배포 전에는 정적 파일 제공·HTTPS·배포 설정과 추가 보안 기능을 구성해야 합니다.
