# ==========================================================
# ui/callbacks.py
# Callbacks Dash – SIMAGRI v2
# ==========================================================

try:
    from dash import html, dcc, ctx
except Exception:
    import dash_html_components as html
    import dash_core_components as dcc
    from dash import callback_context as ctx
from dash.dependencies import Input, Output, State, ALL
import dash_bootstrap_components as dbc
import json
import csv
from pathlib import Path
import re
from datetime import datetime, timedelta
import unicodedata
import plotly.graph_objects as go
import copy

# --- Imports domaine métier
from domain.geography import get_department_gps, get_department_soil, get_department_options
from domain.climate.enacts import load_enacts, compute_probabilistic_onset
from domain.climate.weather import ensure_weather_for_scenario
from domain.irrigation import get_irrigation_schedule, compute_irrigation_cost
from domain.fertilisation import (
    compute_fertilization_cost,
    compute_npk_from_fertilizer,
)
from domain.socio_eco import (
    SEEDS,
    compute_seed_cost,
    compute_soil_preparation_cost,
    compute_labor_cost,
    compute_post_harvest_cost,
    compute_total_socio_cost,
)
from domain.scenario import build_scenario_from_ui, DSSAT_COLUMNS
from domain.decision import evaluate_scenarios
from domain.dssat.write_xfile import write_x_file
from domain.dssat.write_snx import write_snx_file
from domain.dssat.run_dssat import run_dssat_simulation
from domain.dssat.validate_inputs import validate_dssat_inputs
from domain.dssat.validate_inputs import _find_wth_file, _parse_wth_dates, _parse_planting_date
import os
from pathlib import Path

# ==========================================================
# CONFIGURATION DES CHEMINS
# ==========================================================
# Depuis ui/callbacks.py (ui/ -> SIMAGRI_V3/), on remonte 2 niveaux


# Déterminer BASE_DIR selon l'environnement
if os.getenv('SIMAGRI_ENV') == 'docker':
    # En Docker, on est déjà dans /app
    BASE_DIR = Path('/app')
else:
    # En local (Windows)
    _temp = Path(__file__).resolve().parents[2]
    
    # Assurer que BASE_DIR pointe à SIMAGRI_V3
    if _temp.name == "SIMAGRI_V3":
        BASE_DIR = _temp
    elif _temp.name == "simagri":
        # On a remonté trop haut, aller dans SIMAGRI_V3
        BASE_DIR = _temp / "SIMAGRI_V3"
    else:
        # Default
        BASE_DIR = _temp

print(f"✅ BASE_DIR = {BASE_DIR}")
print(f"   Existe ? {BASE_DIR.exists()}")
print(f"   dssat/ existe ? {(BASE_DIR / 'dssat').exists()}")
print(f"   Fichiers .WTH : {len(list((BASE_DIR / 'dssat').glob('*.WTH')))}")
# IMPORTANT:
# Ne pas générer tous les WTH au démarrage: cela peut bloquer le boot de Dash.
# Les fichiers météo sont générés à la demande par scénario (ensure_weather_for_scenario).
try:
    invalid_depts = []
    report_rows = []
    for opt in get_department_options():
        dept = opt.get("value")
        try:
            _df = load_enacts(dept)
            if _df is None or _df.empty:
                invalid_depts.append(dept)
                report_rows.append({
                    "departement": dept,
                    "statut_enacts": "INVALIDE",
                    "date_min": "",
                    "date_max": "",
                    "nb_lignes_valides": 0,
                })
            else:
                report_rows.append({
                    "departement": dept,
                    "statut_enacts": "OK",
                    "date_min": str(_df["date"].min().date()),
                    "date_max": str(_df["date"].max().date()),
                    "nb_lignes_valides": int(len(_df)),
                })
        except Exception:
            invalid_depts.append(dept)
            report_rows.append({
                "departement": dept,
                "statut_enacts": "INVALIDE",
                "date_min": "",
                "date_max": "",
                "nb_lignes_valides": 0,
            })

    report_path = BASE_DIR / "data" / "enacts_validation_report.csv"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "departement",
                "statut_enacts",
                "date_min",
                "date_max",
                "nb_lignes_valides",
            ],
        )
        w.writeheader()
        w.writerows(report_rows)
    print(f"   📄 Rapport ENACTS: {report_path}")

    if invalid_depts:
        print(f"   ⚠️ Départements sans données ENACTS valides ({len(invalid_depts)}): {', '.join(invalid_depts)}")
except Exception as e:
    print(f"   ⚠️ Audit ENACTS impossible: {e}")

GEOJSON_PATH = BASE_DIR / "data" / "geojson" / "senegal_departments.json"


def _norm_name(value):
    s = unicodedata.normalize("NFD", str(value or ""))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


# ==========================================================
# 🔧 Fonction utilitaire (TABLE)
# ==========================================================
def scenario_to_table_row(s):
    """
    Convertit un scenario complet en une ligne pour la table d'affichage.
    """
    economy = s.get("economy", {})
    fert_cost = economy.get("NFertCost", 0) or 0
    irrig_cost = economy.get("IrrigCost", 0) or 0
    production_cost = economy.get("FixedCosts", 0) or 0
    total_cost = fert_cost + irrig_cost + production_cost

    def _amt(v):
        try:
            return str(int(round(float(v or 0))))
        except Exception:
            return "0"

    return {
        "ID": s["id_scenario"],
        "Departement": s["location"]["department"],
        "Culture": s["crop"]["code"],
        "Cycle": s["crop"]["cycle"],
        "Semis": s["crop"]["planting_date"],
        "Fertilisation": "Oui" if s["fertilization"].get("enabled") else "Non",
        "Irrigation": "Oui" if s["irrigation"].get("enabled") else "Non",
        "Cout fertilisation (FCFA)": _amt(fert_cost),
        "Cout irrigation (FCFA)": _amt(irrig_cost),
        "Cout production (FCFA)": _amt(production_cost),
        "Cout total (FCFA)": _amt(total_cost),
    }


def get_triggered_id():
    """
    Compat Dash v1/v2 pour récupérer l'id qui a déclenché le callback.
    """
    try:
        return ctx.triggered_id
    except Exception:
        triggered = getattr(ctx, "triggered", None) or []
        if not triggered:
            return None
        prop_id = triggered[0].get("prop_id", "")
        return prop_id.split(".")[0] if prop_id else None


