interface Props {
  pairCounts: Record<string, number>;
}

function parseKey(key: string): string[][] {
  return key.split("||").map((team) => team.split("|").filter(Boolean));
}

export const DuplicatePairs = ({ pairCounts }: Props) => {
  const duplicates = Object.entries(pairCounts)
    .filter(([, count]) => count >= 2)
    .sort(([, a], [, b]) => b - a);

  if (duplicates.length === 0) return null;

  return (
    <section>
      <h2>重複対戦ペア</h2>
      <ul>
        {duplicates.map(([key, count]) => {
          const teams = parseKey(key);
          return (
            <li key={key}>
              <strong>{count}回</strong>：{teams.map((t) => t.join("・")).join(" vs ")}
            </li>
          );
        })}
      </ul>
    </section>
  );
};
