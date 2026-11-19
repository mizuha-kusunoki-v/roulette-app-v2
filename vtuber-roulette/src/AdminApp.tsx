import { useEffect, useState } from "react";
import { fetchSession, resetState } from "./api/client";
import { wsUrl } from "./api/endpoint";
import { SessionState } from "./types";
import { DrawSettings } from "./components/DrawSettings";
import { HistoryList } from "./components/HistoryList";
import { MatchInfo } from "./components/MatchInfo";
import { OrganizerSettings } from "./components/OrganizerSettings";
import { ParticipantManager } from "./components/ParticipantManager";
import { RouletteController } from "./components/RouletteController";
import { RouletteDisplay } from "./components/RouletteDisplay";

const AdminApp = () => {
  const [session, setSession] = useState<SessionState | null>(null);

  const reload = async () => {
    setSession(await fetchSession());
  };

  useEffect(() => {
    reload();
  }, []);

  useEffect(() => {
    const ws = new WebSocket(wsUrl("/ws/session"));

    ws.onmessage = (e) => {
      setSession(JSON.parse(e.data) as SessionState);
    };

    return () => ws.close();
  }, []);

  const isLocked = session?.phase === "spinning";

  const handleReset = async () => {
    if (isLocked) return;
    await resetState();
    await reload();
  };

  if (!session) return <p>Loading...</p>;

  return (
    <div>
      <h1>Roulette Admin</h1>

      <OrganizerSettings
        organizerMode={session.organizer_mode}
        organizers={session.organizers}
        disabled={isLocked}
        onUpdated={reload}
      />

      <ParticipantManager
        participants={session.participants}
        forcedLimit={session.settings.forced_limit}
        onUpdated={reload}
      />

      <DrawSettings settings={session.settings} disabled={isLocked} onUpdated={reload} />

      <RouletteController drawOptions={session.draw_options} locked={isLocked} onUpdated={reload} />
      <button onClick={handleReset} disabled={isLocked}>
        リセット
      </button>

      <RouletteDisplay result={session.current_round?.result ?? null} organizers={session.organizers} />
      <MatchInfo session={session} />

      <HistoryList history={session.history} disabled={isLocked} onUpdated={reload} />
    </div>
  );
};

export default AdminApp;