def _parse_max_scenarios(simulation_mode):
    """
    Accepte:
    - int/str numerique -> borne [1, 3]
    - "single" (legacy) -> 1
    """
    if simulation_mode in (None, "", "single"):
        return 1
    try:
        n = int(simulation_mode)
    except Exception:
        return 1
    return max(1, min(n, 3))


def parse_summary_metrics(summary_path):
    """
    Parse les indicateurs clés DSSAT depuis Summary.OUT.
    """
    if not summary_path.exists():
        return {}

    try:
        lines = summary_path.read_text(encoding="latin-1", errors="ignore").splitlines()
    except Exception:
        return {}

    header_tokens = None
    data_tokens = None
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if s.startswith("@"):
            header_tokens = s.split()
            if header_tokens and header_tokens[0] == "@":
                header_tokens = header_tokens[1:]
            continue
        if header_tokens and re.match(r"^\s*\d+\s+", line):
            cand = s.split()
            if len(cand) >= 10:
                data_tokens = cand

    if not header_tokens or not data_tokens:
        return {}

    row = {}
    for i, h in enumerate(header_tokens):
        if i < len(data_tokens):
            row[h] = data_tokens[i]

    # Prefer Summary.OUT keys, fallback to Evaluate.OUT when needed.
    evaluate_row = {}
    eval_path = Path(summary_path).with_name("Evaluate.OUT")
    if eval_path.exists():
        try:
            ev_lines = eval_path.read_text(encoding="latin-1", errors="ignore").splitlines()
            ev_header = None
            ev_data = None
            for ln in ev_lines:
                ss = ln.strip()
                if not ss:
                    continue
                if ss.startswith("@"):
                    ev_header = ss.split()
                    if ev_header and ev_header[0] == "@":
                        ev_header = ev_header[1:]
                    continue
                if ev_header and re.match(r"^\s*\d+\s+", ln):
                    cand = ss.split()
                    if len(cand) >= 10:
                        ev_data = cand
            if ev_header and ev_data:
                for i, h in enumerate(ev_header):
                    if i < len(ev_data):
                        evaluate_row[h] = ev_data[i]
        except Exception:
            pass

    def pick(*keys, default="-"):
        for k in keys:
            if k in row and row[k] not in {"", "-99"}:
                return row[k]
            if k in evaluate_row and evaluate_row[k] not in {"", "-99"}:
                return evaluate_row[k]
        return default

    return {
        "FLO": pick("ADAPS", "FLO"),
        "MAT": pick("MDAPS", "MAT"),
        "TOPWT": pick("CWAM", "CWAMS", "TOPWT"),
        "HARWT": pick("HWAM", "HWAMS", "HARWT"),
        "RAIN": pick("PRCM", "RAIN"),
        "TIRR": pick("IRCM", "TIRR"),
        "CET": pick("ETCM", "CET"),
    }


def format_metrics_short(metrics):
    if not metrics:
        return ""
    return (
        f"HARWT={metrics.get('HARWT', '-')}, "
        f"TOPWT={metrics.get('TOPWT', '-')}, "
        f"RAIN={metrics.get('RAIN', '-')}, "
        f"TIRR={metrics.get('TIRR', '-')}, "
        f"CET={metrics.get('CET', '-')}, "
        f"MAT={metrics.get('MAT', '-')}"
    )


def classify_dssat_status(metrics):
    """
    Retourne un statut simple:
    - SUCCES: rendement grain > 0
    - SUCCES_TECHNIQUE: simulation valide mais HARWT == 0 avec biomasse presente
    - VIDE: sorties manquantes/inexploitables
    - ERREUR: execution invalide
    """
    if not metrics:
        return "ERREUR"
    harwt = str(metrics.get("HARWT", "")).strip()
    topwt = str(metrics.get("TOPWT", "")).strip()
    if harwt in {"-99", ""} and topwt in {"-99", ""}:
        return "VIDE"
    try:
        h = float(harwt)
    except Exception:
        h = None
    try:
        t = float(topwt)
    except Exception:
        t = None
    if h is not None and h > 0:
        return "SUCCES"
    if (h is not None and h == 0) and (t is not None and t >= 0):
        return "SUCCES_TECHNIQUE"
    return "VIDE"


def _planting_date_for_year(base_date, year):
    dt = _parse_planting_date(base_date)
    if not dt:
        return None
    month, day = dt.month, dt.day
    while day >= 1:
        try:
            return datetime(year, month, day).date().isoformat()
        except Exception:
            day -= 1
    return datetime(year, month, 1).date().isoformat()


def _aggregate_history(history):
    if not history:
        return {"status": "ERREUR"}

    def _vals(key):
        vals = []
        for r in history:
            v = _num(r.get(key))
            if v is not None:
                vals.append(v)
        return vals

    agg = {"history": history, "years_ok": len(history)}
    for k in ["HARWT", "TOPWT", "RAIN", "TIRR", "CET", "MAT"]:
        vals = _vals(k)
        agg[k] = f"{sum(vals)/len(vals):.1f}" if vals else "-"

    # status by historical outcomes
    if any((_num(r.get("HARWT")) or 0.0) > 0 for r in history):
        agg["status"] = "SUCCES"
    elif any((_num(r.get("HARWT")) == 0.0) and (_num(r.get("TOPWT")) is not None) for r in history):
        agg["status"] = "SUCCES_TECHNIQUE"
    elif any(_num(r.get("TOPWT")) is not None for r in history):
        agg["status"] = "VIDE"
    else:
        agg["status"] = "ERREUR"
    return agg


