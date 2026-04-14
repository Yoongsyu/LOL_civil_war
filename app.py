"""
app.py
롤 내전 관리 시스템 - 메인 Streamlit 앱
기능 1~8 구현
"""

import json
import uuid
import time
from datetime import datetime

import streamlit as st
from github import GithubException

from github_utils import load_players, add_player, save_players, delete_player
from riot_api import (
    fetch_player_data,
    tier_label,
    tier_emoji,
    calculate_mmr,
    POSITIONS,
    get_league_entries_by_puuid,
)
from balancer import (
    find_balanced_teams,
    find_balanced_teams_with_positions,
    get_most_played_position,
)

# ─── 상수 ─────────────────────────────────────────────────────────
MATCHES_FILE = "data/matches.json"
POSITION_KR = {"TOP": "탑", "JNG": "정글", "MID": "미드", "ADC": "원딜", "SUP": "서포터"}

# 티어+랭크별 MMR (base + rank_offset + 평균 LP 50)
# 각 항목: (표시 레이블, tier, rank, mmr)
_TIER_BASE = [
    ("IRON", 0), ("BRONZE", 400), ("SILVER", 800), ("GOLD", 1200),
    ("PLATINUM", 1600), ("EMERALD", 2000), ("DIAMOND", 2400),
]
_RANK_OFFSET = {"IV": 0, "III": 100, "II": 200, "I": 300}

TIER_RANK_OPTIONS: list[tuple[str, str, str, int]] = []
for _tier, _base in _TIER_BASE:
    for _rank in ["IV", "III", "II", "I"]:
        _mmr = _base + _RANK_OFFSET[_rank] + 50
        TIER_RANK_OPTIONS.append((f"{_tier.capitalize()} {_rank}", _tier, _rank, _mmr))

# 마스터 이상은 랭크 구분 없음, LP 추정값 사용
TIER_RANK_OPTIONS += [
    ("Master",      "MASTER",      "", 2850),
    ("Grandmaster", "GRANDMASTER", "", 3300),
    ("Challenger",  "CHALLENGER",  "", 3900),
]

# (tier, rank) → 인덱스 역참조용
_TIER_RANK_INDEX = {
    (opt[1], opt[2]): i for i, opt in enumerate(TIER_RANK_OPTIONS)
}

