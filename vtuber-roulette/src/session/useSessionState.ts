import { useCallback, useEffect, useState } from "react";
import { fetchSession } from "../api/client";
import { wsUrl } from "../api/endpoint";
import { SessionState } from "../types";

// 管理画面とビュワーが共通で使う、サーバーの状態の受け取り方。
// - GET /session と WebSocket のどちらから届いても、新しい方だけを採用する (acceptNewer)
// - WebSocket が切れたら、間隔を空けながら繋ぎ直し、繋がったら状態を読み直す

const RECONNECT_MIN_MS = 1000;
const RECONNECT_MAX_MS = 10000;

/**
 * 届いた状態 (incoming) と持っている状態 (current) のうち、採用する方を返す。
 * 状態の新しさは revision で比べる。version は書き込みのたびに増えるので、同じ instance_id なら大きい方が新しい。
 * サーバーを起動し直すと version は 0 に戻るが、instance_id も変わるので、ID が違うときは比べずに届いた方を採用する。
 * (version だけで比べると、起動し直したあとの状態をすべて古いとして捨ててしまう)
 */
export function acceptNewer(current: SessionState | null, incoming: SessionState): SessionState {
  if (current === null) return incoming;
  const a = current.revision;
  const b = incoming.revision;
  if (a.instance_id !== b.instance_id) return incoming;
  return b.version > a.version ? incoming : current;
}

// connecting: まだ一度もつながっていない / open: つながっている / lost: 切れた (またはつながらなかった) ので、つなぎ直している
export type Connection = "connecting" | "open" | "lost";

export function reconnectDelay(failures: number): number {
  return Math.min(RECONNECT_MIN_MS * 2 ** failures, RECONNECT_MAX_MS);
}

export function useSessionState() {
  const [state, setState] = useState<SessionState | null>(null);
  const [connection, setConnection] = useState<Connection>("connecting");

  const accept = useCallback((incoming: SessionState) => {
    setState((current) => acceptNewer(current, incoming));
  }, []);

  // 操作のあとなどに、状態を読み直す。応答が WebSocket の新しい状態より遅れて届いても、捨てられる。
  // 失敗しても例外にしない: WebSocket が繋がっていれば次の変更で、切れていれば繋ぎ直したときに読み直す
  const refresh = useCallback(async () => {
    try {
      accept(await fetchSession());
    } catch {
      // 上のとおり、ここで読めなくても追いつく
    }
  }, [accept]);

  useEffect(() => {
    let disposed = false;
    let socket: WebSocket | null = null;
    let timer: number | undefined;
    let failures = 0;

    const connect = () => {
      const ws = new WebSocket(wsUrl("/ws/session"));
      socket = ws;
      ws.onopen = () => {
        failures = 0;
        setConnection("open");
        // 切れている間の変更を取りこぼさないよう、繋がったら読み直す (接続直後に WebSocket でも届く)
        fetchSession().then(accept, () => {});
      };
      ws.onmessage = (e) => accept(JSON.parse(e.data) as SessionState);
      ws.onclose = () => {
        if (disposed) return;
        setConnection("lost");
        timer = window.setTimeout(connect, reconnectDelay(failures));
        failures += 1;
      };
    };

    // 最初の状態は WebSocket を待たずに読む (サーバーが落ちていれば失敗して、繋がったときの読み直しに任せる)
    fetchSession().then(accept, () => {});
    connect();

    return () => {
      disposed = true;
      window.clearTimeout(timer);
      socket?.close();
    };
  }, [accept]);

  return { state, connection, refresh };
}
