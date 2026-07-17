import { draw } from "../api/client";
import { DrawMode, OrganizerMode, RouletteResult } from "../types";

interface Props {
  organizerMode: OrganizerMode;
  organizers: string[];
  forcedPlayers: string[];
  onResult: (r: RouletteResult) => void;
  onUpdated: () => void;
  disabled?: boolean;
}

export const RouletteController = ({
  organizerMode,
  organizers,
  forcedPlayers,
  onResult,
  onUpdated,
  disabled = false,
}: Props) => {
  const hasTwoHosts = organizers.filter((name) => name.trim()).length >= 2;
  const hostDrawDisabled = disabled || !hasTwoHosts;
  const standard3Disabled = disabled || forcedPlayers.length > 3;

  const exec = async (mode: DrawMode) => {
    if (disabled) return;

    try {
      const result = await draw(mode);
      onResult(result);
      onUpdated();
    } catch (error) {
      const message = error instanceof Error ? error.message : "抽選に失敗しました。";
      window.alert(message);
    }
  };

  return (
    <div>
      <h2>抽選</h2>
      {organizerMode === "single" ? (
        <>
          <button onClick={() => exec("standard_3")} disabled={standard3Disabled}>3人抽選</button>
          {standard3Disabled && !disabled && <span>手動強制が4人のため3人抽選は実行できません</span>}
          <button onClick={() => exec("standard_4")} disabled={disabled}>4人抽選</button>
        </>
      ) : (
        <>
          <button onClick={() => exec("hosts_vs_duo")} disabled={hostDrawDisabled}>
            主催2人 vs 抽選2人
          </button>
          <button onClick={() => exec("hosts_split_pairs")} disabled={hostDrawDisabled}>
            主催別チームのペア抽選
          </button>
          {!hasTwoHosts && <p>主催2人モードでは主催名を2人分入力してください。</p>}
        </>
      )}
    </div>
  );
};