# ─── 페이지 설정 ──────────────────────────────────────────────────
st.set_page_config(
    page_title="LoL 내전 관리",
    page_icon="⚔️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── 별수호자 테마 CSS ────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600;700&family=Noto+Sans+KR:wght@300;400;500;700&display=swap');

.stApp {
    background-color: #F8FAFC;
    color: #1E293B;
    font-family: 'Noto Sans KR', sans-serif;
}
.main .block-container {
    background: rgba(255,255,255,0.95);
    border-radius: 12px;
    padding: 1.2rem 2rem 2rem !important;
    max-width: 1200px;
    box-shadow: 0 4px 24px rgba(15,23,42,0.06);
}
h2, h3 {
    font-family: 'Cinzel', serif !important;
    color: #334155 !important;
    letter-spacing: 2px;
}
.stTabs [data-baseweb="tab-list"] {
    background: rgba(255,255,255,0.7);
    border-bottom: 2px solid rgba(51,65,85,0.15);
    gap: 0;
}
.stTabs [data-baseweb="tab"] {
    color: #64748B !important;
    font-family: 'Cinzel', serif;
    font-size: 0.8rem;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    padding: 0.65rem 1.4rem;
    border-radius: 0 !important;
    border-bottom: 3px solid transparent;
    background: transparent !important;
    transition: all 0.2s;
}
.stTabs [data-baseweb="tab"]:hover { color: #0F172A !important; }
.stTabs [aria-selected="true"] {
    color: #0F172A !important;
    border-bottom: 3px solid #3B82F6 !important;
    background: rgba(59,130,246,0.05) !important;
}
.stTabs [data-baseweb="tab-panel"] { background: transparent; padding-top: 1rem; }
.stButton > button {
    background: #FFFFFF;
    color: #334155;
    border: 1px solid #E2E8F0;
    border-radius: 6px;
    font-family: 'Noto Sans KR', sans-serif;
    font-size: 0.82rem;
    padding: 0.35rem 0.9rem;
    transition: all 0.18s ease;
    box-shadow: 0 1px 3px rgba(15,23,42,0.05);
}
.stButton > button:hover {
    background: #F8FAFC;
    border-color: #CBD5E1;
    box-shadow: 0 2px 6px rgba(15,23,42,0.1);
}
.stButton > button[kind="primary"] {
    background: linear-gradient(180deg, #3B82F6 0%, #2563EB 100%);
    color: #FFFFFF !important;
    font-weight: 700;
    border: none;
    box-shadow: 0 4px 12px rgba(37,99,235,0.3);
}
.stButton > button[kind="primary"]:hover {
    background: linear-gradient(180deg, #60A5FA 0%, #3B82F6 100%);
    box-shadow: 0 6px 16px rgba(37,99,235,0.4);
}
.stTextInput input, .stNumberInput input {
    background: #FFFFFF !important;
    color: #1E293B !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 6px !important;
}
.stTextInput input:focus, .stNumberInput input:focus {
    border-color: #3B82F6 !important;
    box-shadow: 0 0 0 2px rgba(59,130,246,0.2) !important;
}
.stTextInput input::placeholder { color: #94A3B8 !important; }
.stSelectbox > div > div {
    background: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 6px !important;
    color: #1E293B !important;
}
.stSelectbox > div > div:focus-within { border-color: #3B82F6 !important; }
[data-baseweb="popover"] { background: #FFFFFF !important; border: 1px solid #E2E8F0 !important; }
[data-baseweb="menu"]    { background: #FFFFFF !important; }
[data-baseweb="option"]  { background: #FFFFFF !important; color: #334155 !important; }
[data-baseweb="option"]:hover, [data-baseweb="option"][aria-selected="true"] {
    background: #F1F5F9 !important; color: #0F172A !important;
}
.stSlider [data-baseweb="slider"] div[role="slider"] { background: #3B82F6 !important; border: 2px solid #FFFFFF !important; }
.stSlider [data-testid="stSliderTrackActive"] { background: #93C5FD !important; }
.stRadio label { color: #334155 !important; }
.stRadio [data-baseweb="radio"] div { border-color: #CBD5E1 !important; }
.stRadio [aria-checked="true"] div { background: #3B82F6 !important; border-color: #3B82F6 !important; }
.stCheckbox label { color: #334155 !important; }
.stCheckbox [data-baseweb="checkbox"] div { border-color: #CBD5E1 !important; background: #FFFFFF !important; }
.stCheckbox [aria-checked="true"] div { background: #3B82F6 !important; border-color: #3B82F6 !important; }
.stExpander { border: 1px solid #E2E8F0 !important; border-radius: 6px !important; background: #F8FAFC !important; }
.stExpander summary { color: #475569 !important; font-size: 0.85rem; }
.stExpander summary:hover { color: #0F172A !important; }
div[data-testid="stNotification"] {
    background: #F8FAFC !important;
    border: 1px solid #E2E8F0 !important;
    border-left: 3px solid #3B82F6 !important;
    color: #1E293B !important;
    border-radius: 6px !important;
}
hr { border-color: #E2E8F0 !important; margin: 1em 0; }
p, span, label, .stMarkdown { color: #334155; }
.stCaption, small { color: #64748B !important; font-size: 0.78rem; }
.stDataFrame { border: 1px solid #E2E8F0; border-radius: 6px; }
.stDataFrame thead tr th {
    background: #F1F5F9 !important; color: #334155 !important;
    font-family: 'Cinzel', serif; font-size: 0.76rem; letter-spacing: 1px;
    border-bottom: 1px solid #E2E8F0 !important;
}
.stDataFrame tbody tr td { background: #FFFFFF !important; color: #1E293B !important; }
.stDataFrame tbody tr:hover td { background: #F8FAFC !important; }
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: #F1F5F9; }
::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #94A3B8; }

/* 플레이어 목록 테이블 테두리를 위한 커스텀 스타일 */
div[data-testid="stVerticalBlockBorderWrapper"] {
    border: 1px solid #E2E8F0 !important;
    border-radius: 8px !important;
    background: #FFFFFF !important;
    padding: 1rem !important;
    overflow: hidden;
    box-shadow: 0 1px 3px rgba(15,23,42,0.03);
}

/* ── 모바일 반응형 ── */
@media (max-width: 768px) {
    .main .block-container {
        padding: 0.6rem 0.8rem 1.5rem !important;
        max-width: 100% !important;
    }
    /* 컬럼 자동 줄바꿈 */
    [data-testid="stHorizontalBlock"] {
        flex-wrap: wrap !important;
    }
    [data-testid="column"] {
        min-width: min(100%, 280px) !important;
        flex: 1 1 280px !important;
    }
    /* 탭 레이블 크기 축소 */
    .stTabs [data-baseweb="tab"] {
        font-size: 0.62rem !important;
        padding: 0.5rem 0.55rem !important;
        letter-spacing: 0.3px !important;
    }
    /* 타이틀 배너 */
    div[style*="font-size:2.1rem"] { font-size: 1.3rem !important; letter-spacing: 3px !important; }
    /* 버튼 */
    .stButton > button { font-size: 0.78rem !important; padding: 0.3rem 0.6rem !important; }
    /* 헤더 */
    h2, h3 { font-size: 1.05rem !important; letter-spacing: 1px !important; }
    p, span, label, .stMarkdown { font-size: 0.82rem !important; }
    /* 슬라이더 레이블 */
    .stSlider label { font-size: 0.78rem !important; }
    /* expander */
    .stExpander summary { font-size: 0.8rem !important; }
}
@media (max-width: 480px) {
    [data-testid="column"] {
        min-width: 100% !important;
        flex: 1 1 100% !important;
    }
    .stTabs [data-baseweb="tab"] {
        font-size: 0.58rem !important;
        padding: 0.45rem 0.4rem !important;
    }
}
</style>
""", unsafe_allow_html=True)

# ─── 타이틀 배너 ──────────────────────────────────────────────────
st.html("""
<div style="text-align:center; padding:1.6rem 0 1.1rem; border-bottom:1px solid #E2E8F0; margin-bottom:0.5rem;">
    <div style="font-family:'Cinzel',serif; font-size:2.1rem; font-weight:700; color:#1E293B; letter-spacing:8px; text-transform:uppercase; text-shadow:0 2px 8px rgba(15,23,42,0.1);">
        ✦ &nbsp; 내전 관리 시스템 &nbsp; ✦
    </div>
    <div style="font-family:'Noto Sans KR',sans-serif; font-size:0.72rem; color:#64748B; letter-spacing:5px; margin-top:0.4rem;">
        LEAGUE OF LEGENDS &nbsp;·&nbsp; CUSTOM MATCH SYSTEM
    </div>
    <div style="width:50%; height:1px; margin:0.7rem auto 0; background:linear-gradient(90deg,transparent,#CBD5E1,#94A3B8,#CBD5E1,transparent);"></div>
</div>
""")

# ─── 세션 초기화 ──────────────────────────────────────────────────
if "admin_authed" not in st.session_state:
    st.session_state.admin_authed = False
if "team_result" not in st.session_state:
    st.session_state.team_result = None
# 이전 세션의 4-tuple 형식 호환 처리
if isinstance(st.session_state.team_result, tuple) and len(st.session_state.team_result) == 4:
    st.session_state.team_result = None
if "chk_reset_count" not in st.session_state:
    st.session_state.chk_reset_count = 0
if "chk_all_default" not in st.session_state:
    st.session_state.chk_all_default = False


# ─── matches.json 유틸리티 ────────────────────────────────────────

def _get_repo():
    from github import Github
    token = st.secrets.get("GITHUB_TOKEN", "")
    repo_name = st.secrets.get("REPO_NAME", "")
    return Github(token).get_repo(repo_name)


def load_matches() -> list:
    try:
        repo = _get_repo()
        try:
            contents = repo.get_contents(MATCHES_FILE)
            data = json.loads(contents.decoded_content.decode("utf-8"))
            return data.get("matches", [])
        except GithubException as e:
            if e.status == 404:
                return []
            raise
    except Exception as e:
        st.error(f"경기 기록 로드 오류: {str(e)}")
        return []


def save_matches(matches: list, commit_msg: str = "update: matches data") -> bool:
    try:
        repo = _get_repo()
        data = json.dumps({"matches": matches}, ensure_ascii=False, indent=2)
        try:
            contents = repo.get_contents(MATCHES_FILE)
            repo.update_file(MATCHES_FILE, commit_msg, data, contents.sha)
        except GithubException as e:
            if e.status == 404:
                repo.create_file(MATCHES_FILE, commit_msg, data)
            else:
                raise
        return True
    except Exception as e:
        st.error(f"경기 기록 저장 오류: {str(e)}")
        return False


def record_match_batch(blue_team, red_team, winner, positions, champions=None) -> bool:
    """
    모든 플레이어 stats 일괄 업데이트 + matches.json 저장 (총 2회 GitHub 커밋)
    positions: {puuid: position_str}
    champions: {puuid: champion_name}  (optional)
    winner: "blue" or "red"
    """
    if champions is None:
        champions = {}
    players = load_players()
    player_map = {p["puuid"]: p for p in players}

    match_id = str(uuid.uuid4())[:8]
    match_record = {
        "id": match_id,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "blue_team": [],
        "red_team": [],
        "winner": winner,
    }

    for side, team in [("blue", blue_team), ("red", red_team)]:
        is_win = side == winner
        for pi in team:
            puuid = pi["puuid"]
            pos = positions.get(puuid, "TOP")
            if puuid in player_map:
                p = player_map[puuid]
                stats = p.setdefault("inhouse_stats", {
                    "win": 0, "loss": 0,
                    "positions": {x: 0 for x in POSITIONS},
                    "position_wins": {x: 0 for x in POSITIONS},
                })
                stats.setdefault("position_wins", {x: 0 for x in POSITIONS})
                if is_win:
                    stats["win"] = stats.get("win", 0) + 1
                    stats["position_wins"][pos] = stats["position_wins"].get(pos, 0) + 1
                else:
                    stats["loss"] = stats.get("loss", 0) + 1
                stats["positions"][pos] = stats["positions"].get(pos, 0) + 1
                # 포지션별 챔피언 픽 카운트
                champ = champions.get(puuid, "")
                if champ:
                    pos_champs = stats.setdefault("position_champions", {})
                    pos_champs.setdefault(pos, {})
                    pos_champs[pos][champ] = pos_champs[pos].get(champ, 0) + 1
                win_cnt  = stats.get("win", 0)
                loss_cnt = stats.get("loss", 0)
                total    = win_cnt + loss_cnt
                solo_mmr = p.get("solo_mmr", calculate_mmr(
                    p["solo_tier"], p.get("solo_rank", ""), p.get("solo_lp", 0), 0, 0
                ))
                inhouse_adj = int((win_cnt / total - 0.5) * 300) if total >= 5 else 0
                p["mmr"] = max(0, solo_mmr + inhouse_adj)
            match_record[f"{side}_team"].append({
                "puuid":    puuid,
                "name":     pi["name"],
                "tag":      pi.get("tag", ""),
                "position": pos,
                "champion": champions.get(puuid, ""),
            })

    ok1 = save_players(list(player_map.values()), commit_message=f"update: match {match_id}")
    matches = load_matches()
    matches.insert(0, match_record)
    ok2 = save_matches(matches, commit_msg=f"feat: add match {match_id}")
    return ok1 and ok2


def revert_match(match: dict) -> bool:
    """경기 삭제 시 해당 경기의 stats를 전원에서 차감 후 저장"""
    players = load_players()
    player_map = {p["puuid"]: p for p in players}

    for side, team in [("blue", match["blue_team"]), ("red", match["red_team"])]:
        is_win = side == match["winner"]
        for pi in team:
            puuid = pi["puuid"]
            pos = pi.get("position", "TOP")
            if puuid not in player_map:
                continue
            p = player_map[puuid]
            stats = p.get("inhouse_stats", {})
            if not stats:
                continue
            if is_win:
                stats["win"] = max(0, stats.get("win", 0) - 1)
                pw = stats.get("position_wins", {})
                pw[pos] = max(0, pw.get(pos, 0) - 1)
                stats["position_wins"] = pw
            else:
                stats["loss"] = max(0, stats.get("loss", 0) - 1)
            pp = stats.get("positions", {})
            pp[pos] = max(0, pp.get(pos, 0) - 1)
            stats["positions"] = pp
            # 포지션별 챔피언 픽 카운트 차감
            champ = pi.get("champion", "")
            if champ:
                pos_champs = stats.get("position_champions", {})
                if pos_champs.get(pos, {}).get(champ, 0) > 0:
                    pos_champs[pos][champ] -= 1
                    if pos_champs[pos][champ] == 0:
                        del pos_champs[pos][champ]
            win_cnt  = stats.get("win", 0)
            loss_cnt = stats.get("loss", 0)
            total    = win_cnt + loss_cnt
            solo_mmr = p.get("solo_mmr", calculate_mmr(
                p["solo_tier"], p.get("solo_rank", ""), p.get("solo_lp", 0), 0, 0
            ))
            inhouse_adj = int((win_cnt / total - 0.5) * 300) if total >= 5 else 0
            p["mmr"] = max(0, solo_mmr + inhouse_adj)

    return save_players(
        list(player_map.values()),
        commit_message=f"revert: match {match['id']}",
    )


# ─── 캐시된 로더 ─────────────────────────────────────────────────

@st.cache_data(ttl=300)
def get_players_cached():
    return load_players()


@st.cache_data(ttl=300)
def get_matches_cached():
    return load_matches()


@st.cache_data(ttl=3600 * 24)  # 24시간 캐시 (챔피언 목록은 자주 안 바뀜)
def get_champion_list() -> list[str]:
    """Riot Data Dragon에서 최신 챔피언 목록(한국어)을 가져옴. 실패 시 빈 목록."""
    try:
        import requests as _req
        ver = _req.get(
            "https://ddragon.leagueoflegends.com/api/versions.json", timeout=5
        ).json()[0]
        data = _req.get(
            f"https://ddragon.leagueoflegends.com/cdn/{ver}/data/ko_KR/champion.json",
            timeout=10,
        ).json()
        names = sorted(c["name"] for c in data["data"].values())
        return [""] + names          # 첫 항목 빈 문자열 = 선택 안 함
    except Exception:
        return [""]


@st.cache_data(ttl=3600 * 24)
def get_champion_url_map() -> dict[str, str]:
    """한국어 챔피언 이름 → Data Dragon 이미지 URL 매핑. 실패 시 빈 딕셔너리."""
    try:
        import requests as _req
        ver = _req.get(
            "https://ddragon.leagueoflegends.com/api/versions.json", timeout=5
        ).json()[0]
        data = _req.get(
            f"https://ddragon.leagueoflegends.com/cdn/{ver}/data/ko_KR/champion.json",
            timeout=10,
        ).json()
        base = f"https://ddragon.leagueoflegends.com/cdn/{ver}/img/champion/"
        return {c["name"]: base + c["image"]["full"] for c in data["data"].values()}
    except Exception:
        return {}


# ─── UI 헬퍼 ─────────────────────────────────────────────────────

_TIER_BADGE_COLORS = {
    "IRON":        ("#6B7280", "#F3F4F6"),
    "BRONZE":      ("#92400E", "#FEF3C7"),
    "SILVER":      ("#475569", "#F1F5F9"),
    "GOLD":        ("#854D0E", "#FEF9C3"),
    "PLATINUM":    ("#0F766E", "#CCFBF1"),
    "EMERALD":     ("#166534", "#DCFCE7"),
    "DIAMOND":     ("#1D4ED8", "#DBEAFE"),
    "MASTER":      ("#7C3AED", "#EDE9FE"),
    "GRANDMASTER": ("#B91C1C", "#FEE2E2"),
    "CHALLENGER":  ("#92400E", "#FEF3C7"),
    "UNRANKED":    ("#64748B", "#F8FAFC"),
}


def tier_badge_html(tier: str, rank: str = "", lp: int = 0, font_size: str = "0.75rem") -> str:
    """티어를 색상 배지 HTML로 반환"""
    text_color, bg_color = _TIER_BADGE_COLORS.get(tier.upper(), ("#64748B", "#F8FAFC"))
    label = tier_label(tier, rank, lp)
    emoji = tier_emoji(tier)
    return (
        f"<span style='background:{bg_color};color:{text_color};"
        f"border:1px solid {text_color}33;border-radius:4px;"
        f"padding:2px 7px;font-size:{font_size};font-weight:600;"
        f"white-space:nowrap;display:inline-block;'>{emoji} {label}</span>"
    )


def with_pure_mmr(players: list) -> list:
    """솔랭 MMR만으로 팀 구성할 때 사용하는 복사본 반환 (내전 보정치 제외)"""
    result = []
    for p in players:
        copy = dict(p)
        # solo_mmr 필드가 있으면 그대로, 없으면 tier 기반 재계산
        copy["mmr"] = p.get("solo_mmr", calculate_mmr(
            p.get("solo_tier", "UNRANKED"),
            p.get("solo_rank", ""),
            p.get("solo_lp", 0),
            0, 0,
        ))
        result.append(copy)
    return result


def show_player_detail(player: dict):
    """플레이어 상세 정보 렌더링 (포지션별 / 챔피언별 탭)"""
    import pandas as pd

    stats = player.get("inhouse_stats", {})
    win = stats.get("win", 0)
    loss = stats.get("loss", 0)
    total = win + loss
    wr = f"{win / total * 100:.1f}%" if total > 0 else "-"
    most = get_most_played_position(player)
    solo_mmr = player.get("solo_mmr", player.get("mmr", 0))
    final_mmr = player.get("mmr", solo_mmr)
    adj = final_mmr - solo_mmr
    adj_str = f" ({'+' if adj >= 0 else ''}{adj:,})" if adj != 0 else ""
    badge = tier_badge_html(player["solo_tier"], player.get("solo_rank", ""), player.get("solo_lp", 0))

    # 요약 한 줄
    st.markdown(
        f"{badge}&ensp;"
        f"솔랭 MMR **{solo_mmr:,}**&ensp;|&ensp;"
        f"내전 MMR **{final_mmr:,}**{adj_str}&ensp;|&ensp;"
        f"승률 **{wr}** ({win}승 {loss}패 {total}판)&ensp;|&ensp;"
        f"모스트 **{POSITION_KR.get(most, most)}**",
        unsafe_allow_html=True,
    )

    if total == 0:
        return

    # ── 포지션별 / 챔피언별 탭 ────────────────────────────────────
    puuid = player["puuid"]
    view = st.radio(
        "통계 보기",
        ["포지션별 승률", "챔피언별 승률"],
        horizontal=True,
        key=f"detail_view_{puuid}",
        label_visibility="collapsed",
    )

    if view == "포지션별 승률":
        pos_champs = stats.get("position_champions", {})
        rows = []
        for pos in POSITIONS:
            played = stats.get("positions", {}).get(pos, 0)
            wins = stats.get("position_wins", {}).get(pos, 0)
            champ_counts = pos_champs.get(pos, {})
            most_champ = max(champ_counts, key=champ_counts.get) if champ_counts else "-"
            rows.append({
                "포지션": POSITION_KR[pos],
                "판수": played,
                "승": wins,
                "패": played - wins,
                "승률": f"{wins / played * 100:.1f}%" if played > 0 else "-",
                "모스트 챔피언": most_champ,
            })
        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
            height=210,
        )

    else:  # 챔피언별 승률
        matches = get_matches_cached()
        url_map = get_champion_url_map()

        # matches에서 이 플레이어의 챔피언별 승/패 집계
        champ_stats: dict[str, dict] = {}
        for m in matches:
            winner = m["winner"]
            for side in ["blue", "red"]:
                for pi in m.get(f"{side}_team", []):
                    if pi.get("puuid") != puuid:
                        continue
                    champ = pi.get("champion", "")
                    if not champ:
                        continue
                    if champ not in champ_stats:
                        champ_stats[champ] = {"win": 0, "loss": 0}
                    if side == winner:
                        champ_stats[champ]["win"] += 1
                    else:
                        champ_stats[champ]["loss"] += 1

        if not champ_stats:
            st.caption("챔피언 기록이 없습니다. (전적 입력 시 챔피언을 선택해야 집계됩니다)")
            return

        # 판수 내림차순 정렬
        sorted_champs = sorted(
            champ_stats.items(),
            key=lambda x: -(x[1]["win"] + x[1]["loss"]),
        )

        # 전체 카드를 하나의 스크롤 박스로 렌더링 (4~5줄 고정 높이)
        cards_html = ""
        for champ, s in sorted_champs:
            w, l = s["win"], s["loss"]
            t = w + l
            wr_val = w / t * 100
            wr_color = "#10B981" if wr_val >= 60 else "#EF4444" if wr_val < 40 else "#64748B"
            img_url = url_map.get(champ, "")
            img_html = (
                f"<img src='{img_url}' width='32' height='32' "
                f"style='border-radius:50%;border:2px solid #E2E8F0;"
                f"object-fit:cover;flex-shrink:0;'>"
                if img_url else
                f"<div style='width:32px;height:32px;border-radius:50%;"
                f"background:#F1F5F9;border:2px solid #E2E8F0;"
                f"display:flex;align-items:center;justify-content:center;"
                f"font-size:0.7rem;color:#94A3B8;flex-shrink:0;'>?</div>"
            )
            cards_html += (
                f"<div style='display:flex;align-items:center;gap:9px;"
                f"padding:0.32rem 0.5rem;border-bottom:1px solid #F1F5F9;'>"
                f"{img_html}"
                f"<div style='flex:1;font-weight:700;font-size:0.85rem;color:#1E293B;'>{champ}</div>"
                f"<div style='text-align:right;'>"
                f"<span style='font-size:0.78rem;color:#475569;'>{t}판 &nbsp;{w}승 {l}패</span><br>"
                f"<span style='font-size:0.85rem;font-weight:700;color:{wr_color};'>{wr_val:.1f}%</span>"
                f"</div>"
                f"</div>"
            )

        st.markdown(
            f"<div style='height:230px;overflow-y:auto;"
            f"border:1px solid #E2E8F0;border-radius:6px;"
            f"background:#FFFFFF;'>"
            f"{cards_html}"
            f"</div>",
            unsafe_allow_html=True,
        )


def _most_played_champ_for(player: dict, pos: str = "") -> str:
    """플레이어의 (포지션별) 모스트 챔피언 한국어 이름 반환. 없으면 빈 문자열."""
    pos_champs = player.get("inhouse_stats", {}).get("position_champions", {})
    if pos and pos_champs.get(pos):
        return max(pos_champs[pos], key=pos_champs[pos].get)
    # 포지션 미지정 시 전체 합산
    combined: dict[str, int] = {}
    for champ_dict in pos_champs.values():
        for champ, cnt in champ_dict.items():
            combined[champ] = combined.get(champ, 0) + cnt
    return max(combined, key=combined.get) if combined else ""


def show_team_result(result: dict, with_positions: bool):
    """팀 구성 결과를 블루/레드 2열로 카드 렌더링 (챔피언 초상화 포함)"""
    url_map = get_champion_url_map()
    col_b, col_r = st.columns(2)
    team_styles = [
        (col_b, "blue",  "🔵 블루팀", "#3B82F6", "#EFF6FF"),
        (col_r, "red",   "🔴 레드팀", "#EF4444", "#FFF5F5"),
    ]
    for col, side, label, border, bg in team_styles:
        with col:
            total_mmr = result[f"{side}_mmr"]
            st.markdown(
                f"<div style='background:{bg};border:2px solid {border};"
                f"border-radius:10px;padding:0.75rem 1rem 0.6rem;"
                f"margin-bottom:0.5rem;'>"
                f"<div style='font-size:1rem;font-weight:700;color:#1E293B;'>{label}</div>"
                f"<div style='font-size:0.75rem;color:#64748B;margin-top:2px;'>"
                f"총 MMR <b>{total_mmr:,}</b></div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            for p in result[side]:
                badge = tier_badge_html(p["solo_tier"], p.get("solo_rank", ""), p.get("solo_lp", 0))

                pos = ""
                pos_html = ""
                if with_positions:
                    pos = result.get(f"{side}_positions", {}).get(p["name"], "")
                    if pos:
                        pos_html = (
                            f"<span style='background:#F1F5F9;color:#475569;"
                            f"border-radius:4px;padding:1px 6px;font-size:0.7rem;"
                            f"font-weight:600;margin-left:5px;'>"
                            f"{POSITION_KR.get(pos, pos)}</span>"
                        )

                # 챔피언 초상화
                champ = _most_played_champ_for(p, pos)
                champ_url = url_map.get(champ, "") if champ else ""
                if champ_url:
                    champ_img_html = (
                        f"<img src='{champ_url}' width='44' height='44' "
                        f"style='border-radius:50%;border:2px solid #E2E8F0;"
                        f"object-fit:cover;flex-shrink:0;' "
                        f"title='{champ}'>"
                    )
                    champ_name_html = (
                        f"<div style='font-size:0.68rem;color:#94A3B8;"
                        f"text-align:center;margin-top:2px;white-space:nowrap;"
                        f"overflow:hidden;text-overflow:ellipsis;max-width:48px;'>"
                        f"{champ}</div>"
                    )
                    left_section = (
                        f"<div style='display:flex;flex-direction:column;"
                        f"align-items:center;margin-right:10px;flex-shrink:0;'>"
                        f"{champ_img_html}{champ_name_html}</div>"
                    )
                else:
                    left_section = (
                        f"<div style='width:44px;height:44px;border-radius:50%;"
                        f"background:#F1F5F9;border:2px solid #E2E8F0;"
                        f"display:flex;align-items:center;justify-content:center;"
                        f"margin-right:10px;flex-shrink:0;font-size:1.1rem;'>?</div>"
                    )

                st.markdown(
                    f"<div style='background:#FFFFFF;border:1px solid #E2E8F0;"
                    f"border-radius:8px;padding:0.55rem 0.85rem;"
                    f"margin-bottom:0.35rem;display:flex;"
                    f"align-items:center;'>"
                    f"{left_section}"
                    f"<div style='flex:1;min-width:0;'>"
                    f"<div style='font-weight:700;font-size:0.9rem;color:#1E293B;'>"
                    f"{p['name']}{pos_html}</div>"
                    f"<div style='margin-top:4px;'>{badge}</div>"
                    f"</div>"
                    f"<div style='text-align:right;flex-shrink:0;margin-left:8px;'>"
                    f"<div style='font-size:0.68rem;color:#94A3B8;'>MMR</div>"
                    f"<div style='font-size:0.95rem;font-weight:700;color:#334155;'>"
                    f"{p['mmr']:,}</div>"
                    f"</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

    diff = result["diff"]
    diff_color = "#10B981" if diff <= 100 else "#F59E0B" if diff <= 250 else "#EF4444"
    st.markdown(
        f"<div style='text-align:center;padding:0.55rem 1rem;"
        f"background:#F8FAFC;border:1px solid #E2E8F0;"
        f"border-radius:8px;margin-top:0.4rem;'>"
        f"<span style='color:{diff_color};font-weight:700;font-size:0.9rem;'>"
        f"MMR 차이: {diff:,}점</span>"
        f"</div>",
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════
# 메인 앱
# ══════════════════════════════════════════════════════════════════

tab1, tab2, tab3, tab4 = st.tabs(["🏠 플레이어 & 팀 구성", "➕ 플레이어 등록", "🔧 관리자", "🏆 리더보드"])


# ══════════════════════════════════════════════════════════════════
# TAB 1: 플레이어 리스트 (기능 1·2·3) + 팀 구성 (기능 4·5)
# ══════════════════════════════════════════════════════════════════
with tab1:
    hdr_col, refresh_col = st.columns([5, 1])
    with hdr_col:
        st.subheader("플레이어 목록")
    with refresh_col:
        if st.button("🔄 새로고침", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    players = get_players_cached()

    if not players:
        st.info("등록된 플레이어가 없습니다. '플레이어 등록' 탭에서 먼저 추가해주세요.")
    else:
        # ── 기능 1·2·3: 리스트 + 티어 + 상세 정보 ─────────────────
        # ── 정렬 옵션 ─────────────────────────────────────────────
        sort_col, _ = st.columns([2, 5])
        with sort_col:
            sort_by = st.selectbox(
                "정렬 기준",
                ["내전 MMR 높은순", "내전 MMR 낮은순", "솔랭 MMR 높은순", "솔랭 MMR 낮은순",
                 "이름순", "승률 높은순", "승률 낮은순", "내전 판수 많은순"],
                label_visibility="collapsed",
                key="player_sort",
            )

        def _sort_key(p):
            stats = p.get("inhouse_stats", {})
            win = stats.get("win", 0)
            loss = stats.get("loss", 0)
            total = win + loss
            wr = win / total if total > 0 else 0.0
            smr = p.get("solo_mmr", p.get("mmr", 0))
            mmr = p.get("mmr", smr)
            name = p.get("name", "")
            if sort_by == "내전 MMR 높은순":   return -mmr
            if sort_by == "내전 MMR 낮은순":   return mmr
            if sort_by == "솔랭 MMR 높은순":   return -smr
            if sort_by == "솔랭 MMR 낮은순":   return smr
            if sort_by == "이름순":            return name
            if sort_by == "승률 높은순":        return -wr
            if sort_by == "승률 낮은순":        return wr
            if sort_by == "내전 판수 많은순":   return -total
            return -mmr

        players = sorted(players, key=_sort_key)

        with st.container(border=True):
            # 헤더 행
            h_chk, h_name, h_tier, h_solo, h_inhouse, h_record = st.columns([0.5, 2.2, 1.8, 1.4, 1.4, 1.8])
            with h_chk:
                select_all = st.checkbox(
                    "전체",
                    value=st.session_state.chk_all_default,
                    key=f"chk_all_{st.session_state.chk_reset_count}",
                    label_visibility="collapsed",
                )
                if select_all != st.session_state.chk_all_default:
                    st.session_state.chk_reset_count += 1
                    st.session_state.chk_all_default = select_all
                    st.rerun()
            h_name.markdown("**닉네임**")
            h_tier.markdown("**솔랭 티어**")
            h_solo.markdown("**솔랭 MMR**")
            h_inhouse.markdown("**내전 MMR**")
            h_record.markdown("**내전 전적**")

            hr_html = "<hr style='margin: 0.5rem 0; padding: 0; border: none; border-bottom: 1px solid #E2E8F0;'>"

            for player in players:
                st.markdown(hr_html, unsafe_allow_html=True)
                stats = player.get("inhouse_stats", {})
                win = stats.get("win", 0)
                loss = stats.get("loss", 0)
                total = win + loss
                wr_str = f"{win / total * 100:.0f}%" if total > 0 else "-"

                # 솔랭 MMR (solo_mmr 필드 없는 기존 데이터 호환)
                solo_mmr = player.get("solo_mmr", calculate_mmr(
                    player.get("solo_tier", "UNRANKED"),
                    player.get("solo_rank", ""),
                    player.get("solo_lp", 0), 0, 0,
                ))
                final_mmr = player.get("mmr", solo_mmr)
                adj = final_mmr - solo_mmr
                adj_str = f" ({'+' if adj >= 0 else ''}{adj:,})" if adj != 0 else ""

                # 요약 행
                c_chk, c_name, c_tier, c_solo, c_inhouse, c_rec = st.columns([0.5, 2.2, 1.8, 1.4, 1.4, 1.8])
                with c_chk:
                    st.checkbox(
                        "선택",
                        key=f"chk_{player['puuid']}_{st.session_state.chk_reset_count}",
                        value=st.session_state.chk_all_default,
                        label_visibility="collapsed",
                    )
                c_name.markdown(f"**{player['name']}**#{player.get('tag', '')}")
                c_tier.markdown(tier_badge_html(player["solo_tier"], player.get("solo_rank",""), player.get("solo_lp",0)), unsafe_allow_html=True)
                c_solo.markdown(f"**{solo_mmr:,}**")
                c_inhouse.markdown(f"**{final_mmr:,}**{adj_str}")
                c_rec.markdown(f"{win}승 {loss}패 ({total}판) {wr_str}")

                # 상세 정보 - 전체 너비 expander (컬럼 밖에 배치)
                with st.expander(f"📊 {player['name']} 상세 정보"):
                    show_player_detail(player)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── 기능 4·5: 팀 구성 ───────────────────────────────────
        st.subheader("팀 구성")

        selected_players = [
            p for p in players
            if st.session_state.get(f"chk_{p['puuid']}_{st.session_state.chk_reset_count}", False)
        ]
        selected_count = len(selected_players)

        tolerance = st.slider(
            "MMR 오차 허용 범위 (Tolerance)",
            min_value=0, max_value=500, value=100, step=50,
            help="이 값 이내의 MMR 차이를 가진 조합들 중 랜덤으로 팀을 구성합니다.",
        )

        mmr_mode = st.radio(
            "MMR 계산 방식",
            ["📊 내전 성적 반영 (솔랭 + 내전 승률 가중치)", "🎮 솔랭 MMR만 반영 (내전 성적 무시)"],
            horizontal=True,
            help="내전 성적 반영: 5판 이상 시 승률에 따라 ±150점 보정 / 솔랭 MMR만: 티어·랭크·LP만 사용",
        )
        use_pure_mmr = mmr_mode.startswith("🎮")

        col_btn1, col_btn2, col_reset = st.columns([2, 2, 1])
        with col_reset:
            if st.button("선택 초기화", use_container_width=True):
                st.session_state.chk_reset_count += 1
                st.session_state.chk_all_default = False
                st.session_state.team_result = None
                st.rerun()

        if selected_count != 10:
            st.warning(
                f"{selected_count}/10명 선택됨. 정확히 10명을 선택해야 팀 구성이 가능합니다."
            )
        else:
            target_players = with_pure_mmr(selected_players) if use_pure_mmr else selected_players

            with col_btn1:
                if st.button("⚡ 팀 구성하기", type="primary", use_container_width=True):
                    result = find_balanced_teams(target_players, tolerance=tolerance)
                    st.session_state.team_result = (
                        "random", result, selected_players, tolerance, use_pure_mmr
                    )

            with col_btn2:
                if st.button("📌 고정 포지션 팀 구성하기", use_container_width=True):
                    result = find_balanced_teams_with_positions(target_players, tolerance=tolerance)
                    st.session_state.team_result = (
                        "position", result, selected_players, tolerance, use_pure_mmr
                    )

        # 팀 구성 결과 표시
        if st.session_state.team_result:
            mode, result, saved_players, saved_tol, saved_pure = st.session_state.team_result
            st.markdown("---")
            st.subheader("팀 구성 결과")

            badge = "🎮 솔랭 MMR 기준" if saved_pure else "📊 내전 성적 반영 기준"
            st.caption(badge)

            show_team_result(result, with_positions=(mode == "position"))

            if st.button("🔀 다시 구성하기"):
                t = with_pure_mmr(saved_players) if saved_pure else saved_players
                if mode == "position":
                    new_result = find_balanced_teams_with_positions(t, tolerance=saved_tol)
                else:
                    new_result = find_balanced_teams(t, tolerance=saved_tol)
                st.session_state.team_result = (mode, new_result, saved_players, saved_tol, saved_pure)
                st.rerun()


# ══════════════════════════════════════════════════════════════════
# TAB 2: 플레이어 등록 (기능 6)
# ══════════════════════════════════════════════════════════════════
with tab2:
    st.subheader("플레이어 등록")
    st.markdown(
        "닉네임#태그를 입력하면 Riot API에서 솔랭 티어와 MMR을 자동으로 가져와 등록합니다."
    )

    with st.form("register_form"):
        riot_id = st.text_input("Riot ID", placeholder="Hide on bush#KR1")
        submitted = st.form_submit_button("등록하기", type="primary", use_container_width=True)

    if submitted:
        if not riot_id or "#" not in riot_id:
            st.error("닉네임과 태그를 '#'으로 구분하여 정확히 입력해주세요. (예: Hide on bush#KR1)")
        else:
            name_part, tag_part = riot_id.rsplit("#", 1)
            with st.spinner(f"{name_part}#{tag_part} 조회 중..."):
                player_data = fetch_player_data(name_part.strip(), tag_part.strip())

            if "error" in player_data:
                st.error(player_data["error"])
            else:
                with st.spinner("GitHub에 저장 중..."):
                    ok = add_player(player_data)

                if ok:
                    emoji = tier_emoji(player_data["solo_tier"])
                    tier_str = tier_label(
                        player_data["solo_tier"],
                        player_data.get("solo_rank", ""),
                        player_data.get("solo_lp", 0),
                    )
                    st.success(f"✅ **{player_data['name']}#{player_data['tag']}** 등록 완료!")
                    st.info(f"{emoji} {tier_str} | MMR {player_data['mmr']:,}")
                    st.cache_data.clear()
                else:
                    st.error("저장 중 오류가 발생했습니다.")


# ══════════════════════════════════════════════════════════════════
# TAB 3: 관리자 (기능 7·8)
# ══════════════════════════════════════════════════════════════════
with tab3:
    st.subheader("관리자 메뉴")

    # ── 관리자 인증 ───────────────────────────────────────────────
    if not st.session_state.admin_authed:
        with st.form("admin_login"):
            pw = st.text_input("관리자 비밀번호", type="password")
            login_ok = st.form_submit_button("인증", type="primary")
            if login_ok:
                if pw == st.secrets.get("ADMIN_PASSWORD", ""):
                    st.session_state.admin_authed = True
                    st.rerun()
                else:
                    st.error("비밀번호가 틀렸습니다.")
    else:
        if st.button("🔓 로그아웃"):
            st.session_state.admin_authed = False
            st.rerun()

        admin_tab1, admin_tab2, admin_tab3 = st.tabs(
            ["📝 전적 입력", "📋 경기 기록", "👤 플레이어 관리"]
        )

        # ── 기능 7: 전적 입력 ─────────────────────────────────────
        with admin_tab1:
            st.markdown("내전 종료 후 결과를 입력하세요.")
            admin_players = load_players()

            if len(admin_players) < 10:
                st.warning(
                    f"현재 {len(admin_players)}명 등록됨. 전적 입력에는 10명 이상이 필요합니다."
                )
            else:
                label_to_player = {
                    f"{p['name']}#{p['tag']}": p for p in admin_players
                }
                labels = list(label_to_player.keys())

                champ_list = get_champion_list()

                st.markdown("**🔵 블루팀 (5명)**")
                blue_picks, blue_pos_picks, blue_champ_picks = [], [], []
                for i in range(5):
                    c1, c2, c3 = st.columns([2.5, 1, 1.5])
                    blue_picks.append(
                        c1.selectbox(f"블루팀 {i+1}번", labels, key=f"b_pick_{i}")
                    )
                    blue_pos_picks.append(
                        c2.selectbox(
                            "포지션",
                            POSITIONS,
                            format_func=lambda x: POSITION_KR[x],
                            key=f"b_pos_{i}",
                        )
                    )
                    blue_champ_picks.append(
                        c3.selectbox(
                            "챔피언",
                            champ_list,
                            key=f"b_champ_{i}",
                            format_func=lambda x: x if x else "선택 안 함",
                        )
                    )

                st.markdown("**🔴 레드팀 (5명)**")
                red_picks, red_pos_picks, red_champ_picks = [], [], []
                for i in range(5):
                    c1, c2, c3 = st.columns([2.5, 1, 1.5])
                    red_picks.append(
                        c1.selectbox(f"레드팀 {i+1}번", labels, key=f"r_pick_{i}")
                    )
                    red_pos_picks.append(
                        c2.selectbox(
                            "포지션",
                            POSITIONS,
                            format_func=lambda x: POSITION_KR[x],
                            key=f"r_pos_{i}",
                        )
                    )
                    red_champ_picks.append(
                        c3.selectbox(
                            "챔피언",
                            champ_list,
                            key=f"r_champ_{i}",
                            format_func=lambda x: x if x else "선택 안 함",
                        )
                    )

                winner = st.radio("승리팀", ["블루팀", "레드팀"], horizontal=True)
                winner_key = "blue" if winner == "블루팀" else "red"

                if st.button("전적 등록", type="primary"):
                    all_picks = blue_picks + red_picks
                    if len(set(all_picks)) < 10:
                        st.error("10명이 모두 달라야 합니다. 중복 선택을 확인해주세요.")
                    else:
                        blue_team = [label_to_player[l] for l in blue_picks]
                        red_team  = [label_to_player[l] for l in red_picks]
                        positions = {}
                        champions = {}
                        for p, pos, champ in zip(blue_team, blue_pos_picks, blue_champ_picks):
                            positions[p["puuid"]] = pos
                            if champ.strip():
                                champions[p["puuid"]] = champ.strip()
                        for p, pos, champ in zip(red_team, red_pos_picks, red_champ_picks):
                            positions[p["puuid"]] = pos
                            if champ.strip():
                                champions[p["puuid"]] = champ.strip()

                        with st.spinner("전적 등록 중... (GitHub 저장에 잠시 시간이 걸릴 수 있습니다)"):
                            ok = record_match_batch(blue_team, red_team, winner_key, positions, champions)

                        if ok:
                            st.success("✅ 전적이 등록되었습니다!")
                            st.cache_data.clear()
                        else:
                            st.error("등록 중 오류가 발생했습니다.")

        # ── 기능 8: 경기 기록 조회 및 삭제 ─────────────────────────
        with admin_tab2:
            matches = load_matches()

            if not matches:
                st.info("등록된 경기 기록이 없습니다.")
            else:
                st.caption(f"총 {len(matches)}경기 기록됨")
                for match in matches:
                    winner_str = "🔵 블루팀" if match["winner"] == "blue" else "🔴 레드팀"
                    with st.expander(
                        f"{match['date']} | {winner_str} 승리 | ID: {match['id']}"
                    ):
                        cb, cr = st.columns(2)
                        with cb:
                            st.markdown("**🔵 블루팀**")
                            for pm in match["blue_team"]:
                                pos_kr = POSITION_KR.get(pm.get("position", ""), "")
                                champ = pm.get("champion", "")
                                champ_str = f" · {champ}" if champ else ""
                                st.markdown(
                                    f"- {pm['name']}#{pm.get('tag', '')} ({pos_kr}{champ_str})"
                                )
                        with cr:
                            st.markdown("**🔴 레드팀**")
                            for pm in match["red_team"]:
                                pos_kr = POSITION_KR.get(pm.get("position", ""), "")
                                champ = pm.get("champion", "")
                                champ_str = f" · {champ}" if champ else ""
                                st.markdown(
                                    f"- {pm['name']}#{pm.get('tag', '')} ({pos_kr}{champ_str})"
                                )

                        st.markdown("---")
                        if st.button(
                            "🗑️ 이 경기 삭제 (전적 원복)",
                            key=f"del_match_{match['id']}",
                        ):
                            with st.spinner("삭제 중..."):
                                ok1 = revert_match(match)
                                updated = [m for m in matches if m["id"] != match["id"]]
                                ok2 = save_matches(
                                    updated,
                                    commit_msg=f"delete: match {match['id']}",
                                )
                            if ok1 and ok2:
                                st.success("삭제 완료! 전적이 원복되었습니다.")
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                st.error("삭제 중 오류가 발생했습니다.")

        # ── 플레이어 관리 (MMR 수정 / 삭제) ─────────────────────────
        with admin_tab3:
            st.markdown("등록된 플레이어를 관리합니다.")
            
            c_sync, _ = st.columns([2, 5])
            with c_sync:
                if st.button("🔄 플레이어 티어 전체 동기화", use_container_width=True):
                    mgmt_players = load_players()
                    if not mgmt_players:
                        st.warning("동기화할 플레이어가 없습니다.")
                    else:
                        success_count = 0
                        error_count = 0
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        for idx, p in enumerate(mgmt_players):
                            status_text.text(f"동기화 중... {p['name']} ({idx+1}/{len(mgmt_players)})")
                            league_res = get_league_entries_by_puuid(p["puuid"])
                            if "error" not in league_res:
                                solo = league_res.get("solo")
                                flex = league_res.get("flex")
                                if solo and solo["tier"] != "UNRANKED":
                                    target_league = solo
                                elif flex and flex["tier"] != "UNRANKED":
                                    target_league = flex
                                else:
                                    target_league = {"tier": "UNRANKED", "rank": "", "lp": 0}
                                    
                                p["solo_tier"] = target_league["tier"]
                                p["solo_rank"] = target_league["rank"]
                                p["solo_lp"] = target_league["lp"]
                                p["solo_mmr"] = calculate_mmr(p["solo_tier"], p["solo_rank"], p["solo_lp"])
                                
                                stats = p.get("inhouse_stats", {})
                                win = stats.get("win", 0)
                                loss = stats.get("loss", 0)
                                total = win + loss
                                inhouse_adj = int((win / total - 0.5) * 300) if total >= 5 else 0
                                p["mmr"] = max(0, p["solo_mmr"] + inhouse_adj)
                                
                                success_count += 1
                                time.sleep(0.1)  # API Rate Limit (최소한의 간격)
                            else:
                                error_count += 1
                                
                            progress_bar.progress((idx + 1) / len(mgmt_players))
                        
                        status_text.text("데이터를 GitHub에 최종 저장하는 중...")
                        if save_players(mgmt_players, commit_message=f"update: sync {success_count} players from Riot API"):
                            st.success(f"동기화 완료! (성공: {success_count}명, 실패: {error_count}명)")
                            st.cache_data.clear()
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("저장 중 오류가 발생했습니다.")
            
            st.markdown("---")
            
            mgmt_players = load_players()

            if not mgmt_players:
                st.info("등록된 플레이어가 없습니다.")
            else:
                for player in mgmt_players:
                    puuid = player["puuid"]
                    stats = player.get("inhouse_stats", {})
                    win = stats.get("win", 0)
                    loss = stats.get("loss", 0)
                    tier_key = f"mmr_tier_{puuid}"
                    num_key  = f"mmr_num_{puuid}"

                    # 처음 렌더링 시 현재 MMR로 number_input 초기화
                    if num_key not in st.session_state:
                        st.session_state[num_key] = player.get("mmr", 800)

                    # 요약 행
                    c1, c2, c3, c4 = st.columns([2.5, 2, 1.5, 1])
                    c1.markdown(f"**{player['name']}**#{player.get('tag', '')}")
                    c2.markdown(
                        f"{tier_emoji(player['solo_tier'])} "
                        f"{tier_label(player['solo_tier'], player.get('solo_rank',''), player.get('solo_lp',0))}"
                    )
                    c3.markdown(f"{win}승 {loss}패 / MMR **{player.get('mmr',0):,}**")
                    with c4:
                        if st.button("삭제", key=f"del_p_{puuid}"):
                            with st.spinner("삭제 중..."):
                                ok = delete_player(puuid)
                            if ok:
                                st.success(f"{player['name']} 삭제 완료!")
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                st.error("삭제 실패")

                    # MMR 수동 수정 expander
                    with st.expander(f"⚙️ {player['name']} MMR 수동 수정"):
                        st.caption(
                            "솔로/자유 랭크가 모두 없는 경우 이전 시즌 기준 티어를 선택해 MMR을 설정하세요."
                        )

                        # 현재 플레이어 tier+rank 기반 기본 인덱스
                        cur_tier = player.get("solo_tier", "SILVER")
                        cur_rank = player.get("solo_rank", "II")
                        default_idx = _TIER_RANK_INDEX.get(
                            (cur_tier, cur_rank),
                            _TIER_RANK_INDEX.get((cur_tier, ""), 10),  # 마스터+ fallback
                        )

                        def _on_tier_rank_change(tk=tier_key, nk=num_key):
                            idx = st.session_state[tk]
                            st.session_state[nk] = TIER_RANK_OPTIONS[idx][3]

                        st.selectbox(
                            "기준 티어 / 랭크",
                            options=range(len(TIER_RANK_OPTIONS)),
                            index=default_idx,
                            format_func=lambda i: (
                                f"{tier_emoji(TIER_RANK_OPTIONS[i][1])} "
                                f"{TIER_RANK_OPTIONS[i][0]}"
                                f"  —  MMR {TIER_RANK_OPTIONS[i][3]:,}"
                            ),
                            key=tier_key,
                            on_change=_on_tier_rank_change,
                        )

                        new_mmr = st.number_input(
                            "적용할 MMR (직접 조정 가능)",
                            min_value=0,
                            max_value=6000,
                            step=50,
                            key=num_key,
                        )

                        if st.button("💾 MMR 저장", key=f"mmr_save_{puuid}", type="primary"):
                            all_players = load_players()
                            for p in all_players:
                                if p["puuid"] == puuid:
                                    p["solo_mmr"] = int(new_mmr)
                                    # 내전 보정치 재적용하여 최종 mmr 계산
                                    s = p.get("inhouse_stats", {})
                                    w = s.get("win", 0)
                                    l = s.get("loss", 0)
                                    t = w + l
                                    inhouse_adj = int((w / t - 0.5) * 300) if t >= 5 else 0
                                    p["mmr"] = max(0, int(new_mmr) + inhouse_adj)
                                    break
                            ok = save_players(
                                all_players,
                                commit_message=f"update: manual solo_mmr {player['name']} → {int(new_mmr)}",
                            )
                            if ok:
                                adj_msg = f" (내전 보정 적용 시 최종 {max(0, int(new_mmr) + (int((w/t-0.5)*300) if t >= 5 else 0)):,})" if t >= 5 else ""
                                st.success(f"솔랭 MMR {int(new_mmr):,} 저장 완료!{adj_msg}")
                                st.cache_data.clear()
                            else:
                                st.error("저장 실패")


# ══════════════════════════════════════════════════════════════════
# TAB 4: 리더보드
# ══════════════════════════════════════════════════════════════════
with tab4:
    import pandas as pd

    lb_players = get_players_cached()

    if not lb_players:
        st.info("등록된 플레이어가 없습니다.")
    else:
        # ── 전체 통계 요약 배너 ───────────────────────────────────
        total_games_all = sum(
            (p.get("inhouse_stats", {}).get("win", 0) + p.get("inhouse_stats", {}).get("loss", 0))
            for p in lb_players
        ) // 10  # 경기 수 = 총 참여 합산 / 10

        players_with_games = [
            p for p in lb_players
            if (p.get("inhouse_stats", {}).get("win", 0) + p.get("inhouse_stats", {}).get("loss", 0)) > 0
        ]

        # 승률왕 (최소 5판)
        qualified = [
            p for p in lb_players
            if (p.get("inhouse_stats", {}).get("win", 0) + p.get("inhouse_stats", {}).get("loss", 0)) >= 5
        ]
        wr_king = max(
            qualified,
            key=lambda p: p["inhouse_stats"]["win"] / (p["inhouse_stats"]["win"] + p["inhouse_stats"]["loss"]),
        ) if qualified else None

        # 최다 경기
        most_played = max(
            players_with_games,
            key=lambda p: p["inhouse_stats"].get("win", 0) + p["inhouse_stats"].get("loss", 0),
        ) if players_with_games else None

        # 최다 승
        most_wins = max(
            players_with_games,
            key=lambda p: p["inhouse_stats"].get("win", 0),
        ) if players_with_games else None

        # 요약 카드 3열
        sc1, sc2, sc3 = st.columns(3)
        card_style = (
            "background:#F8FAFC; border:1px solid #E2E8F0; border-radius:10px;"
            "padding:1rem 1.2rem; text-align:center;"
        )
        with sc1:
            st.markdown(
                f"<div style='{card_style}'>"
                f"<div style='font-size:0.72rem;color:#64748B;letter-spacing:2px;'>TOTAL MATCHES</div>"
                f"<div style='font-size:2rem;font-weight:700;color:#1E293B;'>{total_games_all}</div>"
                f"<div style='font-size:0.72rem;color:#94A3B8;'>누적 내전 경기 수</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
        with sc2:
            if wr_king:
                wr_val = wr_king["inhouse_stats"]["win"] / (
                    wr_king["inhouse_stats"]["win"] + wr_king["inhouse_stats"]["loss"]
                ) * 100
                sc2.markdown(
                    f"<div style='{card_style}'>"
                    f"<div style='font-size:0.72rem;color:#64748B;letter-spacing:2px;'>WIN RATE KING</div>"
                    f"<div style='font-size:1.5rem;font-weight:700;color:#1E293B;'>{wr_king['name']}</div>"
                    f"<div style='font-size:0.85rem;color:#3B82F6;font-weight:600;'>{wr_val:.1f}% 승률</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            else:
                sc2.markdown(
                    f"<div style='{card_style}'>"
                    f"<div style='font-size:0.72rem;color:#64748B;letter-spacing:2px;'>WIN RATE KING</div>"
                    f"<div style='font-size:1.2rem;color:#94A3B8;'>5판 이상 필요</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
        with sc3:
            if most_played:
                mp_total = most_played["inhouse_stats"].get("win", 0) + most_played["inhouse_stats"].get("loss", 0)
                sc3.markdown(
                    f"<div style='{card_style}'>"
                    f"<div style='font-size:0.72rem;color:#64748B;letter-spacing:2px;'>MOST ACTIVE</div>"
                    f"<div style='font-size:1.5rem;font-weight:700;color:#1E293B;'>{most_played['name']}</div>"
                    f"<div style='font-size:0.85rem;color:#10B981;font-weight:600;'>{mp_total}판 참여</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            else:
                sc3.markdown(
                    f"<div style='{card_style}'>"
                    f"<div style='font-size:0.72rem;color:#64748B;letter-spacing:2px;'>MOST ACTIVE</div>"
                    f"<div style='font-size:1.2rem;color:#94A3B8;'>-</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

        st.markdown("<br>", unsafe_allow_html=True)

        # ── 배지 ─────────────────────────────────────────────────
        def _get_badges(player: dict) -> list[str]:
            badges = []
            stats = player.get("inhouse_stats", {})
            win = stats.get("win", 0)
            loss = stats.get("loss", 0)
            total = win + loss
            if total == 0:
                return badges
            wr = win / total
            if total >= 5 and wr >= 0.70:
                badges.append("🔥 승률왕")
            if total >= 30:
                badges.append("⚔️ 베테랑")
            if total >= 60:
                badges.append("👑 레전드")
            if win >= 20:
                badges.append("🏆 20승 달성")
            # 포지션 장인: 한 포지션에 70% 이상 집중
            positions = stats.get("positions", {})
            if total >= 5:
                for pos, cnt in positions.items():
                    if cnt / total >= 0.70:
                        badges.append(f"🎯 {POSITION_KR.get(pos, pos)} 장인")
            return badges

        # ── 종합 순위표 ───────────────────────────────────────────
        lb_sort_col, lb_min_col, _ = st.columns([2, 2, 3])
        with lb_sort_col:
            lb_sort = st.selectbox(
                "정렬 기준",
                ["승률 높은순", "총 승수 많은순", "총 경기 많은순", "내전 MMR 높은순"],
                key="lb_sort",
            )
        with lb_min_col:
            min_games = st.number_input(
                "최소 경기 수",
                min_value=0, max_value=50, value=1, step=1,
                key="lb_min_games",
                help="이 판 수 이상 플레이한 플레이어만 표시",
            )

        rows = []
        for p in lb_players:
            stats = p.get("inhouse_stats", {})
            win = stats.get("win", 0)
            loss = stats.get("loss", 0)
            total = win + loss
            if total < min_games:
                continue
            wr = win / total if total > 0 else 0.0
            solo_mmr = p.get("solo_mmr", p.get("mmr", 0))
            final_mmr = p.get("mmr", solo_mmr)
            most_pos = get_most_played_position(p)
            badges = _get_badges(p)
            rows.append({
                "_win": win,
                "_total": total,
                "_wr": wr,
                "_mmr": final_mmr,
                "닉네임": f"{p['name']}#{p.get('tag', '')}",
                "티어": f"{tier_emoji(p['solo_tier'])} {tier_label(p['solo_tier'], p.get('solo_rank',''), p.get('solo_lp',0))}",
                "내전 MMR": f"{final_mmr:,}",
                "전적": f"{win}승 {loss}패",
                "승률": f"{wr*100:.1f}%" if total > 0 else "-",
                "모스트 포지션": POSITION_KR.get(most_pos, most_pos) if most_pos else "-",
                "배지": " ".join(badges) if badges else "-",
            })

        if not rows:
            st.info(f"{min_games}판 이상 플레이한 플레이어가 없습니다.")
        else:
            sort_key_map = {
                "승률 높은순": lambda r: -r["_wr"],
                "총 승수 많은순": lambda r: -r["_win"],
                "총 경기 많은순": lambda r: -r["_total"],
                "내전 MMR 높은순": lambda r: -r["_mmr"],
            }
            rows.sort(key=sort_key_map[lb_sort])

            # 순위 열 추가
            for i, row in enumerate(rows):
                medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i+1}위"
                row["순위"] = medal

            display_cols = ["순위", "닉네임", "티어", "내전 MMR", "전적", "승률", "모스트 포지션", "배지"]
            df = pd.DataFrame(rows)[display_cols]

            st.dataframe(df, use_container_width=True, hide_index=True, height=min(450, 60 + len(rows) * 35))

        st.markdown("---")

        # ── 포지션별 리더보드 ─────────────────────────────────────
        st.subheader("포지션별 TOP 3")

        pos_cols = st.columns(5)
        for col, pos in zip(pos_cols, POSITIONS):
            pos_rows = []
            for p in lb_players:
                stats = p.get("inhouse_stats", {})
                played = stats.get("positions", {}).get(pos, 0)
                if played == 0:
                    continue
                wins = stats.get("position_wins", {}).get(pos, 0)
                wr = wins / played
                champ_counts = stats.get("position_champions", {}).get(pos, {})
                most_champ = max(champ_counts, key=champ_counts.get) if champ_counts else "-"
                pos_rows.append({
                    "name": p["name"],
                    "played": played,
                    "wins": wins,
                    "wr": wr,
                    "most_champ": most_champ,
                })
            pos_rows.sort(key=lambda r: (-r["wr"], -r["played"]))
            top3 = pos_rows[:3]
            lb_url_map = get_champion_url_map()

            with col:
                st.markdown(
                    f"<div style='text-align:center;font-weight:700;font-size:0.85rem;"
                    f"color:#334155;padding:0.4rem 0 0.6rem;border-bottom:2px solid #E2E8F0;"
                    f"margin-bottom:0.6rem;'>{POSITION_KR[pos]}</div>",
                    unsafe_allow_html=True,
                )
                if not top3:
                    st.caption("기록 없음")
                for rank_i, r in enumerate(top3):
                    medal = ["🥇", "🥈", "🥉"][rank_i]
                    champ_name = r["most_champ"] if r["most_champ"] != "-" else ""
                    champ_url = lb_url_map.get(champ_name, "") if champ_name else ""
                    if champ_url:
                        img_html = (
                            f"<img src='{champ_url}' width='36' height='36' "
                            f"style='border-radius:50%;border:2px solid #E2E8F0;"
                            f"vertical-align:middle;margin-right:6px;'>"
                        )
                    else:
                        img_html = (
                            f"<span style='display:inline-block;width:36px;height:36px;"
                            f"border-radius:50%;background:#F1F5F9;border:2px solid #E2E8F0;"
                            f"vertical-align:middle;margin-right:6px;text-align:center;"
                            f"line-height:36px;font-size:0.8rem;'>?</span>"
                        )
                    st.markdown(
                        f"<div style='display:flex;align-items:center;"
                        f"padding:0.4rem 0;border-bottom:1px solid #F1F5F9;'>"
                        f"{img_html}"
                        f"<div>"
                        f"<div style='font-size:0.85rem;font-weight:700;color:#1E293B;'>"
                        f"{medal} {r['name']}</div>"
                        f"<div style='font-size:0.72rem;color:#64748B;'>"
                        f"{r['wr']*100:.1f}% ({r['wins']}승/{r['played']}판)</div>"
                        f"<div style='font-size:0.68rem;color:#94A3B8;'>"
                        f"{champ_name if champ_name else '-'}</div>"
                        f"</div>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
