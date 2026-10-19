"""Gráficos do relatório analítico.

Cada função recebe dados já agregados (ver report_stats.py) e desenha uma figura.
Convenções: um único eixo de valores, marcas finas, rótulos seletivos e texto em
tinta neutra; a cor identifica a série, nunca a ordem. Com duas ou mais séries, a
legenda fica entre o título e o gráfico, fora da área dos dados.
"""

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import FuncFormatter, MaxNLocator, NullFormatter, NullLocator

MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]


def _virgula(texto):
    return texto.replace(".", ",")


def _rotulo_pct(v, _=None):
    """Percentual sem casas quando o valor é inteiro (0,10 -> '10%') e com uma casa nos demais."""
    pct = round(v * 100, 6)
    return _virgula(f"{pct:.0f}%" if pct == int(pct) else f"{pct:.1f}%")


def _eixo_pct(eixo):
    eixo.set_major_locator(MaxNLocator(nbins=5, steps=[1, 2, 5, 10]))
    eixo.set_major_formatter(FuncFormatter(_rotulo_pct))


def _titulo_com_legenda(ax, titulo, ncol):
    """Título acima e legenda logo abaixo dele, sem sobrepor marcas."""
    ax.set_title(titulo, pad=24)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=ncol, fontsize=8, borderaxespad=0.3, handlelength=1.6)


def serie_diaria(diario, lacunas, COLORS, titulo, janela=7):
    """Contagem diária com média móvel e faixas das lacunas de registro."""
    fig, ax = plt.subplots(figsize=(9, 3.8))
    ax.plot(diario.index, diario.values, color=COLORS["neutral"], linewidth=0.8, label="Ocorrências no dia")
    media = diario.rolling(janela, center=True).mean()
    ax.plot(media.index, media.values, color=COLORS["primary"], linewidth=2, label=f"Média móvel de {janela} dias")
    ax.set_ylim(0, diario.max() * 1.08)
    for inicio, fim, _ in lacunas:
        ax.axvspan(inicio, fim, color=COLORS["highlight"], alpha=0.6, linewidth=0)
        ax.annotate("Sem registros\nno sistema", xy=(inicio, ax.get_ylim()[1] * 0.97), xytext=(-4, 0), textcoords="offset points",
                    fontsize=8, color=COLORS["muted"], ha="right", va="top")
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: MESES[mdates.num2date(v).month - 1]))
    ax.yaxis.grid(True)
    ax.set_ylabel("Ocorrências por dia")
    _titulo_com_legenda(ax, titulo, ncol=2)
    fig.tight_layout()
    return fig


def barras_media_diaria(tabela, COLORS, titulo, destaque=None, ylabel="Ocorrências por dia (média)"):
    """Média diária por categoria do calendário, com a média geral como referência."""
    fig, ax = plt.subplots(figsize=(8, 3.6))
    destaque = set(destaque or [])
    cores = [COLORS["primary"] if c in destaque else COLORS["neutral"] for c in tabela["categoria"]]
    rotulos = [c[:3] for c in tabela["categoria"]]
    ax.bar(rotulos, tabela["media_diaria"], color=cores, width=0.6)
    media = tabela["observado"].sum() / tabela["dias"].sum()
    ax.axhline(media, color=COLORS["ink"], linewidth=1)
    # Rótulo da média na margem direita, fora das barras e dos valores.
    ax.annotate(_virgula(f"Média\n{media:.1f}"), xy=(1, media), xycoords=("axes fraction", "data"), xytext=(4, 0),
                textcoords="offset points", ha="left", va="center", fontsize=8, color=COLORS["ink"])
    for i, v in enumerate(tabela["media_diaria"]):
        # Fundo branco: o rótulo continua legível quando a barra termina perto da linha da média.
        ax.annotate(_virgula(f"{v:.1f}"), xy=(i, v), xytext=(0, 3), textcoords="offset points", ha="center", fontsize=8, color=COLORS["muted"],
                    bbox=dict(boxstyle="square,pad=0.15", fc="white", ec="none"))
    ax.yaxis.grid(True)
    ax.set_axisbelow(True)
    ax.set_ylabel(ylabel)
    ax.set_title(titulo)
    fig.tight_layout()
    return fig


def heatmap_hora_dia(matriz, COLORS, titulo, legenda="Ocorrências por dia"):
    """Média de ocorrências por dia em cada combinação de hora e dia da semana (escala sequencial)."""
    fig, ax = plt.subplots(figsize=(9, 3.4))
    im = ax.imshow(matriz.values, aspect="auto", cmap="Reds", interpolation="nearest", vmin=0)
    ax.set_yticks(range(len(matriz.index)), [d[:3] for d in matriz.index])
    ax.set_xticks(range(0, 24, 2), [f"{h}h" for h in range(0, 24, 2)])
    barra = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.01)
    barra.set_label(legenda, fontsize=8, color=COLORS["muted"])
    barra.outline.set_visible(False)
    barra.ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: _virgula(f"{v:g}")))
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title(titulo)
    fig.tight_layout()
    return fig


