"""Business logic for equity and financial calculations."""
from src.session_manager import (
    session_get_revenus, session_get_depenses, session_get_depenses_with_payeur,
    session_get_travail_domestique
)

def calculer_part():
    """Calculate expected contribution based on income ratio."""
    revenus = session_get_revenus()
    depenses = session_get_depenses()

    rh = revenus.get("homme", 0)
    rf = revenus.get("femme", 0)
    total_revenu = rh + rf
    total_depenses = sum(depenses.values())

    if total_revenu == 0:
        return 0, 0, total_depenses

    return (
        total_depenses * rh / total_revenu,
        total_depenses * rf / total_revenu,
        total_depenses
    )

def calculer_equite():
    """Calculate equity score: compares financial charge vs domestic work."""
    revenus = session_get_revenus()
    travail_user = session_get_travail_domestique()
    depenses_with_payeur = session_get_depenses_with_payeur()
    
    # Check for sufficient data
    total_revenu = sum(revenus.values()) if revenus else 0
    total_heures = sum(
        sum(data.get(role, 0) for role in ["homme", "femme"]) 
        for data in travail_user.values()
    ) if travail_user else 0
    
    if total_revenu == 0 or total_heures == 0:
        return {
            "non_calculé": True,
            "score_equite": None,
            "interpretation": "Veuillez remplir les revenus, les dépenses et le travail domestique"
        }
    
    rh = revenus.get("homme", 0)
    rf = revenus.get("femme", 0)
    
    # Revenue ratios
    ratio_revenu_h = rh / total_revenu if total_revenu > 0 else 0.5
    ratio_revenu_f = rf / total_revenu if total_revenu > 0 else 0.5
    
    # Domestic work hours (weekly)
    heures_h = sum(data.get("homme", 0) for data in travail_user.values()) if travail_user else 0
    heures_f = sum(data.get("femme", 0) for data in travail_user.values()) if travail_user else 0
    
    # Domestic work ratios
    total_h = heures_h + heures_f
    ratio_travail_h = heures_h / total_h if total_h > 0 else 0.5
    ratio_travail_f = heures_f / total_h if total_h > 0 else 0.5
    
    # Expense ratios
    depense_h = 0
    depense_f = 0
    depense_shared = 0
    
    for cat, montant, payeur in depenses_with_payeur:
        if payeur == "homme":
            depense_h += montant
        elif payeur == "femme":
            depense_f += montant
        else:
            depense_shared += montant / 2
    
    depense_h += depense_shared
    depense_f += depense_shared
    total_dep = depense_h + depense_f
    
    ratio_depense_h = depense_h / total_dep if total_dep > 0 else 0.5
    ratio_depense_f = depense_f / total_dep if total_dep > 0 else 0.5
    
    # Financial charge = average of income + expense ratios
    charge_h = (ratio_revenu_h + ratio_depense_h) / 2
    charge_f = (ratio_revenu_f + ratio_depense_f) / 2
    
    # Equity score: how closely charge matches domestic work
    diff_h = abs(charge_h - ratio_travail_h)
    diff_f = abs(charge_f - ratio_travail_f)
    iniquite = (diff_h + diff_f) / 2
    score_equite = max(0, 100 - (iniquite * 100))
    
    return {
        "non_calculé": False,
        "score_equite": score_equite,
        "ratio_revenu": {"homme": ratio_revenu_h, "femme": ratio_revenu_f},
        "ratio_depense": {"homme": ratio_depense_h, "femme": ratio_depense_f},
        "ratio_travail": {"homme": ratio_travail_h, "femme": ratio_travail_f},
        "heures": {"homme": heures_h, "femme": heures_f},
        "depense": {"homme": depense_h, "femme": depense_f},
        "interpretation": get_interpretation_equite(
            score_equite, charge_h, charge_f, ratio_travail_h, ratio_travail_f
        )
    }

def get_interpretation_equite(score, charge_h, charge_f, travail_h, travail_f):
    """Get interpretation text for equity score."""
    if score >= 85:
        return "✅ Très équitable"
    elif score >= 70:
        return "⚠️ Relativement équitable"
    elif score >= 50:
        diff_h = charge_h - travail_h
        if diff_h < -0.05:
            return "⚠️ Inéquité modérée - L'homme supporte plus de travail domestique"
        elif diff_h > 0.05:
            return "⚠️ Inéquité modérée - La femme supporte plus de travail domestique"
        else:
            return "⚠️ Inéquité modérée"
    else:
        diff_h = charge_h - travail_h
        if diff_h < -0.05:
            return "❌ Forte inéquité - L'homme supporte disproportionnément le travail domestique"
        elif diff_h > 0.05:
            return "❌ Forte inéquité - La femme supporte disproportionnément le travail domestique"
        else:
            return "❌ Forte inéquité"
