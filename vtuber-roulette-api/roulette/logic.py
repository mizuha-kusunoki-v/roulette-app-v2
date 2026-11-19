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
    Organizer,
    OrganizerMode,
    OrganizersRequired,
    Participant,
    ResultTeam,
    RouletteResult,
    RouletteState,
    Selection,
    Tally,
    TeamForcedOverSlots,
    TooManyForced,
)

# ── セッション ───────────────────────────────────────────────────────────────
# 抽選の状態 (RouletteState) はグローバルに持たず、使う関数が引数 session で受け取る。
# セッションを作るのは sessions.SessionFactory、持つのは composition root (main.create_app)。


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


def participant_names(session: RouletteState) -> List[str]:
    return [p.name for p in session.participants]


def find_participant(session: RouletteState, name: str) -> Participant | None:
    return next((p for p in session.participants if p.name == name), None)


def active_organizers(session: RouletteState) -> List[str]:
    return [o.name for o in session.organizers if o.active]


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


def replace_participants(session: RouletteState, names: List[str]) -> None:
    """参加者を names に置き換える。残る人は強制・除外の設定を引き継ぎ、消えた人の設定は一緒に消える。"""
    kept = {p.name: p for p in session.participants}
    session.participants = [kept.get(n) or Participant(name=n) for n in sanitize_names(names, limit=1000)]
    # 履歴から導く値を、今の参加者に合わせ直す
    _store_tally(session, _current_tally(session))
    _show_latest_round(session)


def add_participant(session: RouletteState, name: str) -> None:
    replace_participants(session, participant_names(session) + [name])


def remove_participant(session: RouletteState, name: str) -> None:
    replace_participants(session, [p for p in participant_names(session) if p != name])


def set_forced(session: RouletteState, name: str, team: str | None) -> None:
    """name の手動強制を設定する。team は "none" (チーム指定なし) / "A" / "B"、None で解除。"""
    p = find_participant(session, name)
    if p is None:
        return
    if team is not None and p.forced is None and len(manual_forced_players(session)) >= forced_players_limit(session):
        raise ForcedLimitError(forced_players_limit(session))
    p.forced = team  # type: ignore[assignment]


def set_excluded(session: RouletteState, name: str, excluded: bool) -> None:
    p = find_participant(session, name)
    if p is not None:
        p.excluded = excluded


def configure_organizers(
    session: RouletteState,
    mode: OrganizerMode, names: List[str], active: List[str]
) -> None:
    """主催の候補 (並び順どおり) と、そのうち主催として選ぶ人を設定する。

    選べるのは主催モードの人数まで (候補の並び順で先の人から)。
    """
    session.organizer_mode = mode
    chosen = set(sanitize_names(active, limit=10))
    limit = 2 if mode == "double" else 1
    session.organizers = []
    for n in sanitize_names(names, limit=10):
        selected = n in chosen and sum(o.active for o in session.organizers) < limit
        session.organizers.append(Organizer(name=n, active=selected))

    # 主催 2 人モードでは手動強制の上限が下がる。超えた分は参加者の並び順で後ろの人から外す
    for p in manual_forced_players(session)[forced_players_limit(session):]:
        set_forced(session, p, None)


def save_settings(session: RouletteState, miss_threshold: int, enable_auto_force: bool) -> None:
    session.miss_threshold = miss_threshold
    session.enable_auto_force = enable_auto_force


# ── 抽選ロジック ───────────────────────────────────────────────────────────────


