# TEMA GLOBAL DO RELATÓRIO
#Define as cores e fontes do relatório em qmd

import matplotlib.pyplot as plt
import seaborn as sns

def set_report_theme():
    
    # ---------- PALETA OFICIAL ----------
    COLORS = {
        "primary": "#8E1616",     # títulos / elementos principais
        "highlight": "#E8C999",   # destaques
        "secondary": "#C97B63",   # tom intermediário derivado
        "neutral": "#F8EEDF",     # fundo suave
        "axis": "#D9D9D9"         # eixos discretos
    }

    # ---------- CONFIGURAÇÕES GERAIS ----------
    plt.rcParams.update({

        # Fonte
        "font.family": "DejaVu Sans",
        "font.size": 11,

        # Títulos
        "axes.titlesize": 14,
        "axes.titleweight": "bold",
        "axes.titlecolor": COLORS["primary"],

        # Labels
        "axes.labelsize": 11,
        "axes.labelcolor": COLORS["primary"],

        # Fundo
        "figure.facecolor": "white",
        "axes.facecolor": COLORS["neutral"],

        # Grid desligado
        "axes.grid": False,

        # Bordas
        "axes.edgecolor": COLORS["axis"],

        # Ticks
        "xtick.color": COLORS["primary"],
        "ytick.color": COLORS["primary"],
        "xtick.major.size": 0,
        "ytick.major.size": 0,

        # Exportação
        "savefig.bbox": "tight",
        "savefig.dpi": 300
    })

    # Remove estilos herdados do seaborn
    sns.set_style("white")

    return COLORS


# Ativa o tema
COLORS = set_report_theme()