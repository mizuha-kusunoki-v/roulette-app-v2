"""
Draw policy settings.

Adjust these values to tune auto-force behavior.
"""

# ── 主催初期値 ─────────────────────────────────────────────────────────────────
# サーバー起動時およびリセット時に自動で設定される主催名。
# 空文字列の場合は設定しない。
INITIAL_ORGANIZER: str = ""

# ── 自動強制抽選 ───────────────────────────────────────────────────────────────
# If enabled, players far below the participation median are force-selected.
ENABLE_AUTO_FORCE_BY_MEDIAN_GAP = True

# A player becomes auto-force target when:
# participation_count <= median_participation - AUTO_FORCE_MEDIAN_GAP
#
# Initial value = 2 to treat only clear under-participation as "significant".
AUTO_FORCE_MEDIAN_GAP = 2

# Limit auto-forced players per draw. 0 means no limit.
AUTO_FORCE_MAX_PER_DRAW = 2

