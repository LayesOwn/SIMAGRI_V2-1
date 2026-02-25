# ==========================================================
# domain/socio_eco.py
# Module socio-économique – SIMAGRI v2
# ==========================================================

# ----------------------------------------------------------
# 1️⃣ COÛTS UNITAIRES (FCFA / ha)
# ----------------------------------------------------------

SOIL_PREPARATION = {
    "Labour": 30000,
    "Offsetage": 15000,
    "Billonnage": 20000,
}

LABOR = {
    "Semis": 12000,
    "Sarclage": 15000,
    "Récolte": 20000,
    "Autres": 20000,
}

POST_HARVEST = {
    "Battage": 40000,
    "Égrenage": 7000,
    "Séchage": 5000,
    "Autres": 5000,
}

# ----------------------------------------------------------
# 2️⃣ AUTRES DONNÉES (INCHANGÉES MAIS UTILES)
# ----------------------------------------------------------

SEEDS = {
    "Semence locale": {"price": 300, "qty": 20},
    "Semence améliorée": {"price": 600, "qty": 15},
    "Semence certifiée": {"price": 600, "qty": 15},
}

INPUTS = {
    "NPK": {"price": 400, "qty": 50},
    "Urée": {"price": 350, "qty": 40},
    "Compost": {"price": 50, "qty": 1000},
}

OTHER_COSTS = {
    "Transport": 5000,
    "Divers": 3000,
}

# Prix de vente par defaut (FCFA/kg) par culture
CROP_PRICES = {
    "ML": 175,   # Mil
    "SG": 150,   # Sorgho
    "PN": 350,   # Arachide
    "RI": 250,   # Riz
}

# ----------------------------------------------------------
# 3️⃣ FONCTIONS DE CALCUL
# ----------------------------------------------------------

def compute_cost_per_ha(operations, unit_costs, area_ha):
    """
    Coût = somme(prix_unitaire × surface_ha)
    """
    if not operations or area_ha is None:
        return 0

    return sum(
        unit_costs.get(op, 0) * area_ha
        for op in operations
    )

# Préparation du sol
def compute_soil_preparation_cost(operations, area_ha):
    return compute_cost_per_ha(operations, SOIL_PREPARATION, area_ha)

# Main d'œuvre
def compute_labor_cost(operations, area_ha):
    return compute_cost_per_ha(operations, LABOR, area_ha)

# Post-récolte
def compute_post_harvest_cost(operations, area_ha):
    return compute_cost_per_ha(operations, POST_HARVEST, area_ha)

# Coûts fixes non dépendants de la surface
def compute_other_costs(selected_items):
    """
    Coûts fixes non dépendants de la surface
    """
    if not selected_items:
        return 0

    return sum(
        OTHER_COSTS.get(item, 0)
        for item in selected_items
    )

# COut total de production agricole
def compute_total_socio_cost(
    soil_ops,
    labor_ops,
    post_ops,
    seed_cost,
    area_ha,
):
    """
    Coût socio-économique total (hors fertilisation et irrigation)
    """
    return (
        compute_soil_preparation_cost(soil_ops, area_ha)
        + compute_labor_cost(labor_ops, area_ha)
        + compute_post_harvest_cost(post_ops, area_ha)
        + (seed_cost or 0)
    ) 
# Coût des semences       
def compute_seed_cost(qty, price, area_ha):
    """
    Coût des semences = quantité × prix unitaire × superficie
    """
    if qty is None or price is None or area_ha is None:
        return 0
    return qty * price * area_ha