def barras_prevalencia(tabela, COLORS, titulo, rotulo="rotulo"):
    """Proporção por categoria com IC 95% (barras horizontais, ordenadas)."""
    t = tabela.sort_values("p")
    fig, ax = plt.subplots(figsize=(8, 0.42 * len(t) + 1.2))
    y = np.arange(len(t))
    ax.barh(y, t["p"], color=COLORS["primary"], height=0.55)
    ax.errorbar(t["p"], y, xerr=[t["p"] - t["ic_inf"], t["ic_sup"] - t["p"]], fmt="none", ecolor=COLORS["ink"], elinewidth=1, capsize=2)
    for yi, p, hi in zip(y, t["p"], t["ic_sup"]):
        ax.annotate(_virgula(f"{p * 100:.1f}%"), xy=(hi, yi), xytext=(4, 0), textcoords="offset points", va="center", fontsize=8, color=COLORS["ink"])
    ax.set_yticks(y, t[rotulo])
    _eixo_pct(ax.xaxis)
    ax.xaxis.grid(True)
    ax.set_axisbelow(True)
    ax.set_xlim(0, t["ic_sup"].max() * 1.15)
    ax.set_title(titulo)
    fig.tight_layout()
    return fig


def forest(tabela, COLORS, titulo, series=("bruta", "ajustada"), nomes=("Bruta", "Ajustada pelo tamanho do histórico")):
    """Razões de prevalência com IC 95% em escala log; duas séries lado a lado por linha."""
    fig, ax = plt.subplots(figsize=(8, 0.5 * len(tabela) + 1.6))
    y = np.arange(len(tabela))[::-1]
    cores = [COLORS["primary"], COLORS["secondary"]]
    for k, (serie, nome) in enumerate(zip(series, nomes)):
        desloc = 0.14 if k == 0 else -0.14
        rp, lo, hi = tabela[f"{serie}_rp"], tabela[f"{serie}_inf"], tabela[f"{serie}_sup"]
        ax.errorbar(rp, y + desloc, xerr=[rp - lo, hi - rp], fmt="o", color=cores[k], markersize=5, elinewidth=1.4, capsize=0, label=nome)
    ax.axvline(1, color=COLORS["ink"], linewidth=1)
    ax.set_xscale("log")
    ax.set_xticks([0.5, 0.75, 1, 1.5, 2, 3])
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: _virgula(f"{v:g}")))
    ax.xaxis.set_minor_locator(NullLocator())
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.set_yticks(y, tabela["rotulo"])
    ax.xaxis.grid(True)
    ax.set_axisbelow(True)
    ax.set_xlabel("Razão de prevalência (escala log; 1 = sem associação)")
    _titulo_com_legenda(ax, titulo, ncol=2)
    fig.tight_layout()
    return fig


def curva_concentracao(contagens, COLORS, titulo, unidade="células", evento="ocorrências",
                       xlabel="Células ocupadas (da mais à menos ativa)"):
    """Proporção acumulada de ocorrências pelas células ordenadas da mais à menos ativa."""
    ordenado = np.sort(np.asarray(contagens))[::-1]
    x = np.arange(1, len(ordenado) + 1) / len(ordenado)
    y = np.cumsum(ordenado) / ordenado.sum()
    fig, ax = plt.subplots(figsize=(5.6, 4.2))
    ax.plot(x, y, color=COLORS["primary"], linewidth=2, label="Observado")
    ax.plot([0, 1], [0, 1], color=COLORS["neutral"], linewidth=1, label="Distribuição uniforme")
    i50 = int(np.searchsorted(y, 0.5))
    ax.scatter([x[i50]], [y[i50]], color=COLORS["primary"], s=30, zorder=3)
    ax.annotate(_virgula(f"{x[i50] * 100:.1f}% das {unidade}\nconcentram 50% das {evento}"), xy=(x[i50], y[i50]), xytext=(12, -24), textcoords="offset points", fontsize=8, color=COLORS["ink"])
    _eixo_pct(ax.xaxis)
    _eixo_pct(ax.yaxis)
    ax.grid(True)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(f"{evento.capitalize()} acumuladas")
    ax.set_title(titulo)
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    return fig


def barras_horizontais(rotulos, valores, COLORS, titulo, formato="pct", destaque=None, xlabel=None):
    """Barras horizontais ordenadas com rótulo de valor; `destaque` recebe rótulos a colorir."""
    ordem = np.argsort(valores)
    rotulos, valores = np.asarray(rotulos)[ordem], np.asarray(valores)[ordem]
    # Sem destaque, a série é única e usa a cor principal; com destaque, o resto fica neutro.
    cores = [COLORS["primary"] if destaque is None or r in set(destaque) else COLORS["neutral"] for r in rotulos]
    fig, ax = plt.subplots(figsize=(8, 0.26 * len(rotulos) + 1.2))
    ax.barh(rotulos, valores, color=cores, height=0.65)
    for yi, v in enumerate(valores):
        texto = f"{v * 100:.0f}%" if formato == "pct" else f"{v:,.0f}".replace(",", ".")
        ax.annotate(texto, xy=(v, yi), xytext=(3, 0), textcoords="offset points", va="center", fontsize=7, color=COLORS["muted"])
    if formato == "pct":
        _eixo_pct(ax.xaxis)
        ax.set_xlim(0, 1.08)
    ax.tick_params(axis="y", labelsize=8)
    ax.xaxis.grid(True)
    ax.set_axisbelow(True)
    if xlabel:
        ax.set_xlabel(xlabel)
    ax.set_title(titulo)
    fig.tight_layout()
    return fig


