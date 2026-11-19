import { useEffect, useState } from "react";
import { updateOrganizerConfig } from "../api/client";
import { Organizer, OrganizerMode } from "../types";

const MAX_ORGANIZERS = 10;

interface Props {
  organizerMode: OrganizerMode;
  organizers: Organizer[];
  disabled: boolean;
  onUpdated: () => void;
}

export const OrganizerSettings = ({ organizerMode, organizers: savedOrganizers, disabled, onUpdated }: Props) => {
  // 保存済みの主催。編集中の値 (hosts, selectedIndices) はこの画面の中だけで持ち、保存で送る
  const organizers = savedOrganizers.map((o) => o.name);
  const activeIndices = savedOrganizers.flatMap((o, i) => (o.active ? [i] : []));
  // 誰も選ばれていなければ先頭を選んだ状態から始める (主催を初めて追加したとき、その人が選ばれた状態になる)
  const selectedOrganizerIndices = activeIndices.length > 0 ? activeIndices : [0];

  const [mode, setMode] = useState<OrganizerMode>(organizerMode);
  const [hosts, setHosts] = useState<string[]>(organizers);
  const [selectedIndices, setSelectedIndices] = useState<number[]>(selectedOrganizerIndices);
  const [newName, setNewName] = useState("");

  useEffect(() => { setMode(organizerMode); }, [organizerMode]);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { setHosts(organizers); }, [JSON.stringify(organizers)]);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { setSelectedIndices(selectedOrganizerIndices); }, [JSON.stringify(selectedOrganizerIndices)]);

  const requiredCount = mode === "double" ? 2 : 1;
  const canSave =
    !disabled &&
    selectedIndices.length === requiredCount &&
    selectedIndices.every((i) => i >= 0 && i < hosts.length);

  const addHost = () => {
    const trimmed = newName.trim();
    if (!trimmed || hosts.includes(trimmed) || hosts.length >= MAX_ORGANIZERS) return;
    setHosts([...hosts, trimmed]);
    setNewName("");
  };

  const removeHost = (index: number) => {
    const next = hosts.filter((_, i) => i !== index);
    setHosts(next);
    setSelectedIndices(
      selectedIndices
        .filter((i) => i !== index)
        .map((i) => (i > index ? i - 1 : i)),
    );
  };

  const toggleSelect = (index: number) => {
    if (mode === "single") {
      setSelectedIndices([index]);
      return;
    }
    if (selectedIndices.includes(index)) {
      setSelectedIndices(selectedIndices.filter((i) => i !== index));
    } else if (selectedIndices.length < 2) {
      setSelectedIndices([...selectedIndices, index]);
    }
  };

  const save = async () => {
    await updateOrganizerConfig(mode, hosts, selectedIndices);
    await onUpdated();
  };

  const exportCsv = () => {
    const blob = new Blob([hosts.join("\n")], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "organizers.csv";
    link.click();
    URL.revokeObjectURL(url);
  };

  const validationMessage = () => {
    if (selectedIndices.length < requiredCount) {
      return `主催を${requiredCount}人選択してください（現在${selectedIndices.length}人）`;
    }
    return null;
  };

  return (
    <div>
      <h2>主催設定</h2>

      <label>
        <input
          type="radio"
          name="organizerMode"
          checked={mode === "single"}
          onChange={() => {
            setMode("single");
            setSelectedIndices(selectedIndices.slice(0, 1));
          }}
          disabled={disabled}
        />
        主催1人
      </label>
      {" "}
      <label>
        <input
          type="radio"
          name="organizerMode"
          checked={mode === "double"}
          onChange={() => setMode("double")}
          disabled={disabled}
        />
        主催2人
      </label>

      <div style={{ marginTop: 8 }}>
        <input
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && addHost()}
          placeholder="主催名を入力"
          disabled={disabled || hosts.length >= MAX_ORGANIZERS}
        />
        {" "}
        <button
          onClick={addHost}
          disabled={disabled || !newName.trim() || hosts.length >= MAX_ORGANIZERS}
        >
          追加
        </button>
        {" "}
        <button onClick={exportCsv} disabled={hosts.length === 0}>
          CSV書き出し
        </button>
      </div>

      <ul style={{ marginTop: 8 }}>
        {hosts.map((name, i) => {
          const checked = selectedIndices.includes(i);
          const checkDisabled =
            disabled ||
            (!checked && mode === "double" && selectedIndices.length >= 2);

          return (
            <li key={i}>
              <label>
                <input
                  type={mode === "single" ? "radio" : "checkbox"}
                  name="selectedOrganizer"
                  checked={checked}
                  disabled={checkDisabled}
                  onChange={() => toggleSelect(i)}
                />
                {" "}
                {name}
              </label>
              {" "}
              <button onClick={() => removeHost(i)} disabled={disabled}>
                削除
              </button>
            </li>
          );
        })}
      </ul>

      {hosts.length === 0 && <p>主催名を追加してください。</p>}

      {validationMessage() && <p>{validationMessage()}</p>}

      <button onClick={save} disabled={!canSave}>
        主催設定を保存
      </button>
    </div>
  );
};
