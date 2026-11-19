import { useEffect, useRef, useState } from "react";
import { notifyPresentationComplete } from "../api/client";
import { useSessionState } from "../session/useSessionState";
import { getDisplayTeams } from "../utils/resultDisplay";
import "./roulette.css";

const ANIMATION_DURATION_MS = 5000;

export const ResultViewerPage = () => {
  const { state: serverState } = useSessionState();
  const [displayName, setDisplayName] = useState<string>("");
  const [animating, setAnimating] = useState(false);

  const lastRoundIdRef = useRef<string | null>(null);
  const completedRoundIdRef = useRef<string | null>(null);
  const intervalRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (intervalRef.current !== null) clearInterval(intervalRef.current);
    };
  }, []);

  useEffect(() => {
    const round = serverState?.current_round;
    if (!serverState || !round) return;
    if (serverState.phase !== "spinning") return;
    if (round.round_id === lastRoundIdRef.current) return;

    lastRoundIdRef.current = round.round_id;
    const roundId = round.round_id;
    const candidates = serverState.participants.map((p) => p.name);

    if (intervalRef.current !== null) clearInterval(intervalRef.current);

    setAnimating(true);
    const startTime = Date.now();

    intervalRef.current = window.setInterval(() => {
      const elapsed = Date.now() - startTime;
      if (elapsed >= ANIMATION_DURATION_MS) {
        clearInterval(intervalRef.current!);
        intervalRef.current = null;
        setAnimating(false);
        if (completedRoundIdRef.current !== roundId) {
          completedRoundIdRef.current = roundId;
          notifyPresentationComplete(roundId);
        }
        return;
      }
      setDisplayName(candidates[Math.floor(Math.random() * candidates.length)]);
    }, 80);
  }, [serverState]);

  if (!serverState) return <p>Loading...</p>;

  if (animating) {
    return (
      <div className="viewer-screen viewer-center">
        <div className="status-panel">抽選中...</div>
        <div className="slot-display">{displayName}</div>
      </div>
    );
  }

  if (serverState.phase === "spinning") {
    return (
      <div className="viewer-screen viewer-center">
        <div className="status-panel">抽選中</div>
      </div>
    );
  }

  if (!serverState.current_round) {
    return (
      <div className="viewer-screen viewer-center">
        <div className="status-panel">抽選結果待機中</div>
      </div>
    );
  }

  const teams = getDisplayTeams(serverState.current_round.result, serverState.organizers);

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
