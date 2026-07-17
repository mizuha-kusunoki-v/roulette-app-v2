import { DrawMode, OrganizerMode, RouletteState } from "../types";

const BASE_URL = "http://localhost:8000";

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

export async function fetchState(): Promise<RouletteState> {
  const res = await fetch(`${BASE_URL}/state`);
  await ensureOk(res);
  return res.json();
}

export async function updateParticipants(participants: string[]) {
  const res = await fetch(`${BASE_URL}/participants`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ participants }),
  });
  await ensureOk(res);
}

export async function updateOrganizerConfig(
  organizerMode: OrganizerMode,
  organizers: string[],
  selectedOrganizerIndices: number[],
) {
  const res = await fetch(`${BASE_URL}/organizer_config`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      organizer_mode: organizerMode,
      organizers,
      selected_organizer_indices: selectedOrganizerIndices,
    }),
  });
  await ensureOk(res);
}

export async function updateForcedPlayers(forcedPlayers: string[]) {
  const res = await fetch(`${BASE_URL}/forced_players`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ forced_players: forcedPlayers }),
  });
  await ensureOk(res);
}

export async function updateExcludedPlayers(excludedPlayers: string[]) {
  const res = await fetch(`${BASE_URL}/excluded_players`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ excluded_players: excludedPlayers }),
  });
  await ensureOk(res);
}

export async function draw(mode: DrawMode) {
  const res = await fetch(`${BASE_URL}/draw`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode }),
  });
  await ensureOk(res);

  const data = await res.json();
  return data.result;
}

export async function updateDrawSettings(missThreshold: number, enableAutoForce: boolean) {
  const res = await fetch(`${BASE_URL}/draw_settings`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ miss_threshold: missThreshold, enable_auto_force: enableAutoForce }),
  });
  await ensureOk(res);
}

export async function notifyPresentationComplete(roundId: string) {
  const res = await fetch(`${BASE_URL}/presentation_complete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ round_id: roundId }),
  });
  await ensureOk(res);
}

export async function resetState() {
  const res = await fetch(`${BASE_URL}/reset`, {
    method: "POST",
  });
  await ensureOk(res);
}
