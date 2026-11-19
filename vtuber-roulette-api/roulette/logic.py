import random
import statistics
from typing import Dict, List, Sequence

from draw_config import (
    AUTO_FORCE_MAX_PER_DRAW,
    AUTO_FORCE_MEDIAN_GAP,
)
from .models import (
    DrawBlock,
    DrawConstraints,
    DrawMode,
    DrawRecord,
    ModeNotAvailable,
    NotEnoughParticipants,
    OrganizerMode,
    OrganizersRequired,
    ResultTeam,
    RouletteResult,
    RouletteState,
    Selection,
    Tally,
    TeamForcedOverSlots,
    TooManyForced,
)

# ── グローバル状態 ─────────────────────────────────────────────────────────────

state = RouletteState()


def reset_state() -> None:
    # router 側が import 済みの state を参照し続けるため、再代入せず中身を初期化する
    fresh = RouletteState()
    for field in RouletteState.model_fields:
        setattr(state, field, getattr(fresh, field))


# ── ユーティリティ ─────────────────────────────────────────────────────────────


def sanitize_names(names: List[str], limit: int) -> List[str]:
    unique: List[str] = []
    for name in names:
        trimmed = name.strip()
        if trimmed and trimmed not in unique:
            unique.append(trimmed)
        if len(unique) >= limit:
            break
    return unique


def active_organizers() -> List[str]:
    result = [
        state.organizers[i]
        for i in state.selected_organizer_indices
        if 0 <= i < len(state.organizers)
    ]
    limit = 2 if state.organizer_mode == "double" else 1
    return result[:limit]


def get_team_slots(mode: DrawMode) -> tuple[int, int]:
    """抽選で埋めるチームA・チームBのスロット数を返す。"""
    if mode == "standard_3":
        return 1, 2
    if mode == "standard_4":
        return 2, 2
    if mode == "hosts_vs_duo":
        return 0, 2
    # hosts_split_pairs
    return 1, 1


# ── 操作 ─────────────────────────────────────────────────────────────────────
# 画面からの操作で状態を変える。入力の検証 (存在しない名前など) は router が行う。
# 操作が書き込むのは、利用者が入力した値 (参加者、強制、除外、主催、設定) だけ。
# 履歴から導く値 (集計、前回・前々回の参加者など) は _store_tally と _show_latest_round に任せる。


class ForcedLimitError(Exception):
    """手動強制の人数が上限を超える。"""

    def __init__(self, limit: int):
        super().__init__(limit)
        self.limit = limit


def _drop_records_of_non_participants() -> None:
    """参加者でなくなった人の強制・除外の設定を消し、履歴から導く値を今の参加者に合わせ直す。"""

    def keep(names: List[str]) -> List[str]:
        return [p for p in names if p in state.participants]

    state.forced_players = keep(state.forced_players)[: forced_players_limit()]
    state.forced_player_teams = {
        p: state.forced_player_teams.get(p, "none") for p in state.forced_players
    }
    state.excluded_players = keep(state.excluded_players)
    _store_tally(_current_tally())
    _show_latest_round()


def replace_participants(names: List[str]) -> None:
    state.participants = sanitize_names(names, limit=1000)
    _drop_records_of_non_participants()


def add_participant(name: str) -> None:
    replace_participants(state.participants + [name])


def remove_participant(name: str) -> None:
    replace_participants([p for p in state.participants if p != name])


def set_forced(name: str, team: str | None) -> None:
    """name の手動強制を設定する。team は "none" (チーム指定なし) / "A" / "B"、None で解除。"""
    if team is None:
        state.forced_players = [p for p in state.forced_players if p != name]
        state.forced_player_teams.pop(name, None)
    else:
        if name not in state.forced_players:
            if len(state.forced_players) >= forced_players_limit():
                raise ForcedLimitError(forced_players_limit())
            state.forced_players = state.forced_players + [name]
        state.forced_player_teams = {**state.forced_player_teams, name: team}


def set_excluded(name: str, excluded: bool) -> None:
    others = [p for p in state.excluded_players if p != name]
    state.excluded_players = others + [name] if excluded else others


