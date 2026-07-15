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
        return "coconut-bliss", 0, [
            "We could not calculate a recommendation from the answers provided."
        ]

    slug = max(scores, key=scores.get)
    match_score = scores[slug]

    reasons = []
    selected_profile = product_profiles[slug]

    if skin in selected_profile["skin_types"]:
        reasons.append(
            f"This soap matches your selected skin type: "
            f"{skin.replace('_', ' ').title()}."
        )

    if use in selected_profile["use_types"]:
        reasons.append(
            f"This soap is suitable for your intended use: "
            f"{use.replace('_', ' ').title()}."
        )

    if goal in selected_profile["goals"]:
        reasons.append(
            f"This soap supports your selected preference: "
            f"{goal.replace('_', ' ').title()}."
        )

    if not reasons:
        reasons.append(
            "This product received the highest overall score "
            "based on the answers you provided."
        )

    return slug, match_score, reasons
