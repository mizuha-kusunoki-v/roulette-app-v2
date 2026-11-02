import { useEffect, useState } from "react";
import { fetchState, resetState } from "./api/client";
import { RouletteResult, RouletteState } from "./types";
import { DrawSettings } from "./components/DrawSettings";
import { DuplicatePairs } from "./components/DuplicatePairs";
import { HistoryList } from "./components/HistoryList";
import { MatchInfo } from "./components/MatchInfo";
import { OrganizerSettings } from "./components/OrganizerSettings";
import { ParticipantManager } from "./components/ParticipantManager";
import { RouletteController } from "./components/RouletteController";
import { RouletteDisplay } from "./components/RouletteDisplay";

const AdminApp = () => {
  const [state, setState] = useState<RouletteState | null>(null);
  const [result, setResult] = useState<RouletteResult | null>(null);

  const reload = async () => {
    const nextState = await fetchState();
    setState(nextState);
    setResult(nextState.result);
  };

  useEffect(() => {
    reload();
  }, []);

  useEffect(() => {
    const ws = new WebSocket("ws://127.0.0.1:8000/ws");

    ws.onmessage = (e) => {
      const incoming = JSON.parse(e.data) as RouletteState;
      setState(incoming);
      setResult(incoming.result);
    };

    return () => ws.close();
  }, []);

  const handleReset = async () => {
    if (state?.phase === "spinning") return;
    await resetState();
    await reload();
  };

  const isLocked = state?.phase === "spinning";

  if (!state) return <p>Loading...</p>;

  return (
    <div>
      <h1>Roulette Admin</h1>

      <OrganizerSettings
        organizerMode={state.organizer_mode}
        organizers={state.organizers}
        selectedOrganizerIndices={state.selected_organizer_indices}
        disabled={isLocked}
        onUpdated={reload}
      />

      <ParticipantManager
        participants={state.participants}
        forcedPlayers={state.forced_players}
        forcedPlayerTeams={state.forced_player_teams}
        autoForcedPlayers={state.auto_forced_players}
        excludedPlayers={state.excluded_players}
        participationCounts={state.participation_counts}
        organizerMode={state.organizer_mode}
        onUpdated={reload}
      />

      <DrawSettings
        missThreshold={state.miss_threshold}
        enableAutoForce={state.enable_auto_force}
        disabled={isLocked}
        onUpdated={reload}
      />

      <RouletteController
        organizerMode={state.organizer_mode}
        organizers={state.organizers}
        forcedPlayers={state.forced_players}
        onResult={setResult}
        onUpdated={reload}
        disabled={isLocked}
      />
      <button onClick={handleReset} disabled={isLocked}>
        リセット
      </button>

      <RouletteDisplay
        result={result}
        organizers={state.organizers}
        organizerMode={state.organizer_mode}
        selectedOrganizerIndices={state.selected_organizer_indices}
      />
      <MatchInfo state={state} />

      <DuplicatePairs pairCounts={state.pair_counts} />

      <HistoryList history={state.history} disabled={isLocked} onUpdated={reload} />
    </div>
  );
};

export default AdminApp;
