# 🎮 League of Legends 내전 관리 및 팀 구성 시스템

이 프로젝트는 리그오브레전드 내전(5:5)의 공정한 팀 구성과 전적 관리를 위해 **Streamlit**과 **Riot API**, **GitHub(JSON)**을 연동하여 구현하는 웹 애플리케이션입니다.

## 🚀 주요 기능
1. **플레이어 관리**: Riot ID(닉네임#태그)를 통한 플레이어 등록 및 실시간 티어 동기화.
2. **실시간 데이터**: Riot API를 사용하여 솔로 랭크 티어 및 LP 데이터 추출.
3. **팀 밸런싱 (랜덤)**: MMR 기반으로 팀 합계 점수 차이가 최소화된 후보군 중 무작위 팀 구성.
4. **팀 밸런싱 (포지션 고정)**: 플레이어별 포지션 숙련도를 고려한 최적의 포지션 배정.
5. **전적 관리**: 내전 결과(승/패/포지션)를 기록하고 승률 및 통계 업데이트.
6. **데이터 저장**: 별도의 DB 없이 GitHub 리포지토리의 JSON 파일을 저장소로 활용.

## 🛠 기술 스택
- **Language**: Python 3.x
- **Framework**: Streamlit
- **API**: Riot API (Account-V1, Summoner-V4, League-V4)
- **Storage**: GitHub Repository (JSON files)
- **Library**: `PyGithub`, `requests`, `pandas`, `itertools`

## 📂 프로젝트 구조
```text
.
├── app.py                # 메인 Streamlit UI 및 페이지 네비게이션
├── riot_api.py           # Riot API 연동 (티어/PUUID 정보 획득)
├── github_utils.py       # GitHub API 연동 (JSON 읽기/쓰기/커밋)
├── balancer.py           # MMR 계산 및 팀 구성 알고리즘 (Tolerance 로직 포함)
├── requirements.txt      # 프로젝트 의존성 라이브러리
└── .streamlit/
    └── secrets.toml      # API 키 및 보안 설정 (로컬 개발용)
📊 데이터 스키마 (JSON)
1. data/players.json
code
JSON
{
  "players": [
    {
      "name": "닉네임",
      "tag": "KR1",
      "puuid": "RIOT_PUUID",
      "solo_tier": "GOLD",
      "solo_rank": "I",
      "solo_lp": 55,
      "mmr": 1655,
      "inhouse_stats": {
        "win": 12,
        "loss": 8,
        "positions": { "TOP": 4, "JNG": 2, "MID": 10, "ADC": 2, "SUP": 2 }
      }
    }
  ]
}
⚙️ 설정 가이드 (Secrets)
Streamlit Cloud 또는 로컬의 secrets.toml에 다음 정보가 필요합니다.
RIOT_API_KEY: Riot Developer Portal에서 발급.
GITHUB_TOKEN: GitHub Personal Access Token (repo 권한 필요).
REPO_NAME: "계정명/리포지토리명"
ADMIN_PASSWORD: 관리자 메뉴 접속용 비밀번호.
🧠 핵심 로직: 팀 구성 (balancer.py)
MMR 산출: 솔랭 티어 점수 + (내전 승률 가중치).
조합 탐색: 10명의 플레이어로 가능한 모든 5:5 조합(252개) 생성.
오차 범위(Tolerance):
최소 점수 차이(min_diff) + 허용 오차(예: 50점) 이내의 모든 조합을 필터링.
필터링된 후보군 중 random.choice()를 통해 매번 다른 팀 구성 결과 제공.
포지션 최적화: 각 팀 내부에서 5명의 포지션 숙련도 합이 최대가 되는 순열(5!)을 계산하여 포지션 지정.
🛠 개발 로드맵 (Claude Code 지시용)
1단계: riot_api.py 작성 (Riot ID 입력 시 티어 및 MMR 반환 기능).
2단계: github_utils.py 작성 (PyGithub를 이용한 JSON 읽기/쓰기 구현).
3단계: app.py 기본 레이아웃 및 플레이어 등록/조회 UI 구현.
4단계: balancer.py 작성 (MMR 기반 팀 배정 및 랜덤 오차 로직).
5단계: 관리자 페이지 전적 입력 및 JSON 업데이트 로직 완성.