"""
Draw policy settings.

Adjust these values to tune the weighted draw and the auto-force display.
Whether auto-force is on is a per-session setting (the admin screen), not set here.
"""

# A player is shown as an auto-force target (and gets the "median_gap" reason when drawn) when:
# participation_count <= median_participation - AUTO_FORCE_MEDIAN_GAP
#
# Initial value = 2 to treat only clear under-participation as "significant".
AUTO_FORCE_MEDIAN_GAP = 2

# Limit the players shown as auto-force targets. 0 means no limit.
AUTO_FORCE_MAX_PER_DRAW = 2


# Weighted draw. Hard rules, in order: manual force and exclusion; players from the last round play only
# when the others cannot fill the slots; one of the players who have missed the most consecutive draws
# (chosen uniformly among them). The remaining slots are drawn by weight.
# A lineup's chance is proportional to
#   prod(exp(score of each drawn player)) * exp(-PAIR_PENALTY * times the matchup was drawn before)
# score = WAIT_WEIGHT * consecutive misses
#       + DEFICIT_WEIGHT * (participation median - own participation, if positive; only with auto-force on)
# 0 turns a term off; larger values make the draw fairer but more predictable.
WAIT_WEIGHT = 3.0
DEFICIT_WEIGHT = 1.0
PAIR_PENALTY = 1.0
