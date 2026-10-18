# TEMA GLOBAL DO RELATÓRIO
# Define as cores e fontes do relatório em qmd

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager

PASTA_FONTES = Path(__file__).resolve().parents[2] / "fonts"


def _registrar_fontes():
    """Registra a Montserrat do repositório; sem isso o matplotlib cai na fonte padrão."""
    for arquivo in PASTA_FONTES.glob("*.ttf"):
        font_manager.fontManager.addfont(str(arquivo))
    nomes = {f.name for f in font_manager.fontManager.ttflist}
    return "Montserrat" if "Montserrat" in nomes else "DejaVu Sans"


def set_report_theme():

    # ---------- PALETA ----------
    # Séries: vermelho e azul validados para daltonismo (ΔE ≥ 19 em deuteranopia) e contraste.
    # O bordô original (#8E1616) é escuro demais para marca de dados e fica só no texto de destaque.
    COLORS = {
        "primary": "#B23A30",     # série principal
        "secondary": "#3B7DB5",   # segunda série (comparações)
        "tertiary": "#C8962E",    # terceira série
        "neutral": "#C9C3BB",     # marcas sem destaque
        "highlight": "#E8C999",   # faixas de destaque (ex.: lacuna de registro)
        "brand": "#8E1616",       # bordô da identidade, apenas em texto
        "ink": "#2B2B2B",         # texto principal
        "muted": "#6B6B6B",       # texto secundário
        "grid": "#E6E2DC",        # grade e eixos discretos
        "axis": "#D9D9D9",
    }

    # ---------- CONFIGURAÇÕES GERAIS ----------
    plt.rcParams.update({
        "font.family": _registrar_fontes(),
        "font.size": 10,
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
        "axes.titlecolor": COLORS["ink"],
        "axes.titlelocation": "left",
        "axes.titlepad": 10,
        "axes.labelsize": 10,
        "axes.labelcolor": COLORS["muted"],
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.edgecolor": COLORS["grid"],
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": False,
        "grid.color": COLORS["grid"],
        "grid.linewidth": 0.8,
        "xtick.color": COLORS["muted"],
        "ytick.color": COLORS["muted"],
        "xtick.major.size": 0,
        "ytick.major.size": 0,
        "legend.frameon": False,
        "figure.dpi": 150,
        "savefig.bbox": "tight",
        "savefig.dpi": 300,
    })

    return COLORS