def compute_auto_forced_players(
    participation_counts: Dict[str, int],
    candidates: List[str],
    *,
    median_gap: int,
    max_per_draw: int,
) -> List[str]:
    """自動強制 (参加回数の中央値差) のルール。session を読まない。

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


def auto_forced_players(session: RouletteState, already_selected: Sequence[str] = ()) -> List[str]:
    """今の状態で、次の抽選の自動強制の対象になる人。

    状態から導く値なので保存せず、必要なとき (抽選、画面に送る状態の組み立て) に毎回計算する。
    手動強制・前回出た人・除外中・ミス回数の保証の対象・already_selected は候補から外す。
    """
    if not session.enable_auto_force:
        return []
    skip = set(session.last_players) | set(already_selected)
    candidates = [
        p.name for p in session.participants
        if p.forced is None
        and not p.excluded
        and p.name not in skip
        and session.miss_counts.get(p.name, 0) < session.miss_threshold
    ]
    return compute_auto_forced_players(
        {p: session.participation_counts.get(p, 0) for p in participant_names(session)},
        candidates,
        median_gap=AUTO_FORCE_MEDIAN_GAP,
        max_per_draw=AUTO_FORCE_MAX_PER_DRAW,
    )


SINGLE_MODES: tuple[DrawMode, ...] = ("standard_3", "standard_4")
DOUBLE_MODES: tuple[DrawMode, ...] = ("hosts_vs_duo", "hosts_split_pairs")


def modes_for_organizer_mode(session: RouletteState) -> tuple[DrawMode, ...]:
    return DOUBLE_MODES if session.organizer_mode == "double" else SINGLE_MODES


def forced_players_limit(session: RouletteState) -> int:
    return 2 if session.organizer_mode == "double" else 4


def manual_forced_players(session: RouletteState) -> List[str]:
    """手動強制している参加者 (参加者の並び順)。"""
    return [p.name for p in session.participants if p.forced is not None]


def due_players(session: RouletteState) -> set[str]:
    """ミス回数の保証の対象。次の抽選で、枠が足りる限り手動強制の次に優先して選ばれる。"""
    last = set(session.last_players)
    return {
        p.name for p in session.participants
        if p.name not in last
        and not p.excluded
        and session.miss_counts.get(p.name, 0) >= session.miss_threshold
    }


# ── 抽選できない理由 ─────────────────────────────────────────────────────────
# 判定は理由の種類と数値 (models.DrawBlock) だけを返す。利用者向けの文言は messages.py が組み立てる。


def draw_constraints(session: RouletteState, mode: DrawMode) -> DrawConstraints:
    forced = [p for p in session.participants if p.forced is not None]

    return DrawConstraints(
        slots=dict(zip(("A", "B"), get_team_slots(mode))),
        fixed={t: [p.name for p in forced if p.forced == t] for t in ("A", "B")},
        forced_any=[p.name for p in forced if p.forced not in ("A", "B")],
        pool=[p.name for p in session.participants if not p.excluded and p.forced is None],
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


def draw_blocker(session: RouletteState, mode: DrawMode) -> DrawBlock | None:
    """この mode で今は抽選できない理由を返す。抽選できるなら None。

    抽選 API と画面のボタンの可否の両方がこれを使う。抽選演出中かどうかは見ない。
    """
    if mode not in modes_for_organizer_mode(session):
        return ModeNotAvailable()
    if session.organizer_mode == "double" and len(active_organizers(session)) < 2:
        return OrganizersRequired(required=2, active=len(active_organizers(session)))

    return constraint_violation(draw_constraints(session, mode))


# ── 抽選 ─────────────────────────────────────────────────────────────────────


class NotEnoughCandidates(Exception):
    """枠を埋められなかった。draw_blocker が先に弾くので、起きたらバグ。"""


def _shuffled(names: List[str]) -> List[str]:
    names = list(names)
    random.shuffle(names)
    return names


def _longest_wait_first(session: RouletteState, names: List[str]) -> List[str]:
    """ミス回数の多い順。同じ回数どうしは参加者リストの順で決めない。"""
    return sorted(_shuffled(names), key=lambda p: session.miss_counts.get(p, 0), reverse=True)


def _choose_players(session: RouletteState, c: DrawConstraints) -> Dict[str, str]:
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
    fresh = [p for p in c.pool if p not in session.last_players]
    due = due_players(session)
    add(_longest_wait_first(session, [p for p in fresh if p in due]), "miss_3")
    add(auto_forced_players(session, list(chosen)), "median_gap")
    add(_shuffled([p for p in fresh if p not in chosen]), "random")
    add(_shuffled([p for p in c.pool if p in session.last_players]), "exception_prev_round")
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


def select_players(session: RouletteState, mode: DrawMode) -> Selection:
    c = draw_constraints(session, mode)
    chosen = _choose_players(session, c)
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
# 履歴から導く値 (集計、前回・前々回の参加者、結果、選出理由、回の ID) を session に書き込むのは、
# _store_tally と _show_latest_round だけ。抽選、履歴の削除、参加者の入れ替えがこれを呼ぶ。


def _current_tally(session: RouletteState) -> Tally:
    return Tally(
        participation_counts=session.participation_counts,
        miss_counts=session.miss_counts,
        pair_counts=session.pair_counts,
    )


def _store_tally(session: RouletteState, tally: Tally) -> None:
    """集計を状態に入れる。参加回数とミス回数は、今の参加者の分だけを持つ。"""
    names = participant_names(session)
    session.participation_counts = {p: tally.participation_counts.get(p, 0) for p in names}
    session.miss_counts = {p: tally.miss_counts.get(p, 0) for p in names}
    session.pair_counts = dict(tally.pair_counts)


def _show_latest_round(session: RouletteState) -> None:
    """最新の回の情報 (前回・前々回の参加者、結果、選出理由、回の ID) を履歴から取り直す。"""
    history = session.history
    current = set(participant_names(session))

    def alive(names: List[str]) -> List[str]:
        return [p for p in names if p in current]

    session.last_players = alive(history[-1].selected) if history else []
    session.prev_players = alive(history[-2].selected) if len(history) > 1 else []
    session.last_selection_reasons = dict(history[-1].reasons) if history else {}
    session.result = history[-1].result if history else None
    session.round_id = history[-1].round_id if history else None


def apply_draw_result(session: RouletteState, record: DrawRecord) -> None:
    session.history = session.history + [record]
    _store_tally(session, count_round(_current_tally(session), record))
    _show_latest_round(session)
    session.phase = "spinning"


def delete_history_record(session: RouletteState, round_id: str) -> bool:
    """履歴から 1 件削除し、残りの履歴から集計を数え直す。"""
    remaining = [r for r in session.history if r.round_id != round_id]
    if len(remaining) == len(session.history):
        return False
    session.history = remaining
    _store_tally(session, count_history(remaining))
    _show_latest_round(session)
    session.phase = "result" if remaining else "idle"
    return True