def barras_pareadas(rotulos, valores_a, valores_b, nomes, COLORS, titulo):
    """Duas séries de proporções por categoria, em barras horizontais lado a lado."""
    fig, ax = plt.subplots(figsize=(8, 0.62 * len(rotulos) + 1.4))
    y = np.arange(len(rotulos))
    for valores, desloc, cor, nome in [(valores_a, 0.19, COLORS["primary"], nomes[0]), (valores_b, -0.19, COLORS["secondary"], nomes[1])]:
        ax.barh(y + desloc, valores, height=0.34, color=cor, label=nome)
        for yi, v in zip(y + desloc, valores):
            ax.annotate(_virgula(f"{v * 100:.1f}%"), xy=(v, yi), xytext=(3, 0), textcoords="offset points", va="center", fontsize=7, color=COLORS["muted"])
    ax.set_yticks(y, rotulos)
    _eixo_pct(ax.xaxis)
    ax.set_xlim(0, max(max(valores_a), max(valores_b)) * 1.12)
    ax.xaxis.grid(True)
    ax.set_axisbelow(True)
    _titulo_com_legenda(ax, titulo, ncol=2)
    fig.tight_layout()
    return fig


def dispersao_rotulada(x, y, rotulos, COLORS, titulo, xlabel, ylabel, n_rotulos=6):
    """Dispersão com rótulo apenas nos pontos mais extremos; rótulos próximos são deslocados."""
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    fig, ax = plt.subplots(figsize=(6.4, 4.6))
    ax.scatter(x, y, s=36, color=COLORS["primary"], alpha=0.85, edgecolor="white", linewidth=1)
    extremos = np.argsort(x / x.max() + y / y.max())[-n_rotulos:]
    colocados = []
    for i in sorted(extremos, key=lambda i: -y[i]):
        perto = any(abs(x[i] - xj) < 0.08 * x.max() and abs(y[i] - yj) < 0.06 * y.max() for xj, yj in colocados)
        ax.annotate(rotulos[i], xy=(x[i], y[i]), xytext=(5, -10 if perto else 3), textcoords="offset points", fontsize=7, color=COLORS["ink"])
        colocados.append((x[i], y[i]))
    ax.grid(True)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(titulo)
    fig.tight_layout()
    return fig


def linhas_comparadas(categorias, series, COLORS, titulo, ylabel, notas=None):
    """Duas ou três séries no mesmo eixo, com legenda e rótulo direto no último ponto.

    `notas` recebe {(serie, indice): texto} para anotar pontos específicos.
    """
    fig, ax = plt.subplots(figsize=(9, 3.9))
    cores = [COLORS["primary"], COLORS["secondary"], COLORS["tertiary"]]
    for (nome, valores), cor in zip(series.items(), cores):
        ax.plot(categorias, valores, marker="o", markersize=4, linewidth=2, color=cor, label=nome)
    # Rótulos finais afastados verticalmente quando as séries terminam no mesmo valor.
    finais = sorted(((v[-1], nome) for nome, v in series.items()), reverse=True)
    amplitude = np.ptp(np.concatenate([np.asarray(v) for v in series.values()]))
    for k, (v, nome) in enumerate(finais):
        perto = len(finais) > 1 and abs(finais[0][0] - finais[-1][0]) < 0.05 * amplitude
        desloc = (6 if k == 0 else -6) if perto else 0
        ax.annotate(nome, xy=(len(categorias) - 1, v), xytext=(6, desloc), textcoords="offset points", va="center", fontsize=8, color=COLORS["ink"])
    for (nome, i), texto in (notas or {}).items():
        ax.annotate(texto, xy=(i, series[nome][i]), xytext=(7, 0), textcoords="offset points", ha="left", va="center", fontsize=7, color=COLORS["muted"])
    ax.yaxis.grid(True)
    ax.set_axisbelow(True)
    ax.margins(y=0.15)
    ax.set_ylabel(ylabel)
    _titulo_com_legenda(ax, titulo, ncol=len(series))
    fig.tight_layout()
    return fig


def barras_ordenadas(rotulos, valores, COLORS, titulo, ylabel=None):
    """Proporções em barras verticais na ordem recebida (categorias ordinais, como faixas etárias)."""
    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.bar(rotulos, valores, color=COLORS["primary"], width=0.6)
    for i, v in enumerate(valores):
        ax.annotate(_rotulo_pct(v), xy=(i, v), xytext=(0, 3), textcoords="offset points", ha="center", fontsize=8, color=COLORS["muted"])
    _eixo_pct(ax.yaxis)
    ax.yaxis.grid(True)
    ax.set_axisbelow(True)
    if ylabel:
        ax.set_ylabel(ylabel)
    ax.set_title(titulo)
    fig.tight_layout()
    return fig
