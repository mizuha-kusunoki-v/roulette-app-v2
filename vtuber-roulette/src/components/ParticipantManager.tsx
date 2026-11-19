import { ChangeEvent, useRef, useState } from "react";
import { updateExcludedPlayers, updateForcedPlayers, updateParticipants } from "../api/client";
import { ParticipantStatus } from "../types";

type RequestTeam = "none" | "A" | "B";

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

  // 書き込み API はまだリスト全体を受け取る形なので、送るリストを参加者ごとの状態から組み立てる
  const participants = statuses.map((p) => p.name);
  const forcedPlayers = statuses.filter((p) => p.forced !== null).map((p) => p.name);
  const forcedPlayerTeams: Record<string, RequestTeam> = Object.fromEntries(
    statuses.flatMap((p) => (p.forced === null ? [] : [[p.name, p.forced === "any" ? "none" : p.forced]])),
  );
  const excludedPlayers = statuses.filter((p) => p.excluded).map((p) => p.name);

  const add = async () => {
    const trimmed = name.trim();
    if (!trimmed || participants.includes(trimmed)) return;

    await updateParticipants([...participants, trimmed]);
    setName("");
    onUpdated();
  };

  const remove = async (target: string) => {
    await updateParticipants(participants.filter((p) => p !== target));
    onUpdated();
  };

  const toggleForced = async (target: string) => {
    if (forcedPlayers.includes(target)) {
      const newForced = forcedPlayers.filter((p) => p !== target);
      const newTeams = { ...forcedPlayerTeams };
      delete newTeams[target];
      await updateForcedPlayers(newForced, newTeams);
      onUpdated();
      return;
    }

    if (forcedPlayers.length >= forcedLimit) return;

    await updateForcedPlayers([...forcedPlayers, target], forcedPlayerTeams);
    onUpdated();
  };

  const setForcedTeam = async (target: string, team: RequestTeam) => {
    const newTeams = { ...forcedPlayerTeams, [target]: team };
    await updateForcedPlayers(forcedPlayers, newTeams);
    onUpdated();
  };

  const toggleExcluded = async (target: string) => {
    const exists = excludedPlayers.includes(target);
    if (exists) {
      await updateExcludedPlayers(excludedPlayers.filter((p) => p !== target));
      onUpdated();
      return;
    }

    await updateExcludedPlayers([...excludedPlayers, target]);
    onUpdated();
  };

  const handleCsvImport = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      const text = await file.text();
      const imported = parseCsvLines(text);
      await updateParticipants(imported);
      await onUpdated();
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
          const disabledForced = !checkedForced && forcedPlayers.length >= forcedLimit;
          const checkedExcluded = status.excluded;
          const currentTeam = forcedPlayerTeams[player] ?? "none";

          return (
            <li key={player}>
              <input
                type="checkbox"
                checked={checkedForced}
                disabled={disabledForced}
                onChange={() => toggleForced(player)}
              />{" "}
              強制
              {checkedForced && (
                <select
                  value={currentTeam}
                  onChange={(e) => setForcedTeam(player, e.target.value as RequestTeam)}
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
                onChange={() => toggleExcluded(player)}
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
