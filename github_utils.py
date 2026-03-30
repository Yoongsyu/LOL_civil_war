"""
github_utils.py
GitHub API 연동 모듈: PyGithub를 사용하여 data/players.json 파일을 읽고 씁니다.
"""

import json
import base64
import streamlit as st
from github import Github, GithubException

# data/players.json의 기본 경로
DATA_FILE_PATH = "data/players.json"

# 초기 데이터 구조
EMPTY_DATA = {"players": []}


def _get_repo():
    """GitHub 리포지토리 객체 반환"""
    token = st.secrets.get("GITHUB_TOKEN", "")
    repo_name = st.secrets.get("REPO_NAME", "")
    g = Github(token)
    return g.get_repo(repo_name)


def load_players() -> list:
    """
    GitHub 저장소에서 data/players.json을 읽어 플레이어 리스트 반환.
    파일이 없으면 빈 리스트 반환 (자동 초기화).
    """
    try:
        repo = _get_repo()
        try:
            contents = repo.get_contents(DATA_FILE_PATH)
            data = json.loads(contents.decoded_content.decode("utf-8"))
            return data.get("players", [])
        except GithubException as e:
            if e.status == 404:
                # 파일이 없으면 자동 생성
                _create_empty_file(repo)
                return []
            raise
    except Exception as e:
        st.error(f"데이터 로드 오류: {str(e)}")
        return []


def _create_empty_file(repo):
    """data/players.json 파일을 빈 구조로 생성"""
    try:
        repo.create_file(
            DATA_FILE_PATH,
            "chore: initialize players.json",
            json.dumps(EMPTY_DATA, ensure_ascii=False, indent=2),
        )
    except GithubException as e:
        st.warning(f"초기 파일 생성 실패: {str(e)}")


def save_players(players: list, commit_message: str = "update: players data") -> bool:
    """
    플레이어 리스트를 GitHub 저장소의 data/players.json에 저장(커밋).
    반환: 성공 여부 (bool)
    """
    try:
        repo = _get_repo()
        data = json.dumps({"players": players}, ensure_ascii=False, indent=2)

        try:
            # 기존 파일 sha 가져오기 (업데이트용)
            contents = repo.get_contents(DATA_FILE_PATH)
            repo.update_file(
                DATA_FILE_PATH,
                commit_message,
                data,
                contents.sha,
            )
        except GithubException as e:
            if e.status == 404:
                # 파일 없으면 새로 생성
                repo.create_file(DATA_FILE_PATH, commit_message, data)
            else:
                raise

        return True
    except Exception as e:
        st.error(f"데이터 저장 오류: {str(e)}")
        return False


def add_player(player: dict) -> bool:
    """
    새 플레이어를 목록에 추가하고 저장.
    동일 puuid가 이미 존재하면 업데이트.
    반환: 성공 여부 (bool)
    """
    players = load_players()
    existing_ids = {p["puuid"]: i for i, p in enumerate(players)}

    if player["puuid"] in existing_ids:
        # 기존 플레이어 솔로랭 정보만 갱신 (내전 전적은 보존)
        idx = existing_ids[player["puuid"]]
        players[idx]["solo_tier"] = player["solo_tier"]
        players[idx]["solo_rank"] = player["solo_rank"]
        players[idx]["solo_lp"]   = player["solo_lp"]
        players[idx]["mmr"]       = player["mmr"]
        msg = f"update: {player['name']} tier sync"
    else:
        players.append(player)
        msg = f"feat: add player {player['name']}#{player['tag']}"

    return save_players(players, commit_message=msg)


def update_inhouse_result(
    puuid: str,
    result: str,          # "WIN" or "LOSS"
    position: str,        # "TOP", "JNG", "MID", "ADC", "SUP"
    win_position: bool,   # 해당 포지션에서 이겼는지
) -> bool:
    """
    내전 결과(승/패/포지션)를 해당 플레이어의 inhouse_stats에 반영하고 저장.
    반환: 성공 여부 (bool)
    """
    from riot_api import calculate_mmr

    players = load_players()
    for player in players:
        if player["puuid"] == puuid:
            stats = player.setdefault("inhouse_stats", {
                "win": 0, "loss": 0,
                "positions": {p: 0 for p in ["TOP", "JNG", "MID", "ADC", "SUP"]},
                "position_wins": {p: 0 for p in ["TOP", "JNG", "MID", "ADC", "SUP"]},
            })
            # 기본 구조 보정 (구버전 데이터 호환)
            stats.setdefault("position_wins", {p: 0 for p in ["TOP", "JNG", "MID", "ADC", "SUP"]})

            if result == "WIN":
                stats["win"]  = stats.get("win", 0) + 1
            else:
                stats["loss"] = stats.get("loss", 0) + 1

            stats["positions"][position] = stats["positions"].get(position, 0) + 1
            if result == "WIN":
                stats["position_wins"][position] = stats["position_wins"].get(position, 0) + 1

            # MMR 재계산
            player["mmr"] = calculate_mmr(
                player["solo_tier"],
                player["solo_rank"],
                player["solo_lp"],
                stats.get("win", 0),
                stats.get("loss", 0),
            )
            break

    return save_players(
        players,
        commit_message=f"update: inhouse result for {puuid[:8]}",
    )


def delete_player(puuid: str) -> bool:
    """플레이어를 목록에서 삭제하고 저장"""
    players = load_players()
    players = [p for p in players if p["puuid"] != puuid]
    return save_players(players, commit_message=f"delete: player {puuid[:8]}")


if __name__ == "__main__":
    print("[테스트] players.json 로드 중...")
    data = load_players()
    print(f"플레이어 수: {len(data)}")
    for p in data:
        print(f"  - {p['name']}#{p['tag']} | {p['solo_tier']} {p.get('solo_rank','')} | MMR {p['mmr']}")
