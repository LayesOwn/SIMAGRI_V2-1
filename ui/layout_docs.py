try:
    from dash import html
except Exception:
    import dash_html_components as html

import dash_bootstrap_components as dbc
from pathlib import Path


def _captures_section():
    assets_dir = Path(__file__).resolve().parents[1] / "assets"
    patterns = [
        "capture_*.png",
        "capture_*.jpg",
        "capture_*.jpeg",
        "capture_*.webp",
        "screenshot_*.png",
        "screenshot_*.jpg",
        "screenshot_*.webp",
        "doc_*.png",
        "doc_*.jpg",
        "doc_*.webp",
        "Carte_Statique.webp",
    ]
    captures = []
    for pat in patterns:
        captures.extend(sorted(assets_dir.glob(pat)))

    if not captures:
        return dbc.Alert(
            "Aucune capture detectee dans assets/. "
            "Ajoutez des images nommees capture_*.png ou screenshot_*.png pour les afficher ici.",
            color="info",
            className="mb-0",
        )

    cards = []
    for p in captures:
        cards.append(
            dbc.Col(
                dbc.Card(
                    [
                        dbc.CardImg(src=f"/assets/{p.name}", top=True),
                        dbc.CardBody(html.Small(p.name, className="text-muted")),
                    ],
                    className="h-100",
                ),
                md=6,
                lg=4,
                className="mb-3",
            )
        )
    return dbc.Row(cards, className="g-3")


