import { SelectionReason, SessionState } from "../types";
import { activeOrganizerNames } from "../utils/resultDisplay";

// 理由が増えたら、ここに書かないと型チェックで失敗する
const REASON_LABEL: Record<SelectionReason, string> = {
  manual_check: "手動強制",
  miss_3: "連続未選出救済",
  median_gap: "中央値差による救済",
  random: "ランダム抽選",
  exception_prev_round: "前回参加者からの例外補充",
};

const names = (list: string[]) => (list.length ? list.join(", ") : "なし");

export const MatchInfo = ({ session }: { session: SessionState }) => {
  const active = activeOrganizerNames(session.organizers);
  const due = session.participants.filter((p) => p.due).map((p) => p.name);
  const autoForced = session.participants.filter((p) => p.auto_forced).map((p) => p.name);
  const selections = session.current_round?.selections ?? [];

  return (
    <div>
      <h3>主催モード</h3>
      <p>
        {session.organizer_mode === "single" ? "主催1人" : "主催2人"}
        {active.length > 0 ? `: ${active.join(", ")}` : ""}
      </p>

      <h3>入力済み主催名</h3>
      <p>{names(session.organizers.map((o) => o.name))}</p>

      <h3>前回参加者</h3>
      <p>{names(session.previous_round_players)}</p>

      <h3>次回の優先対象（{session.settings.miss_threshold}回連続未選出）</h3>
      <p>{names(due)}</p>

      <h3>自動強制対象（参加回数の中央値差）</h3>
      <p>{session.settings.enable_auto_force ? names(autoForced) : "無効"}</p>

      <h3>直近抽選の内訳</h3>
      {selections.length === 0 ? (
        <p>なし</p>
      ) : (
        <ul>
          {selections.map((group) => (
            <li key={group.reason}>
              {REASON_LABEL[group.reason]}: {group.players.join(", ")}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};
