// バックエンドとのプロトコルの型。手で書かず、OpenAPI から生成した schema.ts に名前を付けるだけにする。
// 型を変えたいときは、バックエンドのモデルを変えて `npm run gen:api` で生成し直す。
import type { components } from "./api/schema";

type Schemas = components["schemas"];

export type SessionState = Schemas["SessionState"];
export type ParticipantStatus = Schemas["ParticipantStatus"];
export type Organizer = Schemas["Organizer"];
export type DrawOption = Schemas["DrawOption"];
export type DrawRecord = Schemas["DrawRecord"];
export type RouletteResult = Schemas["RouletteResult"];
export type RouletteResultTeam = Schemas["ResultTeam"];
export type SelectionGroup = Schemas["SelectionGroup"];
export type SelectionReason = SelectionGroup["reason"];
export type DrawMode = Schemas["DrawRequest"]["mode"];
export type OrganizerMode = SessionState["organizer_mode"];
export type ForcedTeam = NonNullable<ParticipantStatus["forced"]>;