def layout_docs():
    return dbc.Container(
        fluid=True,
        className="simagri-page simagri-docs",
        children=[
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Button(
                            "Retour vers Accueil",
                            href="/",
                            color="secondary",
                            size="sm",
                        ),
                        width="auto",
                    )
                ],
                className="mt-3 mb-2",
            ),
            html.H3("Documentation SIMAGRI", className="text-center my-3"),
            dbc.Card(
                [
                    dbc.CardHeader("Mode de fonctionnement global"),
                    dbc.CardBody(
                        [
                            html.P(
                                "SIMAGRI construit un scenario agronomique, genere les fichiers DSSAT "
                                "(meteo, X, SNX), execute DSSAT, puis lit les sorties pour afficher "
                                "rendements, bilan hydrique et indicateurs economiques."
                            ),
                            html.P(
                                "Deux workflows sont disponibles: Historique et Previsionnelle. "
                                "Les deux partagent la meme chaine DSSAT, mais pas la meme logique meteo."
                            ),
                        ]
                    ),
                ],
                className="mb-3",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Card(
                            [
                                dbc.CardHeader("Partie 1 - Analyse Historique"),
                                dbc.CardBody(
                                    [
                                        html.H6("Donnees utilisees"),
                                        html.Ul(
                                            [
                                                html.Li("Pluie et temperature: ENACTS par departement (data/enacts)."),
                                                html.Li("Sol: mapping departement -> code DSSAT SOIL."),
                                                html.Li("Cultivars: fichiers DSSAT (*.CUL) selon culture et cycle."),
                                            ]
                                        ),
                                        html.H6("Choix des parametres"),
                                        html.Ul(
                                            [
                                                html.Li("Departement, culture, cycle varietal."),
                                                html.Li("Plage d'annees historique (bornee a la couverture ENACTS)."),
                                                html.Li("Date de semis, fertilisation, irrigation (non/manuelle/auto)."),
                                                html.Li("Couts socio-economiques (optionnels)."),
                                            ]
                                        ),
                                        html.H6("Date de semis conseillee (historique)"),
                                        html.P(
                                            "Calculee sur ENACTS via un onset probabiliste: "
                                            "pluie >= 15 mm sur 2 jours, puis absence de secheresse "
                                            "longue (>= 7 jours secs) sur la fenetre suivante. "
                                            "La date retenue est celle avec la probabilite maximale "
                                            "dans la plage d'annees choisie."
                                        ),
                                        html.H6("Processus de simulation"),
                                        html.Ol(
                                            [
                                                html.Li("Creation du scenario depuis l'UI."),
                                                html.Li("Generation du fichier meteo DSSAT pour la station du departement."),
                                                html.Li("Validation des entrees (WTH, sol, cultivar, dates)."),
                                                html.Li("Ecriture des fichiers X et SNX."),
                                                html.Li("Execution DSSAT dans Docker."),
                                                html.Li("Lecture Summary/console et calcul des indicateurs affiches."),
                                            ]
                                        ),
                                    ]
                                ),
                            ],
                            className="h-100",
                        ),
                        md=12,
                        lg=6,
                        className="mb-3",
                    ),
                    dbc.Col(
                        dbc.Card(
                            [
                                dbc.CardHeader("Partie 2 - Analyse Previsionnelle"),
                                dbc.CardBody(
                                    [
                                        html.H6("Donnees utilisees"),
                                        html.Ul(
                                            [
                                                html.Li("Actuellement: pool de reference ENACTS 1991-2022 par departement."),
                                                html.Li("Le moteur forecast genere des realisations meteo quotidiennes."),
                                                html.Li("Sol/cultivar/parametres DSSAT idem workflow historique."),
                                            ]
                                        ),
                                        html.H6("Choix des parametres"),
                                        html.Ul(
                                            [
                                                html.Li("Departement, culture, cycle, date de semis, annee cible."),
                                                html.Li("Methode: Prevision probabiliste (re-echantillonnage BN/NN/AN)."),
                                                html.Li("Nombre de realisations (ex: 20)."),
                                                html.Li("Gestion fertilisation et irrigation (non/manuelle/auto)."),
                                            ]
                                        ),
                                        html.H6("Date de semis conseillee (prevision)"),
                                        html.P(
                                            "Regle appliquee sur pluie journaliere: "
                                            "seuil cumule sur 1-3 jours (Nord: 15 mm, Sud: 20 mm) "
                                            "et pas de pause seche de 20 jours ensuite. "
                                            "Si l'annee cible n'est pas disponible, la date provient "
                                            "de la climatologie mediane du pool de reference."
                                        ),
                                        html.H6("Processus de simulation"),
                                        html.Ol(
                                            [
                                                html.Li("Creation du scenario forecast depuis l'UI."),
                                                html.Li("Generation N realisations meteo conditionnees BN/NN/AN."),
                                                html.Li("Ecriture WTH + X + SNX pour chaque run."),
                                                html.Li("Execution DSSAT pour chaque realisation."),
                                                html.Li("Aggregation des sorties: mediane, P20, P80 (HARWT/TOPWT)."),
                                                html.Li("Affichage tableau + graphiques (agro, eau, economie, incertitude)."),
                                            ]
                                        ),
                                    ]
                                ),
                            ],
                            className="h-100",
                        ),
                        md=12,
                        lg=6,
                        className="mb-3",
                    ),
                ]
            ),
            dbc.Card(
                [
                    dbc.CardHeader("Lecture des sorties DSSAT"),
                    dbc.CardBody(
                        html.Ul(
                            [
                                html.Li("HARWT: rendement grain (kg/ha)."),
                                html.Li("TOPWT: biomasse aerienne (kg/ha)."),
                                html.Li("RAIN/PRCM: pluie cumulee sur la campagne simulee."),
                                html.Li("TIRR/IRCM: irrigation cumulee appliquee."),
                                html.Li("CET/ETCM: evapotranspiration cumulee."),
                                html.Li("MAT: jours jusqu'a maturite."),
                            ]
                        )
                    ),
                ],
                className="mb-3",
            ),
            dbc.Card(
                [
                    dbc.CardHeader("Captures d'ecran"),
                    dbc.CardBody(_captures_section()),
                ]
            ),
            html.Div(style={"height": "1rem"}),
        ],
    )
