
# ==========================================================
# decision.py
# Comparaison et recommandation des scénarios (mock)
# ==========================================================

import random


def evaluate_scenarios(scenarios):
    """
    Ajoute des indicateurs (rendement, bénéfice, risque)
    et retourne les scénarios évalués + le meilleur scénario
    """

    evaluated = []

    for sc in scenarios:

        # --- Rendement simulé (kg/ha) ---
        base_yield = random.uniform(800, 1800)

        if sc.get("fertilization", False):
            base_yield *= 1.2

        if sc.get("irrigation", False):
            base_yield *= 1.15

        yield_kg = round(base_yield, 1)

        # --- Prix et coûts (mock) ---
        price = 200  # FCFA/kg
        cost = 120000

        if sc.get("fertilization", False):
            cost += 30000

        if sc.get("irrigation", False):
            cost += 40000

        benefit = round(yield_kg * price - cost)

        # --- Risque climatique ---
        if sc.get("irrigation", False):
            risk = "Faible"
        elif sc.get("fertilization", False):
            risk = "Moyen"
        else:
            risk = "Élevé"

        sc_eval = sc.copy()
        sc_eval.update({
            "Rendement (kg/ha)": yield_kg,
            "Bénéfice net (FCFA/ha)": benefit,
            "Risque climatique": risk,
        })

        evaluated.append(sc_eval)

    # --- Classement ---
    best = max(evaluated, key=lambda x: x["Bénéfice net (FCFA/ha)"])

    return evaluated, best