def configure_organizers(
    mode: OrganizerMode, names: List[str], active: List[str]
) -> None:
    """主催の候補 (並び順どおり) と、そのうち主催として選ぶ人を設定する。"""
    state.organizer_mode = mode
    state.organizers = sanitize_names(names, limit=10)
    selected = [
        state.organizers.index(n)
        for n in sanitize_names(active, limit=10)
        if n in state.organizers
    ]
    state.selected_organizer_indices = sorted(selected)[: 2 if mode == "double" else 1]

    # 主催 2 人モードでは手動強制の上限が下がる
    state.forced_players = state.forced_players[: forced_players_limit()]
    state.forced_player_teams = {
        p: state.forced_player_teams.get(p, "none") for p in state.forced_players
    }


def save_settings(miss_threshold: int, enable_auto_force: bool) -> None:
    state.miss_threshold = miss_threshold
    state.enable_auto_force = enable_auto_force


# ── 抽選ロジック ───────────────────────────────────────────────────────────────


def compute_auto_forced_players(
    participation_counts: Dict[str, int],
    candidates: List[str],
    *,
    median_gap: int,
    max_per_draw: int,
) -> List[str]:
    """自動強制 (参加回数の中央値差) のルール。state を読まない。

    participation_counts は参加者全員の参加回数 (中央値はこの全員で取る)。
    candidates のうち、参加回数が「中央値 - median_gap」以下の人を、参加回数の少ない順
    (同じ回数は名前順) に最大 max_per_draw 人 (0 なら無制限) 返す。
    """
    if not participation_counts:
        return []
    threshold = statistics.median(participation_counts.values()) - median_gap
    picked = sorted(
        (p for p in candidates if participation_counts.get(p, 0) <= threshold),
        key=lambda p: (participation_counts.get(p, 0), p),
    )
    return picked[:max_per_draw] if max_per_draw > 0 else picked


def auto_forced_players(already_selected: Sequence[str] = ()) -> List[str]:
    """今の状態で、次の抽選の自動強制の対象になる人。

    状態から導く値なので保存せず、必要なとき (抽選、画面に送る状態の組み立て) に毎回計算する。
    手動強制・前回出た人・除外中・ミス回数の保証の対象・already_selected は候補から外す。
    """
    if not state.enable_auto_force:
        return []
    skip = set(manual_forced_players()) | set(state.last_players) | set(state.excluded_players) | set(already_selected)
    candidates = [
        p for p in state.participants
        if p not in skip and state.miss_counts.get(p, 0) < state.miss_threshold
    ]
    return compute_auto_forced_players(
        {p: state.participation_counts.get(p, 0) for p in state.participants},
        candidates,
        median_gap=AUTO_FORCE_MEDIAN_GAP,
        max_per_draw=AUTO_FORCE_MAX_PER_DRAW,
    )


SINGLE_MODES: tuple[DrawMode, ...] = ("standard_3", "standard_4")
DOUBLE_MODES: tuple[DrawMode, ...] = ("hosts_vs_duo", "hosts_split_pairs")


def modes_for_organizer_mode() -> tuple[DrawMode, ...]:
    return DOUBLE_MODES if state.organizer_mode == "double" else SINGLE_MODES


def forced_players_limit() -> int:
    return 2 if state.organizer_mode == "double" else 4


def manual_forced_players() -> List[str]:
    """手動強制のうち、今の参加者にいる人。"""
    return [p for p in state.forced_players if p in state.participants]


def is_due(name: str) -> bool:
    """ミス回数の保証の対象か。次の抽選で、枠が足りる限り手動強制の次に優先して選ばれる。"""
    return (
        name in state.participants
        and name not in state.last_players
        and name not in state.excluded_players
        and state.miss_counts.get(name, 0) >= state.miss_threshold
    )


# ── 抽選できない理由 ─────────────────────────────────────────────────────────
# 判定は理由の種類と数値 (models.DrawBlock) だけを返す。利用者向けの文言は messages.py が組み立てる。


def draw_constraints(mode: DrawMode) -> DrawConstraints:
    forced = manual_forced_players()

    def team(p: str) -> str:
        return state.forced_player_teams.get(p, "none")

    return DrawConstraints(
        slots=dict(zip(("A", "B"), get_team_slots(mode))),
        fixed={t: [p for p in forced if team(p) == t] for t in ("A", "B")},
        forced_any=[p for p in forced if team(p) not in ("A", "B")],
        pool=[p for p in state.participants if p not in state.excluded_players and p not in forced],
    )


