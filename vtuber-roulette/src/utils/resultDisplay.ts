import { Organizer, RouletteResult, RouletteResultTeam } from "../types";

export function activeOrganizerNames(organizers: Organizer[]): string[] {
  return organizers.filter((o) => o.active).map((o) => o.name);
}

/**
 * 表示用のチーム分け。
 * 3人抽選を主催なしで引いた後に主催が設定された場合は、チームAの先頭に今の主催を加えて見せる。
 */
export function getDisplayTeams(
  result: RouletteResult | null,
  organizers: Organizer[],
): RouletteResultTeam[] {
  if (!result) {
    return [];
  }

  const [host] = activeOrganizerNames(organizers);

  if (result.kind === "standard_3" && host && result.teams[0] && result.teams[0].players.length === 1) {
    return [
      { ...result.teams[0], players: [host, result.teams[0].players[0]] },
      ...result.teams.slice(1),
    ];
  }

  return result.teams;
}
