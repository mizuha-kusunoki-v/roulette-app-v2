import { RouletteResult, RouletteResultTeam } from "../types";

export function getActiveOrganizers(
  organizerMode: "single" | "double",
  organizers: string[],
  selectedOrganizerIndices: number[] = [0],
): string[] {
  const limit = organizerMode === "double" ? 2 : 1;
  return selectedOrganizerIndices
    .filter((i) => i >= 0 && i < organizers.length)
    .slice(0, limit)
    .map((i) => organizers[i]);
}

export function getDisplayTeams(
  result: RouletteResult | null,
  organizers: string[] = [],
  organizerMode: "single" | "double" = "single",
  selectedOrganizerIndices: number[] = [0],
): RouletteResultTeam[] {
  if (!result) {
    return [];
  }

  const activeOrganizers = getActiveOrganizers(
    organizerMode,
    organizers,
    selectedOrganizerIndices,
  );

  if (
    result.kind === "standard_3" &&
    activeOrganizers[0] &&
    result.teams[0] &&
    result.teams[0].players.length === 1
  ) {
    return [
      {
        ...result.teams[0],
        players: [activeOrganizers[0], result.teams[0].players[0]],
      },
      ...result.teams.slice(1),
    ];
  }

  return result.teams;
}
