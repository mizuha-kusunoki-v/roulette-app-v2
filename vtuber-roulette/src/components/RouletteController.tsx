import { draw } from "../api/client";
import { DrawMode, DrawOption } from "../types";

const MODE_LABEL: Record<DrawMode, string> = {
  standard_3: "3人抽選",
  standard_4: "4人抽選",
  hosts_vs_duo: "主催2人 vs 抽選2人",
  hosts_split_pairs: "主催別チームのペア抽選",
};

interface Props {
  drawOptions: DrawOption[];
  locked: boolean; // 抽選演出中
  onUpdated: () => void;
}

export const RouletteController = ({ drawOptions, locked, onUpdated }: Props) => {
  const exec = async (mode: DrawMode) => {
    try {
      await draw(mode);
      onUpdated();
    } catch (error) {
      const message = error instanceof Error ? error.message : "抽選に失敗しました。";
      window.alert(message);
    }
  };

  // 実行できない理由はサーバーが返す。演出中はどれも実行できないので、理由は出さない
  const reasons = locked
    ? []
    : Array.from(new Set(drawOptions.flatMap((o) => (o.unavailable_reason ? [o.unavailable_reason] : []))));

  return (
    <div>
      <h2>抽選</h2>
      {drawOptions.map((option) => (
        <button key={option.mode} onClick={() => exec(option.mode)} disabled={!option.available}>
          {MODE_LABEL[option.mode]}
        </button>
      ))}
      {reasons.map((reason) => (
        <p key={reason}>{reason}</p>
      ))}
    </div>
  );
};
