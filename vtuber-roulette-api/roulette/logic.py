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
    ModeNotAvailable,
    NotEnoughParticipants,
    Organizer,
    OrganizerMode,
    OrganizersRequired,
    Participant,
    Phase,
    ResultTeam,
    RouletteResult,
    Round,
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


def _players_of_round(session: RouletteState, back: int) -> List[str]:
    """後ろから back 番目 (0 が最新) の回に出た人のうち、今も参加者にいる人 (名前)。

    ID で照らし合わせるので、消して同じ名前で入れ直した人は含まない (別の参加者)。
    """
    if len(session.history) <= back:
        return []
    name_of = {p.id: p.name for p in session.participants}
    return [name_of[i] for i in session.history[-1 - back].selected if i in name_of]


def last_round_players(session: RouletteState) -> List[str]:
    """最新の回に出た人。次の抽選では、ほかの候補で埋まらないときだけ選ばれる。"""
    return _players_of_round(session, 0)


def previous_round_players(session: RouletteState) -> List[str]:
    """最新の回の 1 つ前の回に出た人 (管理画面の「前回参加者」)。"""
    return _players_of_round(session, 1)


def latest_round(session: RouletteState) -> Round | None:
    return session.history[-1] if session.history else None


def phase(session: RouletteState) -> Phase:
    """最新の回の進み具合。履歴が空なら idle、演出が終わっていなければ spinning、終わっていれば result。"""
    latest = latest_round(session)
    if latest is None:
        return "idle"
    return "result" if latest.presented else "spinning"


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
# 集計は _store_tally に任せる。最新の回は履歴から取り出すので書き込まない。


class ForcedLimitError(Exception):
    """手動強制の人数が上限を超える。"""

    def __init__(self, limit: int):
        super().__init__(limit)
        self.limit = limit


def replace_participants(session: RouletteState, names: List[str]) -> None:
    """参加者を names に置き換える。残る人は強制・除外の設定を引き継ぎ、消えた人の設定は一緒に消える。"""
    kept = {p.name: p for p in session.participants}
    session.participants = [kept.get(n) or Participant(name=n) for n in sanitize_names(names, limit=1000)]
    # 集計を、今の参加者に合わせ直す
    _store_tally(session, _current_tally(session))


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
    skip = set(last_round_players(session)) | set(already_selected)
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
    last = set(last_round_players(session))
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
    last = set(last_round_players(session))
    fresh = [p for p in c.pool if p not in last]
    due = due_players(session)
    add(_longest_wait_first(session, [p for p in fresh if p in due]), "miss_3")
    add(auto_forced_players(session, list(chosen)), "median_gap")
    add(_shuffled([p for p in fresh if p not in chosen]), "random")
    add(_shuffled([p for p in c.pool if p in last]), "exception_prev_round")
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


def _lineup(mode: DrawMode, picked: List[str], organizers: List[str]) -> List[tuple[str, List[str]]]:
    """選ばれた人 (picked、チームA → チームB の順) と主催をチームに分ける。[(チーム名, 顔ぶれ)]"""
    if mode == "standard_3":
        return [("チームA", organizers[:1] + picked[:1]), ("チームB", picked[1:3])]
    if mode == "standard_4":
        return [("チームA", picked[0:2]), ("チームB", picked[2:4])]
    if mode == "hosts_vs_duo":
        return [("主催チーム", organizers[:2]), ("挑戦者チーム", picked[:2])]
    # hosts_split_pairs
    return [
        (f"{organizers[0]}チーム", [organizers[0], picked[0]]),
        (f"{organizers[1]}チーム", [organizers[1], picked[1]]),
    ]


def build_result(mode: DrawMode, selection: Selection, organizers: List[str]) -> RouletteResult:
    """表示用のチーム分け (名前)。organizers は選ばれている順。"""
    return RouletteResult(
        kind=mode,
        teams=[ResultTeam(label=label, players=players) for label, players in _lineup(mode, selection.players, organizers)],
    )


def compute_matchup_key(teams: List[List[str]]) -> str:
    """チーム構成をチーム順不問・選手順不問のキーに変換する。"""
    team_keys = sorted("|".join(sorted(team)) for team in teams)
    return "||".join(team_keys)


