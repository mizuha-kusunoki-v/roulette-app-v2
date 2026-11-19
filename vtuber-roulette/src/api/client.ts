import type { components } from "./schema";
import { DrawMode, ForcedTeam, Organizer, OrganizerMode, SessionState } from "../types";
import { apiUrl } from "./endpoint";

type Schemas = components["schemas"];

async function ensureOk(res: Response) {
  if (res.ok) return;

  let message = "リクエストに失敗しました。";
  try {
    const data = await res.json();
    message = data.detail ?? data.reason ?? message;
  } catch {
    message = res.statusText || message;
  }
  throw new Error(message);
}

// 本文の型は OpenAPI から生成した型に合わせる。形がずれると型チェックで失敗する
async function send<T>(method: "POST" | "PUT", path: string, body: T) {
  const res = await fetch(apiUrl(path), {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  await ensureOk(res);
}

export async function fetchSession(): Promise<SessionState> {
  const res = await fetch(apiUrl("/session"));
  await ensureOk(res);
  return res.json();
}

export const replaceParticipants = (names: string[]) =>
  send<Schemas["ReplaceParticipantsRequest"]>("PUT", "/participants", { names });

export const addParticipant = (name: string) =>
  send<Schemas["ParticipantRequest"]>("POST", "/participants/add", { name });

export const removeParticipant = (name: string) =>
  send<Schemas["ParticipantRequest"]>("POST", "/participants/remove", { name });

export const setForced = (name: string, forced: ForcedTeam | null) =>
  send<Schemas["SetForcedRequest"]>("POST", "/participants/forced", { name, forced });

export const setExcluded = (name: string, excluded: boolean) =>
  send<Schemas["SetExcludedRequest"]>("POST", "/participants/excluded", { name, excluded });

export const saveOrganizers = (organizerMode: OrganizerMode, organizers: Organizer[]) =>
  send<Schemas["SaveOrganizersRequest"]>("PUT", "/organizers", { organizer_mode: organizerMode, organizers });

export const saveSettings = (missThreshold: number, enableAutoForce: boolean) =>
  send<Schemas["SaveSettingsRequest"]>("PUT", "/settings", {
    miss_threshold: missThreshold,
    enable_auto_force: enableAutoForce,
  });

export const draw = (mode: DrawMode) => send<Schemas["DrawRequest"]>("POST", "/draw", { mode });

export async function resetState() {
  const res = await fetch(apiUrl("/reset"), { method: "POST" });
  await ensureOk(res);
}

export async function deleteHistoryRecord(roundId: string) {
  const res = await fetch(apiUrl(`/history/${encodeURIComponent(roundId)}`), {
    method: "DELETE",
  });
  await ensureOk(res);
}
