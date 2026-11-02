import { deleteHistoryRecord } from "../api/client";
import { DrawRecord } from "../types";

interface Props {
  history: DrawRecord[];
  disabled: boolean;
  onUpdated: () => void;
}

export const HistoryList = ({ history, disabled, onUpdated }: Props) => {
  const remove = async (record: DrawRecord, number: number) => {
    if (!window.confirm(`第${number}回の抽選結果を削除します。参加回数などは再計算されます。よろしいですか？`)) {
      return;
    }
    try {
      await deleteHistoryRecord(record.round_id);
      onUpdated();
    } catch (error) {
      window.alert(error instanceof Error ? error.message : "削除に失敗しました。");
    }
  };

  const saveJson = () => {
    const json = JSON.stringify(history, null, 2);
    const blob = new Blob([json], { type: "application/json;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    const stamp = new Date().toISOString().replace(/[-:]/g, "").slice(0, 15);
    link.href = url;
    link.download = `draw_history_${stamp}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div>
      <h2>抽選履歴</h2>
      <button onClick={saveJson} disabled={history.length === 0}>
        JSONに保存
      </button>
      {history.length === 0 ? (
        <p>履歴はありません。</p>
      ) : (
        <ul>
          {history.map((record, index) => (
            <li key={record.round_id}>
              第{index + 1}回（{new Date(record.drawn_at).toLocaleString()}）:{" "}
              {record.result.teams
                .map((team) => `${team.label}: ${team.players.join(", ")}`)
                .join(" / ")}{" "}
              <button onClick={() => remove(record, index + 1)} disabled={disabled}>
                削除
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};
