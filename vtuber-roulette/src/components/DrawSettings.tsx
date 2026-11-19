import { useEffect, useState } from "react";
import { updateDrawSettings } from "../api/client";
import { SessionState } from "../types";

interface Props {
  settings: SessionState["settings"];
  disabled: boolean;
  onUpdated: () => void;
}

export const DrawSettings = ({ settings, disabled, onUpdated }: Props) => {
  const [threshold, setThreshold] = useState(settings.miss_threshold);
  const [autoForce, setAutoForce] = useState(settings.enable_auto_force);

  useEffect(() => { setThreshold(settings.miss_threshold); }, [settings.miss_threshold]);
  useEffect(() => { setAutoForce(settings.enable_auto_force); }, [settings.enable_auto_force]);

  const save = async () => {
    await updateDrawSettings(threshold, autoForce);
    await onUpdated();
  };

  return (
    <div>
      <h2>抽選設定</h2>

      <div>
        <label>
          連続未抽選の救済閾値：
          <input
            type="number"
            min={1}
            max={20}
            value={threshold}
            onChange={(e) => setThreshold(Math.max(1, Number(e.target.value)))}
            disabled={disabled}
            style={{ width: 60, marginLeft: 8 }}
          />
          回
        </label>
        <p style={{ fontSize: 13, margin: "4px 0 0" }}>
          この回数連続で抽選されなかった参加者を優先選出します。
        </p>
      </div>

      <div style={{ marginTop: 12 }}>
        <label>
          <input
            type="checkbox"
            checked={autoForce}
            onChange={(e) => setAutoForce(e.target.checked)}
            disabled={disabled}
          />
          {" "}
          参加回数の中央値乖離による自動強制を有効にする
        </label>
        <p style={{ fontSize: 13, margin: "4px 0 0" }}>
          参加回数が中央値を大きく下回る参加者を自動的に優先選出します。
        </p>
      </div>

      <button onClick={save} disabled={disabled} style={{ marginTop: 12 }}>
        抽選設定を保存
      </button>
    </div>
  );
};
