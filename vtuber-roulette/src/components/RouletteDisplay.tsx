import { Organizer, RouletteResult } from "../types";
import { getDisplayTeams } from "../utils/resultDisplay";

export const RouletteDisplay = ({
  result,
  organizers,
}: {
  result: RouletteResult | null;
  organizers: Organizer[];
}) => {
  if (!result) return <p>抽選結果はまだありません。</p>;

  const teams = getDisplayTeams(result, organizers);

  return (
    <div>
      <h2>抽選結果</h2>
      {teams.map((team) => (
        <p key={team.label}>
          {team.label}: {team.players.join(", ")}
        </p>
      ))}
    </div>
  );
};