def build_table(scenarios, sim_results):
    table_data = []
    for s in scenarios:
        row = scenario_to_table_row(s)
        sid = s.get("id_scenario")
        m = (sim_results or {}).get(sid, {})
        row["DSSAT:Status"] = m.get("status", "-")
        row["DSSAT:HARWT"] = m.get("HARWT", "-")
        row["DSSAT:TOPWT"] = m.get("TOPWT", "-")
        row["DSSAT:RAIN"] = m.get("RAIN", "-")
        row["DSSAT:TIRR"] = m.get("TIRR", "-")
        row["DSSAT:CET"] = m.get("CET", "-")
        row["DSSAT:MAT"] = m.get("MAT", "-")
        row["DSSAT:AnneesOK"] = m.get("years_ok", "-")
        table_data.append(row)

    col_order = [
        "ID", "Departement", "Culture", "Cycle", "Semis",
        "Fertilisation", "Irrigation",
        "Cout fertilisation (FCFA)", "Cout irrigation (FCFA)",
        "Cout production (FCFA)", "Cout total (FCFA)",
        "DSSAT:Status", "DSSAT:HARWT", "DSSAT:TOPWT",
        "DSSAT:RAIN", "DSSAT:TIRR", "DSSAT:CET", "DSSAT:MAT", "DSSAT:AnneesOK",
    ]
    columns = [{"name": c, "id": c} for c in col_order] if table_data else []
    return table_data, columns


def _num(v):
    try:
        x = float(v)
        if x == -99:
            return None
        return x
    except Exception:
        return None


def _advice_for_row(status, harwt, rain, tirr, cet):
    if status == "SUCCES_TECHNIQUE":
        return "Simulation valide mais rendement grain nul: ajuster semis, cultivar et fertilisation."
    if status != "SUCCES":
        return "Verifier format/qualite des donnees (meteo, sol, cultivar, semis)."
    if harwt is None or harwt <= 0:
        if rain is not None and rain < 150:
            return "Stress hydrique probable: avancer semis utile ou activer irrigation/fertilisation."
        return "Rendement nul: verifier variet?, date de semis et fertilisation de base."
    if rain is not None and cet is not None and rain + (tirr or 0) < 0.7 * cet:
        return "Bilan eau limite: ajuster semis ou ajouter irrigation ciblee."
    if harwt < 500:
        return "Rendement faible: augmenter fertilisation NPK et optimiser date de semis."
    return "Scenario correct: stabiliser les couts et reproduire les pratiques." 


def build_simulation_output(scenarios, sim_results, messages):
    rows = []
    labels = []
    harwt_vals = []
    topwt_vals = []
    rain_vals = []
    tirr_vals = []
    cet_vals = []
    mat_vals = []
    cost_vals = []
    revenue_vals = []
    margin_vals = []
    advices = []
    metric_lines = []
    histories = []

    for idx, s in enumerate(scenarios, start=1):
        sid = s.get("id_scenario")
        m = (sim_results or {}).get(sid, {})
        status = m.get("status", "ERREUR")
        color = "success" if status == "SUCCES" else ("warning" if status in {"VIDE", "SUCCES_TECHNIQUE"} else "danger")

        harwt = _num(m.get("HARWT"))
        topwt = _num(m.get("TOPWT"))
        rain = _num(m.get("RAIN"))
        tirr = _num(m.get("TIRR"))
        cet = _num(m.get("CET"))
        mat = _num(m.get("MAT"))

        eco = s.get("economy", {})
        total_cost = float((eco.get("NFertCost", 0) or 0) + (eco.get("IrrigCost", 0) or 0) + (eco.get("FixedCosts", 0) or 0))
        crop_price = float(eco.get("CropPrice", 0) or 0)
        revenue = (harwt or 0.0) * crop_price
        margin = revenue - total_cost

        rows.append(
            html.Tr([
                html.Td(f"Scenario {idx}"),
                html.Td(sid or "-"),
                html.Td(dbc.Badge(status, color=color, className="me-1")),
                html.Td(m.get("HARWT", "-")),
                html.Td(m.get("TOPWT", "-")),
                html.Td(m.get("RAIN", "-")),
                html.Td(m.get("TIRR", "-")),
                html.Td(m.get("CET", "-")),
                html.Td(m.get("MAT", "-")),
            ])
        )

        labels.append(sid or f"S{idx:03d}")
        harwt_vals.append(harwt or 0)
        topwt_vals.append(topwt or 0)
        rain_vals.append(rain or 0)
        tirr_vals.append(tirr or 0)
        cet_vals.append(cet or 0)
        mat_vals.append(mat or 0)
        cost_vals.append(total_cost)
        revenue_vals.append(revenue)
        margin_vals.append(margin)
        advices.append((sid or f"Scenario {idx}", _advice_for_row(status, harwt, rain, tirr, cet)))
        metric_lines.append(
            f"{sid or f'Scenario {idx}'}: "
            f"HARWT={m.get('HARWT','-')} kg/ha (rendement grain), "
            f"TOPWT={m.get('TOPWT','-')} kg/ha (biomasse), "
            f"RAIN={m.get('RAIN','-')} mm (pluie), "
            f"TIRR={m.get('TIRR','-')} mm (irrigation), "
            f"CET={m.get('CET','-')} mm (evapotranspiration), "
            f"MAT={m.get('MAT','-')} j (maturite)."
        )
        h = m.get("history") or []
        if h:
            histories.append((sid or f"S{idx:03d}", h))

    n_success = sum(1 for v in (sim_results or {}).values() if v.get("status") == "SUCCES")
    n_tech = sum(1 for v in (sim_results or {}).values() if v.get("status") == "SUCCES_TECHNIQUE")
    n_empty = sum(1 for v in (sim_results or {}).values() if v.get("status") == "VIDE")
    n_error = max(0, len(scenarios) - n_success - n_tech - n_empty)

    fig_agro = go.Figure()
    fig_agro.add_bar(name="HARWT", x=labels, y=harwt_vals)
    fig_agro.add_bar(name="TOPWT", x=labels, y=topwt_vals)
    fig_agro.update_layout(barmode="group", title="Performance agronomique (kg/ha)", yaxis_title="kg/ha", margin=dict(l=20, r=20, t=50, b=20))

    fig_water = go.Figure()
    fig_water.add_bar(name="RAIN", x=labels, y=rain_vals)
    fig_water.add_bar(name="TIRR", x=labels, y=tirr_vals)
    fig_water.add_bar(name="CET", x=labels, y=cet_vals)
    fig_water.update_layout(barmode="group", title="Bilan hydrique (mm)", yaxis_title="mm", margin=dict(l=20, r=20, t=50, b=20))

    fig_econ = go.Figure()
    fig_econ.add_bar(name="Cout total", x=labels, y=cost_vals)
    fig_econ.add_bar(name="Revenu brut", x=labels, y=revenue_vals)
    fig_econ.add_bar(name="Marge", x=labels, y=margin_vals)
    fig_econ.update_layout(
        barmode="group",
        title="Lecture economique (FCFA/ha)",
        yaxis_title="FCFA/ha",
        yaxis_tickformat=".0f",
        margin=dict(l=20, r=20, t=50, b=20),
    )

    fig_hist = go.Figure()
    for sid, h in histories:
        xs = [r.get("year") for r in h]
        ys = [(_num(r.get("HARWT")) or 0) for r in h]
        fig_hist.add_scatter(x=xs, y=ys, mode="lines+markers", name=sid)
    fig_hist.update_layout(
        title="Analyse historique: rendement HARWT par annee",
        xaxis_title="Annee",
        yaxis_title="HARWT (kg/ha)",
        margin=dict(l=20, r=20, t=50, b=20),
    )

    return html.Div([
        html.H5("Resultat des simulations DSSAT", className="mb-3"),
        html.Ul([html.Li(m, className="mb-1") for m in messages]),
        dbc.Table(
            [
                html.Thead(html.Tr([
                    html.Th("Scenario"),
                    html.Th("ID"),
                    html.Th("Status"),
                    html.Th("HARWT (kg/ha)"),
                    html.Th("TOPWT (kg/ha)"),
                    html.Th("RAIN (mm)"),
                    html.Th("TIRR (mm)"),
                    html.Th("CET (mm)"),
                    html.Th("MAT (jours)"),
                ])),
                html.Tbody(rows),
            ],
            bordered=True,
            striped=True,
            hover=True,
            size="sm",
            className="mt-3",
        ),
        dbc.Alert(
            "Definitions: HARWT=rendement grain sec, TOPWT=biomasse aerienne seche, "
            "RAIN=pluie cumulee de la campagne, TIRR=irrigation cumulee, "
            "CET=evapotranspiration cumulée, MAT=jours jusqu'a maturite. "
            "Une valeur 0 peut etre un resultat DSSAT valide (ex: pas de rendement ou pas d'irrigation).",
            color="info",
            className="mt-2",
        ),
        dbc.Alert(
            html.Ul([html.Li(x) for x in metric_lines]),
            color="secondary",
            className="mt-2",
        ),
        html.P(f"Total: {len(scenarios)} | Succes: {n_success} | Succes technique: {n_tech} | Vides: {n_empty} | Erreurs: {n_error}"),
        dbc.Row([
            dbc.Col(dcc.Graph(figure=fig_agro), md=6),
            dbc.Col(dcc.Graph(figure=fig_water), md=6),
        ]),
        dbc.Row([
            dbc.Col(dcc.Graph(figure=fig_econ), md=12),
        ]),
        dbc.Row([
            dbc.Col(dcc.Graph(figure=fig_hist), md=12),
        ]),
        dbc.Card([
            dbc.CardHeader("Conseils automatiques"),
            dbc.CardBody(html.Ul([html.Li(f"{sid}: {txt}") for sid, txt in advices]))
        ], className="mt-2")
    ])


