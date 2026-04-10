#Configuração padrão dos principais gráficos utilizados no relatório
#Este código serve para reduzir os chuncks de formatação de gráficos no relatório final

import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

# CONFIGURAÇÃO PADRÃO

def _setup_axes(title, xlabel, ylabel):

    plt.title(title, loc="center", pad=15)

    plt.xlabel(xlabel)
    plt.ylabel(ylabel)

    # remove grid
    plt.grid(False)

    # remove bordas superiores/direita
    sns.despine(left=True, bottom=True)


def _add_value_labels(ax, orientation="vertical"):

    for container in ax.containers:
        for bar in container:

            if orientation == "vertical":
                height = bar.get_height()
                ax.text(
                    bar.get_x() + bar.get_width()/2,
                    height,
                    f'{int(height)}',
                    ha='center',
                    va='bottom',
                    fontsize=10
                )

            else:
                width = bar.get_width()
                ax.text(
                    width,
                    bar.get_y() + bar.get_height()/2,
                    f'{int(width)}',
                    va='center',
                    ha='left',
                    fontsize=10
                )


def _highlight_colors(values, COLORS):

    order = np.argsort(values)[::-1]

    colors = [COLORS["neutral"]] * len(values)

    if len(values) >= 1:
        colors[order[0]] = COLORS["primary"]

    if len(values) >= 2:
        colors[order[1]] = COLORS["highlight"]

    return colors

# 1️⃣ BARRAS HORIZONTAIS COM DESTAQUE

def bar_horizontal_highlight(
    df,
    x,
    y,
    title,
    COLORS,
    xlabel=None,
    ylabel=None,
    label_offset=0.02  # controla distância do label (tipo hjust)
):

    df_plot = df.sort_values(y, ascending=True)

    colors = _highlight_colors(df_plot[y].values, COLORS)

    plt.figure(figsize=(8, 5))

    ax = plt.barh(
        df_plot[x],
        df_plot[y],
        color=colors
    )

    plt.yticks(rotation=0)
    plt.xticks(rotation=0)

    # Função auxiliar para formatar automaticamente
    def format_label(label):
        return label.replace("_", " ").title()

    # eixo invertido (horizontal)
    final_xlabel = xlabel if xlabel else format_label(y)
    final_ylabel = ylabel if ylabel else format_label(x)

    _setup_axes(
        title,
        xlabel=final_xlabel,
        ylabel=final_ylabel
    )

    # cálculo do offset baseado no range do eixo X
    x_min, x_max = df_plot[y].min(), df_plot[y].max()
    offset = (x_max - x_min) * label_offset

    # labels externos (à direita das barras)
    for i, v in enumerate(df_plot[y]):
        plt.text(
            v + offset,              # desloca para fora
            i,                       # posição no eixo Y
            str(int(v)),
            va="center",
            ha="left",               # ancora à esquerda → texto cresce pra direita
            fontsize=10
        )

    plt.tight_layout()
    plt.show()


# 2️⃣ BARRAS VERTICAIS (SÉRIE TEMPORAL)

def bar_timeseries(
    df,
    x,
    y,
    title,
    COLORS,
    xlabel=None,
    ylabel=None
):

    plt.figure(figsize=(9, 4.5))

    ax = plt.bar(
        df[x],
        df[y],
        color=COLORS["primary"]
    )

    plt.xticks(rotation=15)
    plt.yticks(rotation=0)

    # Função auxiliar para formatar automaticamente
    def format_label(label):
        return label.replace("_", " ").title()

    # Usa o manual se fornecido, senão formata automaticamente
    final_xlabel = xlabel if xlabel else format_label(x)
    final_ylabel = ylabel if ylabel else format_label(y)

    _setup_axes(title, xlabel=final_xlabel, ylabel=final_ylabel)

    _add_value_labels(plt.gca())

    plt.tight_layout()
    plt.show()

# 3️⃣ BARRAS VERTICAIS ORDENADAS + DESTAQUE

def bar_vertical_sorted_highlight(
    df,
    x,
    y,
    title,
    COLORS
):

    df_plot = df.sort_values(y, ascending=False)

    colors = _highlight_colors(df_plot[y].values, COLORS)

    plt.figure(figsize=(8, 5))

    ax = plt.bar(
        df_plot[x],
        df_plot[y],
        color=colors
    )

    plt.xticks(rotation=0)
    plt.yticks(rotation=0)

    _setup_axes(title, xlabel=x, ylabel=y)

    _add_value_labels(plt.gca())

    plt.tight_layout()
    plt.show()


# 4️⃣ GRÁFICO DE LINHAS

def line_chart(
    df,
    x,
    y,
    title,
    COLORS,
    xlabel=None,
    ylabel=None,
    label_offset=0.05
):

    plt.figure(figsize=(9, 4.5))

    plt.plot(
        df[x],
        df[y],
        linewidth=2.5,
        marker="o",
        color=COLORS["primary"]
    )

    plt.xticks(rotation=0)
    plt.yticks(rotation=0)

    # Função auxiliar para formatar automaticamente
    def format_label(label):
        return label.replace("_", " ").title()

    # Labels finais
    final_xlabel = xlabel if xlabel else format_label(x)
    final_ylabel = ylabel if ylabel else format_label(y)

    _setup_axes(title, xlabel=final_xlabel, ylabel=final_ylabel)

    # cálculo do offset
    y_min, y_max = df[y].min(), df[y].max()
    offset = (y_max - y_min) * label_offset

    # identifica o maior valor
    max_value = y_max

    # labels nos pontos
    for i, v in enumerate(df[y]):
        color = COLORS["primary"] if v == max_value else "black"

        plt.text(
            df[x].iloc[i],
            v + offset,
            str(int(v)),
            ha="center",
            va="bottom",
            fontsize=10,
            color=color,
            fontweight="bold" if v == max_value else "normal"
        )

    plt.tight_layout()
    plt.show()

#Formatar percentuais
from matplotlib.ticker import FuncFormatter

def percent_formatter(x, pos):
    return f"{x:.1f}%".replace(".", ",")

#Séries temporais com destaque
def bar_vertical_temporal_highlight(
    df,
    x,
    y,
    title,
    COLORS,
    xlabel=None,
    ylabel=None
):
    """
    Gráfico de barras verticais para variáveis temporais
    (mantém ordem do dataframe e destaca as 2 maiores categorias)
    """

    # NÃO ordena — respeita ordem temporal já definida
    df_plot = df.copy()

    # destaca maiores valores
    colors = _highlight_colors(df_plot[y].values, COLORS)

    plt.figure(figsize=(8, 5))

    ax = plt.bar(
        df_plot[x],
        df_plot[y],
        color=colors
    )

    # labels horizontais
    plt.xticks(rotation=15)
    plt.yticks(rotation=0)

    # Função auxiliar para formatar automaticamente
    def format_label(label):
        return label.replace("_", " ").title()  # ou .capitalize()

    # Define rótulos finais
    final_xlabel = xlabel if xlabel else format_label(x)
    final_ylabel = ylabel if ylabel else format_label(y)

    # padrão visual do relatório
    _setup_axes(
        title,
        xlabel=final_xlabel,
        ylabel=final_ylabel
    )

    # valores nas barras
    _add_value_labels(plt.gca())

    plt.tight_layout()
    plt.show()