def constraint_violation(c: DrawConstraints) -> DrawBlock | None:
    """制約を満たして枠を埋められなければ、その理由を返す。

    手動強制以外の候補はどのチームの枠にも入れるので、人数を数えるだけで判定できる。
    候補が入れるチームを制限する制約を足すときは、ここを割り当ての判定に変える。
    """
    for team in ("A", "B"):
        if len(c.fixed[team]) > c.slots[team]:
            return TeamForcedOverSlots(team=team, forced=len(c.fixed[team]), slots=c.slots[team])  # type: ignore[arg-type]
    if len(c.forced) > c.total_slots:
        return TooManyForced(forced=len(c.forced), slots=c.total_slots)
    eligible = len(c.forced) + len(c.pool)
    if eligible < c.total_slots:
        return NotEnoughParticipants(needed=c.total_slots, eligible=eligible)
    return None


def draw_blocker(mode: DrawMode) -> DrawBlock | None:
    """この mode で今は抽選できない理由を返す。抽選できるなら None。

    抽選 API と画面のボタンの可否の両方がこれを使う。抽選演出中かどうかは見ない。
    """
    if mode not in modes_for_organizer_mode():
        return ModeNotAvailable()
    if state.organizer_mode == "double" and len(active_organizers()) < 2:
        return OrganizersRequired(required=2, active=len(active_organizers()))

    return constraint_violation(draw_constraints(mode))


# ── 抽選 ─────────────────────────────────────────────────────────────────────


class NotEnoughCandidates(Exception):
    """枠を埋められなかった。draw_blocker が先に弾くので、起きたらバグ。"""


def _shuffled(names: List[str]) -> List[str]:
    names = list(names)
    random.shuffle(names)
    return names


def _longest_wait_first(names: List[str]) -> List[str]:
    """ミス回数の多い順。同じ回数どうしは参加者リストの順で決めない。"""
    return sorted(_shuffled(names), key=lambda p: state.miss_counts.get(p, 0), reverse=True)


def _choose_players(c: DrawConstraints) -> Dict[str, str]:
    """誰が出るかを、優先度の高い順に決める。チームはまだ決めない。戻り値は {名前: 選ばれた理由}。

    手動強制 → ミス回数の保証 → 自動強制 → ランダム → 前回参加者からの補充。
    """
    chosen = {p: "manual_check" for p in c.forced}

    def add(candidates: List[str], reason: str) -> None:
        for p in candidates:
            if len(chosen) >= c.total_slots:
                return
            chosen.setdefault(p, reason)

    # 前回出た人は、ほかの候補で埋まらないときだけ補充に使う
    fresh = [p for p in c.pool if p not in state.last_players]
    add(_longest_wait_first([p for p in fresh if is_due(p)]), "miss_3")
    add(auto_forced_players(list(chosen)), "median_gap")
    add(_shuffled([p for p in fresh if p not in chosen]), "random")
    add(_shuffled([p for p in c.pool if p in state.last_players]), "exception_prev_round")
    return chosen


def _assign_teams(c: DrawConstraints, chosen: Dict[str, str]) -> Selection:
    """チーム指定ありの手動強制を指定のチームに置き、残りはシャッフルして空いている枠に入れる。

    選ばれた理由でチームが偏らないように、チーム分けは誰が出るかを決めたあとに行う。
    """
    teams = {t: list(c.fixed[t]) for t in ("A", "B")}
    fixed = set(c.fixed["A"]) | set(c.fixed["B"])
    for p in _shuffled([p for p in chosen if p not in fixed]):
        teams["A" if len(teams["A"]) < c.slots["A"] else "B"].append(p)
    return Selection(team_a=teams["A"], team_b=teams["B"], reasons=dict(chosen))


def select_players(mode: DrawMode) -> Selection:
    c = draw_constraints(mode)
    chosen = _choose_players(c)
    if len(chosen) < c.total_slots:
        raise NotEnoughCandidates()
    return _assign_teams(c, chosen)


def build_result(mode: DrawMode, selection: Selection, organizers: List[str]) -> RouletteResult:
    """選ばれた人と主催 (organizers、選ばれている順) をチームに分ける。"""
    picked = selection.players

    def result(*teams: tuple[str, List[str]]) -> RouletteResult:
        return RouletteResult(kind=mode, teams=[ResultTeam(label=label, players=players) for label, players in teams])

    if mode == "standard_3":
        return result(("チームA", organizers[:1] + picked[:1]), ("チームB", picked[1:3]))
    if mode == "standard_4":
        return result(("チームA", picked[0:2]), ("チームB", picked[2:4]))
    if mode == "hosts_vs_duo":
        return result(("主催チーム", organizers[:2]), ("挑戦者チーム", picked[:2]))
    # hosts_split_pairs
    return result(
        (f"{organizers[0]}チーム", [organizers[0], picked[0]]),
        (f"{organizers[1]}チーム", [organizers[1], picked[1]]),
    )