SIM_CYCLE_DAYS = 210


def _feasible_bounds_from_dates(dmin, dmax):
    """
    Borne semis avec marge DSSAT:
    - J-1 doit exister
    - +SIM_CYCLE_DAYS doit exister
    """
    min_ok = dmin + timedelta(days=1)
    max_ok = dmax - timedelta(days=SIM_CYCLE_DAYS)
    if max_ok < min_ok:
        return dmin, dmax
    return min_ok, max_ok


def align_planting_date_to_wth_year(scenario, base_dir):
    """
    Aligne l'année de semis sur l'année couverte par le fichier WTH (si nécessaire).
    Retourne un message d'ajustement ou None.
    """
    try:
        station = scenario.get("location", {}).get("station_code")
        if not station:
            return None
        dssat_dir = Path(base_dir) / "dssat"
        wth_path = _find_wth_file(dssat_dir, station)
        if not wth_path:
            return None
        dates, _ = _parse_wth_dates(wth_path)
        if not dates:
            return None

        pdate = _parse_planting_date(scenario.get("crop", {}).get("planting_date"))
        if not pdate:
            return None

        dmin, dmax = min(dates), max(dates)
        min_ok, max_ok = _feasible_bounds_from_dates(dmin, dmax)
        if min_ok <= pdate <= max_ok:
            return None

        # Clamp to feasible bounds (not only raw bounds).
        if pdate < min_ok:
            new_date = min_ok
        else:
            new_date = max_ok

        scenario["crop"]["planting_date"] = new_date.isoformat()
        if "dssat" in scenario and isinstance(scenario["dssat"], dict):
            scenario["dssat"]["PltDate"] = new_date.isoformat()

        return (
            f"⚠️ Date de semis ajustée pour WTH '{wth_path.name}': "
            f"{pdate} -> {new_date}"
        )
    except Exception:
        return None


def _sanitize_planting_date_for_department(dept, planting_date):
    """
    Force une date de semis valide et couverte par ENACTS.
    """
    df = load_enacts(dept).sort_values("date")
    if df.empty:
        return None
    dmin = df["date"].min().date()
    dmax = df["date"].max().date()
    min_ok, max_ok = _feasible_bounds_from_dates(dmin, dmax)
    p = _parse_planting_date(planting_date)
    if not p:
        p = max_ok
    if p < min_ok:
        p = min_ok
    if p > max_ok:
        p = max_ok
    return p.isoformat()


