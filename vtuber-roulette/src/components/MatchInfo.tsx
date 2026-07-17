import { RouletteState } from "../types";
import { getActiveOrganizers } from "../utils/resultDisplay";

const REASON_LABEL: Record<string, string> = {
  manual_check: "手動強制",
  miss_3: `連続未選出救済`,
  median_gap: "中央値差による救済",
  random: "ランダム抽選",
  exception_prev_round: "前回参加者からの例外補充",
};

export const MatchInfo = ({ state }: { state: RouletteState }) => {
  const guaranteed = Object.entries(state.miss_counts)
    .filter(([_, count]) => count >= state.miss_threshold)
    .map(([name]) => name);

  const grouped = Object.entries(state.last_selection_reasons).reduce(
    (acc, [name, reason]) => {
      if (!acc[reason]) acc[reason] = [];
      acc[reason].push(name);
      return acc;
    },
    {} as Record<string, string[]>
  );

  const activeOrganizers = getActiveOrganizers(
    state.organizer_mode,
    state.organizers,
    state.selected_organizer_indices,
  );

  return (
    <div>
      <h3>主催モード</h3>
      <p>
        {state.organizer_mode === "single" ? "主催1人" : "主催2人"}
        {activeOrganizers.length > 0 ? `: ${activeOrganizers.join(", ")}` : ""}
      </p>

      <h3>入力済み主催名</h3>
      <p>{state.organizers.length > 0 ? state.organizers.join(", ") : "なし"}</p>

      <h3>前回参加者</h3>
      <p>{state.prev_players.length ? state.prev_players.join(", ") : "なし"}</p>

      <h3>次回の優先対象（{state.miss_threshold}回連続未選出）</h3>
      <p>{guaranteed.length ? guaranteed.join(", ") : "なし"}</p>

      <h3>自動強制対象（参加回数の中央値差）</h3>
      <p>
        {state.enable_auto_force
          ? state.auto_forced_players.length
            ? state.auto_forced_players.join(", ")
            : "なし"
          : "無効"}
      </p>

      <h3>直近抽選の内訳</h3>
      {Object.keys(grouped).length === 0 ? (
        <p>なし</p>
      ) : (
        <ul>
          {Object.entries(grouped).map(([reason, names]) => (
            <li key={reason}>
              {REASON_LABEL[reason] ?? reason}: {names.join(", ")}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};
