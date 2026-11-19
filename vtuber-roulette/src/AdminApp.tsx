import { resetState } from "./api/client";
import { DrawSettings } from "./components/DrawSettings";
import { HistoryList } from "./components/HistoryList";
import { MatchInfo } from "./components/MatchInfo";
import { OrganizerSettings } from "./components/OrganizerSettings";
import { ParticipantManager } from "./components/ParticipantManager";
import { RouletteController } from "./components/RouletteController";
import { RouletteDisplay } from "./components/RouletteDisplay";
import { useRoundAnimation } from "./session/useRoundAnimation";
import { useSessionState } from "./session/useSessionState";

const AdminApp = () => {
  const { state: session, connection, refresh: reload } = useSessionState();

  // 抽選の演出が続いている間 (自分の抽選でも、ほかの管理画面の抽選でも) だけ、抽選・履歴の削除・リセットを止める。
  // サーバーは演出を待たないので、これはこの画面だけの規則で、タイマーが終われば必ず戻る
  const isLocked = useRoundAnimation(session) !== null;

  const handleReset = async () => {
    if (isLocked) return;
    await resetState();
    await reload();
  };

  if (!session) return <p>Loading...</p>;

  return (
    <div>
      <h1>Roulette Admin</h1>
      {connection === "connecting" && <p role="status">サーバーに接続しています...</p>}
      {connection === "lost" && <p role="alert">サーバーとの接続が切れています。再接続しています...</p>}

      <OrganizerSettings
        organizerMode={session.organizer_mode}
        organizers={session.organizers}
        onUpdated={reload}
      />

      <ParticipantManager
        participants={session.participants}
        forcedLimit={session.settings.forced_limit}
        onUpdated={reload}
      />

      <DrawSettings settings={session.settings} onUpdated={reload} />

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