def compute_matchup_key(result: RouletteResult) -> str:
    """チーム構成をチーム順不問・選手順不問のキーに変換する。"""
    team_keys = sorted("|".join(sorted(team.players)) for team in result.teams)
    return "||".join(team_keys)


def new_record(
    *,
    round_id: str,
    drawn_at: str,
    result: RouletteResult,
    selection: Selection,
    organizers: List[str],
    participants: List[str],
) -> DrawRecord:
    return DrawRecord(
        round_id=round_id,
        drawn_at=drawn_at,
        result=result,
        selected=selection.players,
        organizers=list(organizers),
        participants=list(participants),
        # 選ばれた人の並び順 (チームA → チームB) にそろえる
        reasons={p: selection.reasons[p] for p in selection.players},
    )


# ── 集計 ─────────────────────────────────────────────────────────────────────
# 参加回数・ミス回数・対戦カードの回数は、どれも履歴を順にたどった結果。
# 1 回分を足すのも、履歴を消したあとに数え直すのも、count_round だけを使う。

EMPTY_TALLY = Tally(participation_counts={}, miss_counts={}, pair_counts={})


def count_round(tally: Tally, record: DrawRecord) -> Tally:
    """集計に 1 回分の記録を足した集計を返す。その回の参加者だけが数えられる。"""
    picked = set(record.selected)
    participation = dict(tally.participation_counts)
    miss = dict(tally.miss_counts)
    for p in record.participants:
        if p in picked:
            participation[p] = participation.get(p, 0) + 1
            miss[p] = 0
        else:
            miss[p] = miss.get(p, 0) + 1
    pairs = dict(tally.pair_counts)
    key = compute_matchup_key(record.result)
    pairs[key] = pairs.get(key, 0) + 1
    return Tally(participation_counts=participation, miss_counts=miss, pair_counts=pairs)


def count_history(history: List[DrawRecord]) -> Tally:
    tally = EMPTY_TALLY
    for record in history:
        tally = count_round(tally, record)
    return tally


# ── 抽選結果と履歴の削除を状態に反映する ─────────────────────────────────────
# 履歴から導く値 (集計、前回・前々回の参加者、結果、選出理由、回の ID) を state に書き込むのは、
# _store_tally と _show_latest_round だけ。抽選、履歴の削除、参加者の入れ替えがこれを呼ぶ。


def _current_tally() -> Tally:
    return Tally(
        participation_counts=state.participation_counts,
        miss_counts=state.miss_counts,
        pair_counts=state.pair_counts,
    )


def _store_tally(tally: Tally) -> None:
    """集計を状態に入れる。参加回数とミス回数は、今の参加者の分だけを持つ。"""
    state.participation_counts = {p: tally.participation_counts.get(p, 0) for p in state.participants}
    state.miss_counts = {p: tally.miss_counts.get(p, 0) for p in state.participants}
    state.pair_counts = dict(tally.pair_counts)


def _show_latest_round() -> None:
    """最新の回の情報 (前回・前々回の参加者、結果、選出理由、回の ID) を履歴から取り直す。"""
    history = state.history
    current = set(state.participants)

    def alive(names: List[str]) -> List[str]:
        return [p for p in names if p in current]

    state.last_players = alive(history[-1].selected) if history else []
    state.prev_players = alive(history[-2].selected) if len(history) > 1 else []
    state.last_selection_reasons = dict(history[-1].reasons) if history else {}
    state.result = history[-1].result if history else None
    state.round_id = history[-1].round_id if history else None


def apply_draw_result(record: DrawRecord) -> None:
    state.history = state.history + [record]
    _store_tally(count_round(_current_tally(), record))
    _show_latest_round()
    state.phase = "spinning"


def delete_history_record(round_id: str) -> bool:
    """履歴から 1 件削除し、残りの履歴から集計を数え直す。"""
    remaining = [r for r in state.history if r.round_id != round_id]
    if len(remaining) == len(state.history):
        return False
    state.history = remaining
    _store_tally(count_history(remaining))
    _show_latest_round()
    state.phase = "result" if remaining else "idle"
    return True
