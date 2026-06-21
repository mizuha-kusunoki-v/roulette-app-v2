import { useEffect, useRef, useState } from "react";
import { notifyPresentationComplete } from "../api/client";
import { RouletteState } from "../types";
import { getDisplayTeams } from "../utils/resultDisplay";
import "./roulette.css";

const ANIMATION_DURATION_MS = 5000;

export const ResultViewerPage = () => {
  const [serverState, setServerState] = useState<RouletteState | null>(null);
  const [displayName, setDisplayName] = useState<string>("");
  const [animating, setAnimating] = useState(false);

  const lastRoundIdRef = useRef<string | null>(null);
  const completedRoundIdRef = useRef<string | null>(null);
  const intervalRef = useRef<number | null>(null);

  useEffect(() => {
    const ws = new WebSocket("ws://127.0.0.1:8000/ws");
    ws.onmessage = (e) => {
      const incoming = JSON.parse(e.data) as RouletteState;
      setServerState(incoming);
    };
    return () => ws.close();
  }, []);

  useEffect(() => {
    return () => {
      if (intervalRef.current !== null) clearInterval(intervalRef.current);
    };
  }, []);

  useEffect(() => {
    if (!serverState?.round_id || !serverState.result) return;
    if (serverState.phase !== "spinning") return;
    if (serverState.round_id === lastRoundIdRef.current) return;

    lastRoundIdRef.current = serverState.round_id;
    const roundId = serverState.round_id;
    const candidates = [...serverState.participants];

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

  if (!serverState.result) {
    return (
      <div className="viewer-screen viewer-center">
        <div className="status-panel">抽選結果待機中</div>
      </div>
    );
  }

  const teams = getDisplayTeams(
    serverState.result,
    serverState.organizers,
    serverState.organizer_mode,
    serverState.selected_organizer_index,
  );

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
