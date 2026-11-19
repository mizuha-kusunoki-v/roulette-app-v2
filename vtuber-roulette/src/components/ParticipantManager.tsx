import { ChangeEvent, useRef, useState } from "react";
import { addParticipant, removeParticipant, replaceParticipants, setExcluded, setForced } from "../api/client";
import { ForcedTeam, ParticipantStatus } from "../types";

// 画面の選択肢の値。"none" はチーム指定なし (プロトコルでは "any")
type TeamChoice = "none" | "A" | "B";
const toChoice = (forced: ForcedTeam): TeamChoice => (forced === "any" ? "none" : forced);
const fromChoice = (choice: TeamChoice): ForcedTeam => (choice === "none" ? "any" : choice);

const reportError = (error: unknown) =>
  window.alert(error instanceof Error ? error.message : "操作に失敗しました。");

interface Props {
  participants: ParticipantStatus[];
  forcedLimit: number;
  onUpdated: () => void;
}

function parseCsvLines(text: string): string[] {
  const names: string[] = [];

  text
    .replace(/^﻿/, "")
    .split(/\r?\n/)
    .forEach((line) => {
      const trimmed = line.trim();
      if (!trimmed) return;

      const unquoted = trimmed.replace(/^"(.*)"$/, "$1").trim();
      if (unquoted && !names.includes(unquoted)) {
        names.push(unquoted);
      }
    });

  return names;
}

export const ParticipantManager = ({ participants: statuses, forcedLimit, onUpdated }: Props) => {
  const [name, setName] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const participants = statuses.map((p) => p.name);
  const forcedCount = statuses.filter((p) => p.forced !== null).length;

  const run = async (operation: () => Promise<void>) => {
    try {
      await operation();
      onUpdated();
    } catch (error) {
      reportError(error);
    }
  };

  const add = async () => {
    const trimmed = name.trim();
    if (!trimmed || participants.includes(trimmed)) return;

    await run(async () => {
      await addParticipant(trimmed);
      setName("");
    });
  };

  const remove = (target: string) => run(() => removeParticipant(target));

  const toggleForced = (status: ParticipantStatus) => {
    if (status.forced !== null) return run(() => setForced(status.name, null));
    if (forcedCount >= forcedLimit) return;
    return run(() => setForced(status.name, "any"));
  };

  const setForcedTeam = (target: string, choice: TeamChoice) => run(() => setForced(target, fromChoice(choice)));

  const toggleExcluded = (status: ParticipantStatus) => run(() => setExcluded(status.name, !status.excluded));

  const handleCsvImport = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      const text = await file.text();
      const imported = parseCsvLines(text);
      await run(() => replaceParticipants(imported));
    } finally {
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const exportCsv = () => {
    const csv = participants.join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "participants.csv";
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div>
      <h2>参加者管理</h2>
      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="参加者名を入力"
      />
      <button onClick={add}>追加</button>

      <div>
        <label>
          CSV取り込み
          {" "}
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv,text/csv"
            onChange={handleCsvImport}
          />
        </label>
        {" "}
        <button onClick={exportCsv} disabled={participants.length === 0}>
          CSV書き出し
        </button>
      </div>

      <ul>
        {statuses.map((status) => {
          const player = status.name;
          const checkedForced = status.forced !== null;
          const disabledForced = !checkedForced && forcedCount >= forcedLimit;
          const checkedExcluded = status.excluded;
          const currentTeam: TeamChoice = status.forced === null ? "none" : toChoice(status.forced);

          return (
            <li key={player}>
              <input
                type="checkbox"
                checked={checkedForced}
                disabled={disabledForced}
                onChange={() => toggleForced(status)}
              />{" "}
              強制
              {checkedForced && (
                <select
                  value={currentTeam}
                  onChange={(e) => setForcedTeam(player, e.target.value as TeamChoice)}
                  style={{ marginLeft: 4 }}
                >
                  <option value="none">チーム指定なし</option>
                  <option value="A">チームA固定</option>
                  <option value="B">チームB固定</option>
                </select>
              )}
              {" "}
              <input
                type="checkbox"
                checked={checkedExcluded}
                onChange={() => toggleExcluded(status)}
              />{" "}
              除外
              {" "}
              {player} (参加回数: {status.participation_count}){" "}
              {status.auto_forced && <span>[自動強制対象]</span>}{" "}
              {checkedForced && <span>[手動強制{currentTeam !== "none" ? `・チーム${currentTeam}固定` : ""}]</span>}{" "}
              {checkedExcluded && <span>[除外中]</span>}{" "}
              <button onClick={() => remove(player)}>削除</button>
            </li>
          );
        })}
      </ul>
      <p>CSV は参加者1人1行で読み書きします。手動強制は最大{forcedLimit}人まで選択できます（主催2人モード時は2人まで）。</p>
    </div>
  );
};
