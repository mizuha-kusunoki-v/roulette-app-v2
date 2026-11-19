import { useEffect, useRef, useState } from "react";
import { SessionState } from "../types";

/**
 * 抽選演出の間だけ、演出中の回の ID を返す (演出中でなければ null)。
 * 管理画面 (操作を止める間) とビュワー (スロット演出を出す間) が同じ判定を使う。
 *
 * - 最初に受け取った状態は、そのまま見せる (演出しない)
 * - そのあとで、履歴にまだなかった回が届いたときだけ演出する。自分の抽選でも、ほかの管理画面の抽選でも同じ
 * - 演出の間にさらに新しい回が届いたら、その回で最初からやり直す
 * - 長さは受け取った状態の presentation_duration_ms (バックエンドの設定)。画面側では決めない
 * - 終わりはこの画面の中のタイマーで決めるので、サーバーや通信の様子に関わらず必ず戻る
 *
 * 最新の回を履歴から消して前の回が最新に戻っても、その回は履歴にあったので演出しない。
 */
export function useRoundAnimation(state: SessionState | null): string | null {
  const [animatingRoundId, setAnimatingRoundId] = useState<string | null>(null);
  const knownRoundIds = useRef<Set<string> | null>(null);
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => {
    if (!state) return;
    const known = knownRoundIds.current;
    const current = state.current_round;
    knownRoundIds.current = new Set(state.history.map((r) => r.round_id));
    if (known === null || !current || known.has(current.round_id)) return;

    window.clearTimeout(timer.current);
    setAnimatingRoundId(current.round_id);
    timer.current = window.setTimeout(() => setAnimatingRoundId(null), Math.max(0, state.presentation_duration_ms));
  }, [state]);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  return animatingRoundId;
}