# ==========================================================
# 🚀 ENREGISTREMENT DES CALLBACKS
# ==========================================================
def register_callbacks(app):
    """
    Enregistre tous les callbacks Dash pour SIMAGRI v2
    """

    # ======================================================
    # 🗺️ CARTE + SOL
    # ======================================================
    @app.callback(
        [
            Output("map", "center"),
            Output("map", "zoom"),
            Output("dept-marker", "position"),
            Output("dept-geojson", "data"),
            Output("soil_type", "value"),
        ],
        Input("department", "value"),
    )
    def update_map_and_soil(dept_name):
        """
        Met à jour la carte, le marqueur et le type de sol
        en fonction du département sélectionné
        """

        # 🔒 Sécurité
        if not dept_name:
            return [14.15, -16.07], 7, [14.15, -16.07], None, None

        # 📍 GPS
        lat, lon = get_department_gps(dept_name)

        # 🌱 Type de sol
        soil = get_department_soil(dept_name)

        # 🗺️ Charger GeoJSON
        geojson = None
        try:
            with open(GEOJSON_PATH, encoding="utf-8") as f:
                geo = json.load(f)

            feature = None
            target = _norm_name(dept_name)
            for f in geo["features"]:
                name = (
                    f["properties"].get("NAME")
                    or f["properties"].get("name")
                    or f["properties"].get("ADM2_FR")
                    or f["properties"].get("ADM2_EN")
                    or ""
                )
                if _norm_name(name) == target:
                    feature = f
                    break

            if feature:
                geojson = {
                    "type": "FeatureCollection",
                    "features": [feature]
                }

        except Exception as e:
            print(f"⚠️ Erreur chargement GeoJSON : {e}")
            geojson = None

        return (
            [lat, lon],   # center
            12,            # zoom rapproché
            [lat, lon],   # marker
            geojson,      # contour département
            soil          # type de sol
        )

    # ======================================================
    # 🌱 AFFICHAGE BLOCS (Montrer/Cacher)
    # ======================================================
    @app.callback(
        Output("fertilization-block", "style"),
        Input("fertilization", "checked")
    )
    def toggle_fert(use):
        """Affiche/cache le bloc fertilisation"""
        return {"display": "block"} if use else {"display": "none"}

    @app.callback(
        Output("irrigation-block", "style"),
        Input("irrigation", "value")
    )
    def toggle_irrig(use):
        """Affiche/cache le bloc irrigation"""
        return {"display": "block"} if use == "MANUAL" else {"display": "none"}

    @app.callback(
        Output("socio-block", "style"),
        Input("toggle_socio", "n_clicks"),
        Input("reset_scenarios", "n_clicks"),
        prevent_initial_call=True
    )
    def toggle_socio(_toggle, _reset):
        """Affiche/cache le bloc socio-economique"""
        trig = get_triggered_id()
        if trig == "reset_scenarios":
            return {"display": "none"}
        return {"display": "block"}

    @app.callback(
        [
            Output("department", "value"),
            Output("crop", "value"),
            Output("cycle", "value"),
            Output("fertilization", "checked"),
            Output("irrigation", "value"),
            Output("simulation_mode", "value"),
            Output("area_ha", "value"),
            Output("prep_sol", "value"),
            Output("seed_type", "value"),
            Output("post_harvest", "value"),
            Output("labor_type", "value"),
        ],
        Input("reset_scenarios", "n_clicks"),
        prevent_initial_call=True,
    )
    def reset_main_ui(_reset):
        year_now = datetime.now().year
        return (
            "Kaolack",     # department
            "ML",          # crop
            "court",       # cycle
            False,         # fertilization
            "NONE",        # irrigation
            1,             # simulation_mode
            1,             # area_ha
            ["Labour"],    # prep_sol
            "Semence locale",  # seed_type
            [],            # post_harvest
            ["Semis"],     # labor_type
        )
    # ======================================================
    # 💧 IRRIGATION
    # ======================================================
    @app.callback(
        [
            Output("irrigation-store", "data"),
            Output("irrig_cost", "value"),
        ],
        [
            Input("irrigation", "value"),
            Input("add-irrigation", "n_clicks"),
            Input("auto-irrigation", "n_clicks"),
            Input({"type": "irrig_day", "index": ALL}, "value"),
            Input({"type": "irrig_mm", "index": ALL}, "value"),
            Input({"type": "irrig_price", "index": ALL}, "value"),
        ],
        [
            State("irrigation-store", "data"),
            State("crop", "value"),
        ],
    )
    def manage_irrigation(mode, add_clicks, auto_clicks, days, mms, prices, store, crop):
        """
        Gère l'ajout et la modification des irrigations
        """

        if mode != "MANUAL":
            return [], 0

        if not store:
            store = [{
                "doy": 20,
                "mm": 30,
                "price": 250
            }]

        trig = get_triggered_id()
        if trig == "auto-irrigation":
            irr_days, water_mm = get_irrigation_schedule(crop or "ML")
            if irr_days and water_mm:
                store = [
                    {"doy": int(d), "mm": float(water_mm), "price": 250.0}
                    for d in irr_days
                ]
        elif trig == "add-irrigation":
            store.append(store[-1].copy())

        total = 0
        for i, ir in enumerate(store):
            if i < len(days):
                ir["doy"] = days[i]
                ir["mm"] = mms[i]
                ir["price"] = prices[i]

            total += (ir["mm"] or 0) * (ir["price"] or 0)

        return store, total

    # Affichage lignes irrigation
    @app.callback(
        Output("irrigation-lines", "children"),
        Input("irrigation-store", "data"),
    )
    def render_irrigation_lines(data):
        """Affiche les lignes d'irrigation modifiables"""

        rows = []

        for i, ir in enumerate(data):
            cost = (ir["mm"] or 0) * (ir["price"] or 0)

            rows.append(
                dbc.Row([
                    dbc.Col(
                        dbc.Input(
                            id={"type": "irrig_day", "index": i},
                            type="number",
                            value=ir["doy"]
                        ), md=3
                    ),
                    dbc.Col(
                        dbc.Input(
                            id={"type": "irrig_mm", "index": i},
                            type="number",
                            value=ir["mm"]
                        ), md=3
                    ),
                    dbc.Col(
                        dbc.Input(
                            id={"type": "irrig_price", "index": i},
                            type="number",
                            value=ir["price"]
                        ), md=3
                    ),
                    dbc.Col(
                        dbc.Input(
                            value=cost,
                            disabled=True
                        ), md=3
                    ),
                ], className="mb-2")
            )

        return rows

    # Résumé irrigation
    @app.callback(
        Output("irrig_summary", "children"),
        Input("irrigation-store", "data"),
    )
    def update_irrig_summary(store):
        """Affiche un résumé des irrigations"""

        if not store:
            return "Aucune irrigation définie"

        total_mm = sum(ir["mm"] for ir in store if ir["mm"])
        total_events = len(store)

        return (
            f"{total_events} irrigations | "
            f"Eau totale = {total_mm} mm"
        )

    # ======================================================
    # 💰 SOCIO-ÉCONOMIE
    # ======================================================
    @app.callback(
        Output("prep_sol_cost", "value"),
        [
            Input("prep_sol", "value"),
            Input("area_ha", "value")
        ]
    )
    def update_prep_cost(ops, area):
        """Calcule le coût de préparation du sol"""
        return compute_soil_preparation_cost(ops, area)

    @app.callback(
        [
            Output("seed_qty", "value"),
            Output("seed_price", "value")
        ],
        Input("seed_type", "value"),
    )
    def update_seed_defaults(seed_type):
        """Charge les valeurs par défaut pour le type de semence"""
        data = SEEDS.get(seed_type, {})
        return data.get("qty", 0), data.get("price", 0)

    @app.callback(
        Output("seed_cost", "value"),
        [
            Input("seed_qty", "value"),
            Input("seed_price", "value"),
            Input("area_ha", "value")
        ]
    )
    def update_seed_cost(qty, price, area):
        """Calcule le coût des semences"""
        return compute_seed_cost(qty, price, area)

    @app.callback(
        Output("labor_cost", "value"),
        [
            Input("labor_type", "value"),
            Input("area_ha", "value")
        ]
    )
    def update_labor_cost(ops, area):
        """Calcule le coût de main-d'œuvre"""
        return compute_labor_cost(ops, area)

    @app.callback(
        Output("post_harvest_cost", "value"),
        [
            Input("post_harvest", "value"),
            Input("area_ha", "value")
        ]
    )
    def update_post_cost(ops, area):
        """Calcule le coût post-récolte"""
        return compute_post_harvest_cost(ops, area)

    @app.callback(
        Output("total_cost", "value"),
        [
            Input("prep_sol", "value"),
            Input("labor_type", "value"),
            Input("post_harvest", "value"),
            Input("seed_cost", "value"),
            Input("area_ha", "value"),
        ]
    )
    def update_total_cost(soil_ops, labor_ops, post_ops, seed_cost, area_ha):
        """Calcule le coût total de production"""
        return compute_total_socio_cost(
            soil_ops,
            labor_ops,
            post_ops,
            seed_cost,
            area_ha,
        )


    # ======================================================
    # 🌾 FERTILISATION
    # ======================================================
    @app.callback(
        [
            Output("fertilization-store", "data"),
            Output("fert_total_cost", "value")
        ],
        [
            Input("fertilization", "checked"),
            Input("add-fertilization", "n_clicks"),
            Input({"type": "fert_type", "index": ALL}, "value"),
            Input({"type": "fert_qty", "index": ALL}, "value")
        ],
        State("fertilization-store", "data"),
    )
    def manage_fert(use, add, types, qtys, store):
        """
        Gère l'ajout et la modification des fertilisants
        """

        if not use:
            return [], 0

        if not store:
            store = [{"type": "NPK", "qty": 150}]

        if get_triggered_id() == "add-fertilization":
            store.append(store[-1].copy())

        total = 0
        for i, f in enumerate(store):
            if i < len(types):
                f["type"] = types[i]
                f["qty"] = qtys[i]
            total += compute_fertilization_cost(f["type"], f["qty"])

        return store, total

    @app.callback(
        Output("fertilization-lines", "children"),
        Input("fertilization-store", "data"),
    )
    def render_fert_lines(data):
        """Affiche les lignes de fertilisation modifiables"""
        rows = []
        for i, f in enumerate(data):
            cost = compute_fertilization_cost(f["type"], f["qty"])
            rows.append(
                dbc.Row([
                    dbc.Col(dcc.Dropdown(
                        id={"type": "fert_type", "index": i},
                        options=[
                            {"label": "Compost", "value": "COMPOST"},
                            {"label": "NPK", "value": "NPK"},
                            {"label": "Urée", "value": "UREA"},
                        ],
                        value=f["type"],
                    ), md=4),
                    dbc.Col(dbc.Input(
                        id={"type": "fert_qty", "index": i},
                        type="number", value=f["qty"]
                    ), md=4),
                    dbc.Col(dbc.Input(value=cost, disabled=True), md=4),
                ])
            )
        return rows

    @app.callback(
        Output("fert_npk_summary", "children"),
        Input("fertilization-store", "data"),
    )
    def update_npk(store):
        """Affiche un résumé des apports NPK"""
        if not store:
            return "Aucun apport calculé"
        N = P = K = 0
        for f in store:
            npk = compute_npk_from_fertilizer(f["type"], f["qty"])
            N += npk["N"]
            P += npk["P"]
            K += npk["K"]
        return f"N = {N:.1f} | P = {P:.1f} | K = {K:.1f} kg/ha"


    # ======================================================
    # 🌧️ DATE DE SEMIS ENACTS
    # ======================================================
    @app.callback(
        [
            Output("recommended_sowing_date", "value"),
            Output("planting_date", "min_date_allowed"),
            Output("planting_date", "max_date_allowed"),
            Output("planting_date", "date"),
        ],
        [
            Input("department", "value"),
            Input("hist_start_year", "value"),
            Input("hist_end_year", "value"),
        ],
        State("planting_date", "date"),
    )
    def update_onset(dept, y0, y1, current_planting_date):
        """
        Calcule la date de semis recommandee basee sur les donnees ENACTS.
        Emp?che une date de semis invalide dans l'UI.
        """
        if not dept or not y0 or not y1:
            return "", None, None, current_planting_date
        try:
            df = load_enacts(dept).sort_values("date")
            if df.empty:
                return (
                    "Donnees ENACTS incompletes pour ce departement",
                    None,
                    None,
                    current_planting_date,
                )
            full_min = df["date"].min().date()
            full_max = df["date"].max().date()
            min_ok, max_ok = _feasible_bounds_from_dates(full_min, full_max)
            d, p = compute_probabilistic_onset(df, y0, y1)

            cur_dt = _parse_planting_date(current_planting_date) or max_ok

            if d:
                ref_year = cur_dt.year
                onset_dt = datetime.strptime(f"{d} {ref_year}", "%d %B %Y").date()
                min_dt = max(min_ok, onset_dt - timedelta(days=10))
                max_dt = min(max_ok, onset_dt + timedelta(days=10))
                if onset_dt < min_dt:
                    onset_dt = min_dt
                elif onset_dt > max_dt:
                    onset_dt = max_dt
                selected_dt = cur_dt if (min_dt <= cur_dt <= max_dt) else onset_dt
                msg = (
                    f"{d} (P={p:.0%}) | Fenetre: "
                    f"{min_dt.strftime('%d/%m/%Y')} - {max_dt.strftime('%d/%m/%Y')}"
                )
            else:
                min_dt = min_ok
                max_dt = max_ok
                selected_dt = cur_dt if (min_dt <= cur_dt <= max_dt) else max_ok
                msg = (
                    "Pas de date fiable | Fenetre ENACTS: "
                    f"{min_dt.strftime('%d/%m/%Y')} - {max_dt.strftime('%d/%m/%Y')}"
                )

            return msg, min_dt.isoformat(), max_dt.isoformat(), selected_dt.isoformat()
        except Exception as e:
            print(f"Warning onset: {e}")
            safe = _parse_planting_date(current_planting_date)
            return "Erreur calcul", None, None, safe.isoformat() if safe else None

    @app.callback(
        [
            Output("hist_start_year", "min"),
            Output("hist_start_year", "max"),
            Output("hist_start_year", "value"),
            Output("hist_end_year", "min"),
            Output("hist_end_year", "max"),
            Output("hist_end_year", "value"),
        ],
        [
            Input("department", "value"),
            Input("hist_start_year", "value"),
            Input("hist_end_year", "value"),
            Input("reset_scenarios", "n_clicks"),
        ],
    )
    def clamp_hist_years_to_enacts(dept_name, y0, y1, reset_clicks):
        """
        Limite la plage historique a la couverture ENACTS du departement.
        """
        trig = get_triggered_id()
        if trig == "reset_scenarios":
            year_now = datetime.now().year
            y0 = year_now - 30
            y1 = year_now - 1
        try:
            df = load_enacts(dept_name).sort_values("date")
            if df.empty:
                year_now = datetime.now().year
                return 1991, year_now, y0, 1991, year_now, y1

            ymin = int(df["date"].dt.year.min())
            ymax = min(int(df["date"].dt.year.max()), 2022)
            y0 = int(y0) if y0 is not None else ymin
            y1 = int(y1) if y1 is not None else ymax

            y0 = max(ymin, min(y0, ymax))
            y1 = max(ymin, min(y1, ymax))
            if y0 > y1:
                y1 = y0

            return ymin, ymax, y0, ymin, ymax, y1
        except Exception:
            return 1991, 2022, y0, 1991, 2022, y1


    @app.callback(
        Output("scenario-store", "data"),
        Input("add_scenario", "n_clicks"),
        Input("reset_scenarios", "n_clicks"),
        State("scenario-store", "data"),
        State("department", "value"),
        State("crop", "value"),
        State("cycle", "value"),
        State("planting_date", "date"),
        State("hist_start_year", "value"),
        State("hist_end_year", "value"),
        State("recommended_sowing_date", "value"),
        State("fertilization", "checked"),
        State("fertilization-store", "data"),
        State("irrigation", "value"),
        State("irrigation-store", "data"),
        State("fert_total_cost", "value"),
        State("irrig_cost", "value"),
        State("total_cost", "value"),
        State("toggle_socio", "n_clicks"),
        State("simulation_mode", "value"),
        prevent_initial_call=True,
    )
    def add_scenario(
        n_clicks,
        reset_clicks,
        stored_scenarios,
        department,
        crop,
        cycle,
        planting_date,
        hist_start_year,
        hist_end_year,
        recommended_sowing_date,
        fertilization,
        fertilization_plan,
        irrigation_mode,
        irrigation_plan,
        fert_cost,
        irrig_cost,
        total_cost,
        toggle_socio_clicks,
        simulation_mode,
    ):
        """
        Ajoute un nouveau scénario aux scénarios stockés
        et met à jour le tableau d'affichage
        """
        trig = get_triggered_id()
        if trig == "reset_scenarios":
            return []

        # 🔒 Sécurité
        if stored_scenarios is None:
            stored_scenarios = []
        max_scenarios = _parse_max_scenarios(simulation_mode)
        if len(stored_scenarios) >= max_scenarios:
            return stored_scenarios

        # --------------------------------------------------
        # 1️⃣ Construire le scénario COMPLET depuis l'UI
        # --------------------------------------------------
        safe_planting_date = _sanitize_planting_date_for_department(department, planting_date)
        if not safe_planting_date:
            print(f"⚠️ Scenario ignore: donnees ENACTS invalides pour {department}")
            return stored_scenarios
        # Clamp des annees historiques a la couverture ENACTS du departement.
        try:
            _df = load_enacts(department).sort_values("date")
            y_min = int(_df["date"].dt.year.min())
            y_max = min(int(_df["date"].dt.year.max()), 2022)
            hist_start_year = int(hist_start_year) if hist_start_year is not None else y_min
            hist_end_year = int(hist_end_year) if hist_end_year is not None else y_max
            hist_start_year = max(y_min, min(hist_start_year, y_max))
            hist_end_year = max(y_min, min(hist_end_year, y_max))
            if hist_start_year > hist_end_year:
                hist_end_year = hist_start_year
        except Exception:
            pass

        # Cout de production: 0 par defaut.
        # Si la section socio-economique est ouverte, on prend le total calcule.
        fixed_cost = (total_cost or 0) if (toggle_socio_clicks or 0) > 0 else 0

        irrig_enabled = irrigation_mode in ("MANUAL", "AUTO")
        irrig_method = irrigation_mode if irrigation_mode in ("MANUAL", "AUTO") else "NONE"

        scenario = build_scenario_from_ui(
            scenario_id=f"S{len(stored_scenarios) + 1:03d}",
            department=department,
            crop=crop,
            cycle=cycle,
            planting_date=safe_planting_date,
            hist_start_year=hist_start_year,
            hist_end_year=hist_end_year,
            recommended_sowing_date=recommended_sowing_date,
            recommended_sowing_prob=None,
            fertilization=fertilization,
            fertilization_plan=fertilization_plan or [],
            irrigation=irrig_enabled,
            irrigation_plan=(irrigation_plan or []) if irrig_method == "MANUAL" else [],
            costs={
                "CropPrice": 200,
                "NFertCost": fert_cost or 0,
                "SeedCost": 0,
                "IrrigCost": irrig_cost or 0,
                "OtherVariableCosts": 0,
                "FixedCosts": fixed_cost,
            },
        )
        scenario.setdefault("irrigation", {})["method"] = irrig_method

        # --------------------------------------------------
        # 2️⃣ Ajouter au scenario-store
        # --------------------------------------------------
        stored_scenarios.append(scenario)

        return stored_scenarios

    @app.callback(
        [
            Output("scenario-table", "data"),
            Output("scenario-table", "columns"),
        ],
        Input("scenario-store", "data"),
        Input("simulation-results-store", "data"),
    )
    def render_scenario_table(stored_scenarios, sim_results):
        if not stored_scenarios:
            return [], []
        return build_table(stored_scenarios, sim_results or {})


    # ======================================================
    # ▶️ SIMULATION DSSAT
    # ======================================================
    @app.callback(
        [
            Output("comparison-output", "children"),
            Output("simulation-results-store", "data"),
        ],
        Input("run_simulation", "n_clicks"),
        Input("reset_scenarios", "n_clicks"),
        State("scenario-store", "data"),
        State("simulation-results-store", "data"),
        State("simulation_mode", "value"),
        prevent_initial_call=True,
    )
    def run_dssat_from_ui(n_clicks, reset_clicks, scenarios, sim_results, simulation_mode):
        """
        Lance la simulation DSSAT historique sur l'intervalle d'annees choisi.
        """

        trig = get_triggered_id()
        if trig == "reset_scenarios":
            return "Ajoutez un scenario puis cliquez sur Simuler.", {}
        if not n_clicks:
            return "Cliquez sur le bouton Simuler", (sim_results or {})

        if not scenarios or len(scenarios) == 0:
            return "Aucun scenario a simuler. Ajoutez au moins un scenario.", (sim_results or {})

        messages = []
        sim_results = dict(sim_results or {})
        max_scenarios = _parse_max_scenarios(simulation_mode)
        scenarios = scenarios[:max_scenarios]

        for i, scenario in enumerate(scenarios, start=1):
            sid = scenario.get("id_scenario")
            try:
                dept = scenario.get("location", {}).get("department")
                try:
                    enacts_df = load_enacts(dept).sort_values("date")
                except Exception as e:
                    sim_results[sid] = {"status": "ERREUR"}
                    messages.append(f"Scenario {i} - ENACTS indisponible pour '{dept}' ({e})")
                    continue

                if enacts_df.empty:
                    sim_results[sid] = {"status": "ERREUR"}
                    messages.append(f"Scenario {i} - ENACTS vide pour '{dept}'")
                    continue

                y0 = int(scenario.get("climate", {}).get("hist_start_year") or enacts_df["date"].dt.year.min())
                y1 = int(scenario.get("climate", {}).get("hist_end_year") or enacts_df["date"].dt.year.max())
                if y0 > y1:
                    y0, y1 = y1, y0
                years = list(range(y0, y1 + 1))
                if len(years) > 60:
                    years = years[:60]

                base_date = scenario.get("crop", {}).get("planting_date")
                history = []
                year_errors = 0
                dssat_dir = BASE_DIR / "dssat"

                # Optimisation: generation meteo une seule fois par scenario.
                scenario_base = copy.deepcopy(scenario)
                wth_path = ensure_weather_for_scenario(scenario_base, dssat_dir)
                if wth_path is None:
                    sim_results[sid] = {"status": "ERREUR"}
                    messages.append(f"Scenario {i} - meteo DSSAT non disponible")
                    continue
                wth_dates, _ = _parse_wth_dates(wth_path)
                if not wth_dates:
                    sim_results[sid] = {"status": "ERREUR"}
                    messages.append(f"Scenario {i} - WTH invalide: {Path(wth_path).name}")
                    continue
                wth_min, wth_max = min(wth_dates), max(wth_dates)
                min_ok, max_ok = _feasible_bounds_from_dates(wth_min, wth_max)

                for y in years:
                    scenario_run = copy.deepcopy(scenario_base)
                    run_date = _planting_date_for_year(base_date, y)
                    if not run_date:
                        year_errors += 1
                        continue
                    pdt = _parse_planting_date(run_date)
                    if not pdt:
                        year_errors += 1
                        continue
                    # Verification rapide de couverture meteo (evite validation complete a chaque annee).
                    if pdt < min_ok or pdt > max_ok:
                        year_errors += 1
                        continue
                    scenario_run.setdefault("crop", {})["planting_date"] = pdt.isoformat()
                    scenario_run.setdefault("dssat", {})["PltDate"] = pdt.isoformat()

                    x_path = write_x_file(
                        scenario_run,
                        output_dir=str(dssat_dir / "exp")
                    )
                    if not x_path.exists():
                        year_errors += 1
                        continue

                    snx_output_dir = Path("/app/dssat/snx")
                    snx_output_dir.mkdir(parents=True, exist_ok=True)
                    snx_path = Path(write_snx_file(
                        scenario_run,
                        x_path.name,
                        output_dir=str(snx_output_dir)
                    ))

                    result = run_dssat_simulation(
                        str(snx_path),
                        dssat_workdir=str(dssat_dir)
                    )
                    if result["returncode"] != 0:
                        year_errors += 1
                        continue

                    parsed = parse_summary_metrics(BASE_DIR / "dssat" / "Summary.OUT")
                    status = classify_dssat_status(parsed) if parsed else "VIDE"
                    row = dict(parsed or {})
                    row["status"] = status
                    row["year"] = y
                    history.append(row)

                if history:
                    agg = _aggregate_history(history)
                    agg["years_total"] = len(years)
                    agg["years_err"] = year_errors
                    sim_results[sid] = agg
                    messages.append(
                        f"Scenario {i} - historique {y0}-{y1}: "
                        f"{agg.get('years_ok',0)}/{len(years)} annees simulees | "
                        f"HARWT moyen={agg.get('HARWT','-')} kg/ha"
                    )
                else:
                    sim_results[sid] = {"status": "ERREUR", "years_ok": 0, "years_total": len(years), "years_err": year_errors}
                    messages.append(
                        f"Scenario {i} - aucune annee simulee sur {y0}-{y1}"
                    )

            except Exception as e:
                sim_results[sid] = {"status": "ERREUR"}
                messages.append(f"Scenario {i} - erreur: {str(e)[:120]}")

        return build_simulation_output(scenarios, sim_results, messages), sim_results
