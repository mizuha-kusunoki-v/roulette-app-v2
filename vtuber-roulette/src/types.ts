export type OrganizerMode = "single" | "double";

export type DrawMode =
  | "standard_3"
  | "standard_4"
  | "hosts_vs_duo"
  | "hosts_split_pairs";

export type RouletteResultTeam = {
  label: string;
  players: string[];
};

export type RouletteResult = {
  kind: DrawMode;
  teams: RouletteResultTeam[];
};

export type RouletteState = {
  participants: string[];
  organizer_mode: OrganizerMode;
  organizers: string[];
  selected_organizer_indices: number[];
  forced_players: string[];
  auto_forced_players: string[];
  excluded_players: string[];
  participation_counts: Record<string, number>;
  prev_players: string[];
  last_players: string[];
  spin_order: string[];
  miss_counts: Record<string, number>;
  last_selection_reasons: Record<string, string>;
  result: RouletteResult | null;
  round_id: string | null;
  phase: "idle" | "spinning" | "result";
  miss_threshold: number;
  enable_auto_force: boolean;
};

// =============================================================================
// 縛りルーレット (Restriction Roulette)
// =============================================================================

export type RestrictionItem = {
  id: string;
  name: string;
  description: string;
  enabled: boolean;
  weight: number;    // 出現重み 1〜5
  use_count: number;
};

export type RestrictionState = {
  items: RestrictionItem[];
  result: RestrictionItem | null;
  target: string;                 // 適用対象テキスト
  phase: "idle" | "spinning" | "result";
  round_id: string | null;
  history: string[];              // 選択済み item.id の履歴
  exclude_recent_count: number;   // 直近 N 回を抽選除外
  spin_order: string[];           // アニメーション用 item.name リスト
};
