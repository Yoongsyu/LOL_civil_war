"""
riot_api.py
Riot API 연동 모듈: PUUID, 소환사 정보, 솔로 랭크 티어/LP/전적 조회 및 MMR 환산
"""

import requests
import streamlit as st

# ─── 상수 정의 ────────────────────────────────────────────────
TIER_BASE_MMR = {
    "IRON":        0,
    "BRONZE":    400,
    "SILVER":    800,
    "GOLD":     1200,
    "PLATINUM": 1600,
    "EMERALD":  2000,
    "DIAMOND":  2400,
    "MASTER":   2800,
    "GRANDMASTER": 3200,
    "CHALLENGER":  3600,
}

RANK_OFFSET = {
    "IV": 0,
    "III": 100,
    "II":  200,
    "I":   300,
}

POSITIONS = ["TOP", "JNG", "MID", "ADC", "SUP"]

# 지역 라우팅 (한국 서버 기준)
REGION_ASIA   = "asia"
REGION_KR     = "kr"


def _get_headers() -> dict:
    """Riot API 요청 헤더 반환"""
    api_key = st.secrets.get("RIOT_API_KEY", "")
    return {"X-Riot-Token": api_key}


def get_puuid(game_name: str, tag_line: str) -> dict:
    """
    Riot ID(닉네임#태그)로 PUUID 조회 (Account-V1)
    반환: {"puuid": str, "gameName": str, "tagLine": str} or {"error": str}
    """
    url = (
        f"https://{REGION_ASIA}.api.riotgames.com"
        f"/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
    )
    try:
        resp = requests.get(url, headers=_get_headers(), timeout=10)
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 404:
            return {"error": "플레이어를 찾을 수 없습니다. 닉네임과 태그를 확인해 주세요."}
        elif resp.status_code == 401:
            return {"error": "Riot API 키가 유효하지 않습니다."}
        else:
            return {"error": f"API 오류 발생 (상태 코드: {resp.status_code})"}
    except requests.exceptions.Timeout:
        return {"error": "요청 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요."}
    except requests.exceptions.RequestException as e:
        return {"error": f"네트워크 오류: {str(e)}"}


def get_league_entries_by_puuid(puuid: str) -> dict:
    """
    PUUID로 랭크 정보 직접 조회 (League-V4 by PUUID)
    반환: {"solo_tier": str, "solo_rank": str, "solo_lp": int, "wins": int, "losses": int} or {"error": str}
    """
    url = (
        f"https://{REGION_KR}.api.riotgames.com"
        f"/lol/league/v4/entries/by-puuid/{puuid}"
    )
    try:
        resp = requests.get(url, headers=_get_headers(), timeout=10)
        if resp.status_code != 200:
            return {"error": f"랭크 정보 조회 실패 (상태 코드: {resp.status_code})"}

        entries = resp.json()
        for entry in entries:
            if entry.get("queueType") == "RANKED_SOLO_5x5":
                return {
                    "solo_tier": entry.get("tier", "UNRANKED"),
                    "solo_rank": entry.get("rank", ""),
                    "solo_lp":   entry.get("leaguePoints", 0),
                    "wins":      entry.get("wins", 0),
                    "losses":    entry.get("losses", 0),
                }
        # 솔로랭크 항목 없음 → 언랭
        return {
            "solo_tier": "UNRANKED",
            "solo_rank": "",
            "solo_lp":   0,
            "wins":      0,
            "losses":    0,
        }
    except requests.exceptions.RequestException as e:
        return {"error": f"네트워크 오류: {str(e)}"}


def calculate_mmr(tier: str, rank: str, lp: int,
                  inhouse_win: int = 0, inhouse_loss: int = 0) -> int:
    """
    티어, 랭크, LP, 내전 전적을 기반으로 MMR(내부 점수) 환산
    - 기본 MMR: 티어 기준 점수 + 랭크 오프셋 + LP
    - 내전 가중치: 내전 게임이 5게임 이상인 경우 승률에 따라 ±최대 150점 보정
    """
    tier_upper = tier.upper()
    base = TIER_BASE_MMR.get(tier_upper, 0)
    rank_add = RANK_OFFSET.get(rank, 0)

    if tier_upper in ("MASTER", "GRANDMASTER", "CHALLENGER"):
        # 마스터 이상은 LP가 누적되므로 rank 오프셋 없음
        mmr = base + lp
    else:
        mmr = base + rank_add + lp

    # 내전 승률 가중치 (최소 5게임 이상 참여 시 반영)
    total_inhouse = inhouse_win + inhouse_loss
    if total_inhouse >= 5:
        win_rate = inhouse_win / total_inhouse
        # 승률 50% 기준으로 -150 ~ +150점 보정
        weight = (win_rate - 0.5) * 300
        mmr = int(mmr + weight)

    return max(0, mmr)


def fetch_player_data(game_name: str, tag_line: str) -> dict:
    """
    Riot ID 입력 후 플레이어의 전체 정보를 조회하여 반환하는 통합 함수
    반환: 플레이어 딕셔너리 or {"error": str}
    """
    # 1) PUUID 조회
    account_data = get_puuid(game_name, tag_line)
    if "error" in account_data:
        return account_data

    puuid = account_data["puuid"]

    # 2) 랭크 정보 조회 (PUUID 직접 사용 - Summoner ID 단계 불필요)
    league_data = get_league_entries_by_puuid(puuid)
    if "error" in league_data:
        return league_data

    tier  = league_data["solo_tier"]
    rank  = league_data["solo_rank"]
    lp    = league_data["solo_lp"]

    # 4) MMR 초기 계산 (내전 전적 없음)
    mmr = calculate_mmr(tier, rank, lp)

    player = {
        "name":      game_name,
        "tag":       tag_line,
        "puuid":     puuid,
        "solo_tier": tier,
        "solo_rank": rank,
        "solo_lp":   lp,
        "mmr":       mmr,
        "inhouse_stats": {
            "win":  0,
            "loss": 0,
            "positions": {p: 0 for p in POSITIONS},
            "position_wins": {p: 0 for p in POSITIONS},
        },
    }
    return player


def tier_label(tier: str, rank: str, lp: int) -> str:
    """티어 + 랭크 + LP 를 읽기 편한 문자열로 반환. 예) GOLD II 55LP"""
    if tier == "UNRANKED":
        return "Unranked"
    upper = tier.upper()
    if upper in ("MASTER", "GRANDMASTER", "CHALLENGER"):
        return f"{tier.capitalize()} {lp}LP"
    return f"{tier.capitalize()} {rank} {lp}LP"


def tier_emoji(tier: str) -> str:
    """티어별 이모지 반환"""
    mapping = {
        "IRON":        "⬛",
        "BRONZE":      "🟫",
        "SILVER":      "⬜",
        "GOLD":        "🟨",
        "PLATINUM":    "🟩",
        "EMERALD":     "💚",
        "DIAMOND":     "💎",
        "MASTER":      "🔮",
        "GRANDMASTER": "🔴",
        "CHALLENGER":  "🏆",
        "UNRANKED":    "❓",
    }
    return mapping.get(tier.upper(), "❓")


if __name__ == "__main__":
    # 테스트: 실제 Riot ID 입력 시 동작 확인
    import sys
    if len(sys.argv) >= 3:
        name, tag = sys.argv[1], sys.argv[2]
    else:
        name, tag = "Hide on bush", "KR1"
    print(f"[테스트] {name}#{tag} 조회 중...")
    result = fetch_player_data(name, tag)
    print(result)
