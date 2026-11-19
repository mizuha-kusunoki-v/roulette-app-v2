import { useEffect, useRef, useState } from "react";
import { useRoundAnimation } from "../session/useRoundAnimation";
import { useSessionState } from "../session/useSessionState";
import { getDisplayTeams } from "../utils/resultDisplay";
import "./roulette.css";

const SLOT_INTERVAL_MS = 80;

export const ResultViewerPage = () => {
  const { state } = useSessionState();
  const animatingRoundId = useRoundAnimation(state);
  const [displayName, setDisplayName] = useState<string>("");

  // 演出の間に入れ替える名前は、そのときの参加者から選ぶ
  const stateRef = useRef(state);
  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  useEffect(() => {
    if (animatingRoundId === null) return;
    const id = window.setInterval(() => {
      const names = stateRef.current?.participants.map((p) => p.name) ?? [];
      if (names.length > 0) setDisplayName(names[Math.floor(Math.random() * names.length)]);
    }, SLOT_INTERVAL_MS);
    return () => window.clearInterval(id);
  }, [animatingRoundId]);

  if (!state) return <p>Loading...</p>;

  // 演出中の回がリセットや削除でなくなったら、演出は出さない
  if (animatingRoundId !== null && state.current_round?.round_id === animatingRoundId) {
    return (
      <div className="viewer-screen viewer-center">
        <div className="status-panel">抽選中...</div>
        <div className="slot-display">{displayName}</div>
      </div>
    );
  }

  if (!state.current_round) {
    return (
      <div className="viewer-screen viewer-center">
        <div className="status-panel">抽選結果待機中</div>
      </div>
    );
  }

  const teams = getDisplayTeams(state.current_round.result, state.organizers);

  return (
    <div className="viewer-screen viewer-center">
      <div className="result-panel">
        <h1 className="result-title">抽選結果</h1>
        {teams.map((team, index) => (
          <p
            key={team.label}
            className={`result-team ${index === 0 ? "team-a" : "team-b"}`}
          >
            {team.label}: {team.players.join(" / ")}
          </p>
        ))}
      </div>
    </div>
  );
};
