from product_profiles import product_profiles


def recommend_soap(skin, use, goal):
    scores = {}

    for product_slug, profile in product_profiles.items():
        score = 0

        if skin in profile["skin_types"]:
            score += 40

        if use in profile["use_types"]:
            score += 25

        if goal in profile["goals"]:
            score += 35

        scores[product_slug] = score

    if not scores:
        return "coconut-bliss", 0, ["overall_match"]

    slug = max(scores, key=scores.get)
    match_score = scores[slug]

    reasons = []

    selected_profile = product_profiles[slug]

    if skin in selected_profile["skin_types"]:
        reasons.append("skin_match")

    if use in selected_profile["use_types"]:
        reasons.append("use_match")

    if goal in selected_profile["goals"]:
        reasons.append("goal_match")

    if not reasons:
        reasons.append("overall_match")

    return slug, match_score, reasons
