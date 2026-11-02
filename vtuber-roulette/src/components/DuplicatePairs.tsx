interface Props {
  pairCounts: Record<string, number>;
}

export const DuplicatePairs = ({ pairCounts }: Props) => {
  const duplicates = Object.entries(pairCounts)
    .filter(([, count]) => count >= 2)
    .sort(([, a], [, b]) => b - a);

  if (duplicates.length === 0) return null;

  return (
    <section>
      <h2>重複チーム組み合わせ</h2>
      <ul>
        {duplicates.map(([key, count]) => {
          const players = key.split("|");
          return (
            <li key={key}>
              <strong>{count}回</strong>：{players.join("・")}
            </li>
          );
        })}
      </ul>
    </section>
  );
};
