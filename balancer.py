"""
balancer.py
팀 밸런싱 알고리즘 모듈
- MMR 기반 랜덤 팀 구성 (Tolerance 로직)
- 포지션 최적화 팀 구성 (5! 순열 탐색)
"""

import random
from itertools import combinations, permutations

POSITIONS = ["TOP", "JNG", "MID", "ADC", "SUP"]


# ─── MMR 기반 랜덤 팀 구성 ─────────────────────────────────────

def find_balanced_teams(players: list, tolerance: int = 100) -> dict:
    """
    10명의 플레이어에서 MMR 합 차이가 최소 + tolerance 이내인
    5:5 조합 중 하나를 무작위로 선택하여 반환.

    반환 형태:
    {
        "blue": [player, ...],   # 5명
        "red":  [player, ...],   # 5명
        "blue_mmr": int,
        "red_mmr":  int,
        "diff":     int,
    }
    """
    if len(players) != 10:
        raise ValueError(f"정확히 10명의 플레이어가 필요합니다. (현재 {len(players)}명)")

    indices = list(range(10))
    # 10 C 5 = 252 가지 조합 생성
    all_combos = list(combinations(indices, 5))

    best_diff = float("inf")
    candidates = []

    for combo in all_combos:
        blue_idx = list(combo)
        red_idx  = [i for i in indices if i not in blue_idx]

        blue_mmr = sum(players[i]["mmr"] for i in blue_idx)
        red_mmr  = sum(players[i]["mmr"] for i in red_idx)
        diff = abs(blue_mmr - red_mmr)

        if diff < best_diff:
            best_diff = diff
            candidates = [(blue_idx, red_idx, blue_mmr, red_mmr, diff)]
        elif diff <= best_diff + tolerance:
            candidates.append((blue_idx, red_idx, blue_mmr, red_mmr, diff))

    # 후보군 중 무작위 선택
    chosen = random.choice(candidates)
    blue_idx, red_idx, blue_mmr, red_mmr, diff = chosen

    return {
        "blue":     [players[i] for i in blue_idx],
        "red":      [players[i] for i in red_idx],
        "blue_mmr": blue_mmr,
        "red_mmr":  red_mmr,
        "diff":     diff,
    }


# ─── 포지션 최적화 ──────────────────────────────────────────────

def _best_position_assignment(team: list) -> dict:
    """
    팀 내 5명에게 포지션을 배정할 때, 각 플레이어의 포지션 숙련도(게임 수) 합이
    최대가 되는 순열을 반환.

    반환: {player_name: position, ...}
    """
    best_score = -1
    best_assign = {}

    for perm in permutations(POSITIONS):
        # perm[i] → team[i]에게 배정할 포지션
        score = 0
        for player, pos in zip(team, perm):
            positions_played = player.get("inhouse_stats", {}).get("positions", {})
            score += positions_played.get(pos, 0)

        if score > best_score:
            best_score = score
            best_assign = {
                player["name"]: pos
                for player, pos in zip(team, perm)
            }

    return best_assign


def find_balanced_teams_with_positions(players: list, tolerance: int = 100) -> dict:
    """
    MMR 기반 밸런스 팀 구성 후, 각 팀 내부에서 포지션 최적화까지 적용.

    반환 형태:
    {
        "blue": [player, ...],
        "red":  [player, ...],
        "blue_mmr": int,
        "red_mmr":  int,
        "diff":     int,
        "blue_positions": {name: position, ...},
        "red_positions":  {name: position, ...},
    }
    """
    result = find_balanced_teams(players, tolerance)

    blue_positions = _best_position_assignment(result["blue"])
    red_positions  = _best_position_assignment(result["red"])

    result["blue_positions"] = blue_positions
    result["red_positions"]  = red_positions

    return result


# ─── 포지션별 승률 계산 ─────────────────────────────────────────

def get_position_winrates(player: dict) -> dict:
    """
    플레이어의 포지션별 승률 계산.
    반환: {"TOP": 0.6, "JNG": 0.4, ...}  (게임 없으면 None)
    """
    stats = player.get("inhouse_stats", {})
    positions_played = stats.get("positions", {})
    position_wins    = stats.get("position_wins", {})
    result = {}
    for pos in POSITIONS:
        played = positions_played.get(pos, 0)
        wins   = position_wins.get(pos, 0)
        result[pos] = round(wins / played, 3) if played > 0 else None
    return result


def get_most_played_position(player: dict) -> str:
    """가장 많이 플레이한 포지션 반환 (없으면 '없음')"""
    positions_played = player.get("inhouse_stats", {}).get("positions", {})
    if not any(positions_played.values()):
        return "없음"
    return max(positions_played, key=lambda p: positions_played.get(p, 0))


if __name__ == "__main__":
    # 더미 플레이어 10명으로 테스트
    import random as _r
    _r.seed(42)

    dummy_players = []
    for i in range(10):
        mmr = _r.randint(800, 2400)
        dummy_players.append({
            "name": f"Player{i+1}",
            "mmr": mmr,
            "inhouse_stats": {
                "win": _r.randint(0, 10),
                "loss": _r.randint(0, 10),
                "positions": {p: _r.randint(0, 5) for p in POSITIONS},
                "position_wins": {p: _r.randint(0, 3) for p in POSITIONS},
            }
        })

    print("=== 랜덤 팀 구성 ===")
    res = find_balanced_teams(dummy_players)
    print(f"블루팀 MMR: {res['blue_mmr']}  vs  레드팀 MMR: {res['red_mmr']}  (차이: {res['diff']})")
    print("블루팀:", [p["name"] for p in res["blue"]])
    print("레드팀:", [p["name"] for p in res["red"]])

    print("\n=== 포지션 고정 팀 구성 ===")
    res2 = find_balanced_teams_with_positions(dummy_players)
    print(f"블루팀 MMR: {res2['blue_mmr']}  vs  레드팀 MMR: {res2['red_mmr']}  (차이: {res2['diff']})")
    print("블루팀 포지션:", res2["blue_positions"])
    print("레드팀 포지션:", res2["red_positions"])