def matchup_key(session: RouletteState, mode: DrawMode, selection: Selection, organizers: List[str]) -> str:
    """対戦カードのキー。参加者は ID で表す (消して入れ直した人との組み合わせは別のカード)。"""
    id_of = {p.name: p.id for p in session.participants}
    picked = [id_of[p] for p in selection.players]
    return compute_matchup_key([players for _, players in _lineup(mode, picked, organizers)])


def new_round(
    session: RouletteState,
    *,
    round_id: str,
    drawn_at: str,
    mode: DrawMode,
    selection: Selection,
    organizers: List[str],
) -> Round:
    """今の参加者で、selection (名前) を記録する 1 回分を作る。人は ID で記録する。"""
    id_of = {p.name: p.id for p in session.participants}
    return Round(
        round_id=round_id,
        drawn_at=drawn_at,
        result=build_result(mode, selection, organizers),
        selected=[id_of[p] for p in selection.players],
        organizers=list(organizers),
        participants=[p.id for p in session.participants],
        names={p.id: p.name for p in session.participants},
        # 選ばれた人の並び順 (チームA → チームB) にそろえる
        reasons={id_of[p]: selection.reasons[p] for p in selection.players},
        matchup=matchup_key(session, mode, selection, organizers),
    )


# ── 集計 ─────────────────────────────────────────────────────────────────────
# 参加回数・ミス回数・対戦カードの回数は、どれも履歴を順にたどった結果。
# 1 回分を足すのも、履歴を消したあとに数え直すのも、count_round だけを使う。

EMPTY_TALLY = Tally(participation_counts={}, miss_counts={}, pair_counts={})


def count_round(tally: Tally, record: Round) -> Tally:
    """集計に 1 回分の記録を足した集計を返す。その回の参加者だけが数えられる。人は ID で数える。"""
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
    pairs[record.matchup] = pairs.get(record.matchup, 0) + 1
    return Tally(participation_counts=participation, miss_counts=miss, pair_counts=pairs)


def count_history(history: List[Round]) -> Tally:
    tally = EMPTY_TALLY
    for record in history:
        tally = count_round(tally, record)
    return tally


# ── 抽選結果と履歴の削除を状態に反映する ─────────────────────────────────────
# 履歴から数える集計を session に書き込むのは _store_tally だけ。抽選、履歴の削除、参加者の入れ替えがこれを呼ぶ。
# 最新の回とその進み具合は保存せず、latest_round / phase で履歴から取り出す。


def _current_tally(session: RouletteState) -> Tally:
    """保存している集計 (名前で持つ) を、ID で数える形にする。"""
    return Tally(
        participation_counts={p.id: session.participation_counts.get(p.name, 0) for p in session.participants},
        miss_counts={p.id: session.miss_counts.get(p.name, 0) for p in session.participants},
        pair_counts=session.pair_counts,
    )


def _store_tally(session: RouletteState, tally: Tally) -> None:
    """ID で数えた集計を状態に入れる。参加回数とミス回数は、今の参加者の分だけを名前で持つ。"""
    session.participation_counts = {p.name: tally.participation_counts.get(p.id, 0) for p in session.participants}
    session.miss_counts = {p.name: tally.miss_counts.get(p.id, 0) for p in session.participants}
    session.pair_counts = dict(tally.pair_counts)


def apply_draw_result(session: RouletteState, new: Round) -> None:
    # 置き換わる最新の回は、演出が終わっていなくても済みにする (その演出はもう意味がない)
    latest = latest_round(session)
    if latest is not None:
        latest.presented = True
    session.history = session.history + [new]
    _store_tally(session, count_round(_current_tally(session), new))


def mark_presented(session: RouletteState, round_id: str) -> bool:
    """最新の回の演出が終わったことを記録する。round_id が最新の回でなければ何もせず False。"""
    latest = latest_round(session)
    if latest is None or latest.round_id != round_id:
        return False
    latest.presented = True
    return True


def delete_history_record(session: RouletteState, round_id: str) -> bool:
    """履歴から 1 件削除し、残りの履歴から集計を数え直す。"""
    remaining = [r for r in session.history if r.round_id != round_id]
    if len(remaining) == len(session.history):
        return False
    session.history = remaining
    _store_tally(session, count_history(remaining))
    return True
