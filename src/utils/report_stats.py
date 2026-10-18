"""Estatísticas do relatório analítico.

Funções puras sobre DataFrames/Series: o relatório só formata o que sai daqui,
de modo que todo número citado no texto é recalculado a cada renderização.
"""

import re
from datetime import date

import numpy as np
import pandas as pd
from scipy import stats

DIAS_SEMANA = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]
MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

# Feriados nacionais e distritais de 2024 (Lei nº 14.759/2023 incluiu o 20 de novembro;
# 30 de novembro é o Dia do Evangélico no DF) e pontos facultativos de Carnaval e Corpus Christi.
FERIADOS_2024 = {
    date(2024, 1, 1): "Confraternização Universal",
    date(2024, 2, 12): "Carnaval",
    date(2024, 2, 13): "Carnaval",
    date(2024, 3, 29): "Paixão de Cristo",
    date(2024, 4, 21): "Tiradentes / Aniversário de Brasília",
    date(2024, 5, 1): "Dia do Trabalho",
    date(2024, 5, 30): "Corpus Christi",
    date(2024, 9, 7): "Independência",
    date(2024, 10, 12): "Nossa Senhora Aparecida",
    date(2024, 11, 2): "Finados",
    date(2024, 11, 15): "Proclamação da República",
    date(2024, 11, 20): "Consciência Negra",
    date(2024, 11, 30): "Dia do Evangélico (DF)",
    date(2024, 12, 25): "Natal",
}
# Datas comemorativas sem feriado, citadas com frequência como de maior risco.
DATAS_COMEMORATIVAS_2024 = {
    date(2024, 5, 12): "Dia das Mães",
    date(2024, 6, 12): "Dia dos Namorados",
    date(2024, 12, 24): "Véspera de Natal",
    date(2024, 12, 31): "Véspera de Ano-Novo",
}

# Grafia das RAs para exibição: as bases trazem os nomes em caixa alta e, na PMDF, sem acento.
_GRAFIA_RA = {
    "AGUAS": "Águas", "BOTANICO": "Botânico", "BRASILIA": "Brasília", "BRAZLANDIA": "Brazlândia",
    "CANDANGOLANDIA": "Candangolândia", "CEILANDIA": "Ceilândia", "GUARA": "Guará", "INDUSTRIA": "Indústria",
    "ITAPOA": "Itapoã", "NUCLEO": "Núcleo", "PARANOA": "Paranoá", "POR": "Pôr", "SAO": "São",
    "SEBASTIAO": "Sebastião", "VARJAO": "Varjão",
}
_PARTICULAS = {"DA", "DAS", "DE", "DO", "DOS", "E"}
_SIGLAS = {"II", "SCIA", "SIA"}
_NUMERO_FORMATADO = r"[−-]?[\d.,]+%?(?: \(.+\))?"


def wilson_ci(k, n, z=1.96):
    """Intervalo de Wilson para uma proporção; devolve (p, inferior, superior)."""
    if n == 0:
        return np.nan, np.nan, np.nan
    p = k / n
    centro = (p + z**2 / (2 * n)) / (1 + z**2 / n)
    meia = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / (1 + z**2 / n)
    return p, centro - meia, centro + meia


def prevalencia(df, coluna):
    """Proporção de registros com a flag, com IC de Wilson."""
    k = int(df[coluna].sum())
    p, lo, hi = wilson_ci(k, len(df))
    return {"n": k, "total": len(df), "p": p, "ic_inf": lo, "ic_sup": hi}


def razao_prevalencia(df, exposicao, desfecho, z=1.96):
    """Razão de prevalência do desfecho entre expostos e não expostos (IC pelo método log)."""
    exp = df[exposicao].astype(bool)
    out = df[desfecho].astype(bool)
    a, n1 = int((exp & out).sum()), int(exp.sum())
    c, n0 = int((~exp & out).sum()), int((~exp).sum())
    if min(a, c, n1, n0) == 0:
        return {"rp": np.nan, "ic_inf": np.nan, "ic_sup": np.nan, "p_expostos": np.nan, "p_nao_expostos": np.nan, "a": a, "c": c}
    rp = (a / n1) / (c / n0)
    ep = np.sqrt(1 / a - 1 / n1 + 1 / c - 1 / n0)
    return {
        "rp": rp,
        "ic_inf": np.exp(np.log(rp) - z * ep),
        "ic_sup": np.exp(np.log(rp) + z * ep),
        "p_expostos": a / n1,
        "p_nao_expostos": c / n0,
        "a": a,
        "c": c,
    }


def razao_prevalencia_mh(df, exposicao, desfecho, estrato, z=1.96):
    """Razão de prevalência de Mantel-Haenszel ajustada por estrato (variância de Greenland-Robins).

    Usada para controlar o tamanho do histórico: narrativas longas citam mais termos, e um
    fator que alonga o relato (como o álcool) parece associado a qualquer outra flag.
    """
    num = den = var = 0.0
    for _, g in df.groupby(estrato, observed=True):
        exp, out = g[exposicao].astype(bool), g[desfecho].astype(bool)
        a, c = float((exp & out).sum()), float((~exp & out).sum())
        n1, n0 = float(exp.sum()), float((~exp).sum())
        n = n1 + n0
        if n1 == 0 or n0 == 0:
            continue
        num += a * n0 / n
        den += c * n1 / n
        var += (n1 * n0 * (a + c) - a * c * n) / n**2
    if num == 0 or den == 0:
        return {"rp": np.nan, "ic_inf": np.nan, "ic_sup": np.nan}
    rp = num / den
    ep = np.sqrt(var / (num * den))
    return {"rp": rp, "ic_inf": rp * np.exp(-z * ep), "ic_sup": rp * np.exp(z * ep)}


def lacunas_de_registro(datas_registro, minimo_dias=2):
    """Intervalos de dias consecutivos sem nenhum registro (indício de falha de sistema ou extração)."""
    dias = pd.to_datetime(datas_registro).dt.normalize()
    todos = pd.date_range(dias.min(), dias.max(), freq="D")
    vazios = todos.difference(pd.DatetimeIndex(dias.unique()))
    if len(vazios) == 0:
        return []
    grupos = (pd.Series(vazios).diff() != pd.Timedelta(days=1)).cumsum()
    return [
        (g.iloc[0].date(), g.iloc[-1].date(), len(g))
        for _, g in pd.Series(vazios).groupby(grupos.values)
        if len(g) >= minimo_dias
    ]


def dias_no_periodo(inicio, fim, chave):
    """Quantos dias de cada categoria do calendário ('dia_semana' ou 'mes') existem no período."""
    dias = pd.date_range(inicio, fim, freq="D")
    rotulo = dias.weekday if chave == "dia_semana" else dias.month - 1
    return pd.Series(1, index=rotulo).groupby(level=0).sum()


def distribuicao_calendario(datas, chave):
    """Contagem observada por categoria, esperada sob taxa diária constante e teste qui-quadrado.

    A esperada é proporcional ao número de dias de cada categoria no período: 2024 tem
    53 segundas e terças e meses de 29 a 31 dias, o que muda o esperado de cada barra.
    """
    datas = pd.to_datetime(datas)
    rotulo = datas.dt.weekday if chave == "dia_semana" else datas.dt.month - 1
    nomes = DIAS_SEMANA if chave == "dia_semana" else MESES
    dias = dias_no_periodo(datas.min().normalize(), datas.max().normalize(), chave)
    obs = rotulo.value_counts().reindex(dias.index, fill_value=0)
    esperado = dias / dias.sum() * obs.sum()
    qui2, p = stats.chisquare(obs.values, esperado.values)
    tabela = pd.DataFrame({
        "categoria": [nomes[i] for i in dias.index],
        "dias": dias.values,
        "observado": obs.values,
        "esperado": esperado.values,
        "media_diaria": obs.values / dias.values,
    })
    tabela["razao_obs_esp"] = tabela["observado"] / tabela["esperado"]
    return tabela, {"qui2": qui2, "gl": len(obs) - 1, "p": p}


def efeito_datas(datas, datas_especiais, janela_semanas=4, dias_excluidos=()):
    """Compara cada data especial com a média do mesmo dia da semana nas semanas vizinhas.

    O esperado de uma data é a média diária das ocorrências no mesmo dia da semana, até
    `janela_semanas` antes e depois, excluídas as próprias datas especiais e os
    `dias_excluidos` (por exemplo, um período de falha de registro). Datas especiais que
    caem em dia excluído ficam na tabela, marcadas, mas fora do total. O IC da razão usa o
    intervalo exato de Poisson para o total observado.
    """
    datas = pd.to_datetime(datas).dt.normalize()
    diario = datas.value_counts().sort_index()
    todos = pd.date_range(diario.index.min(), diario.index.max(), freq="D")
    diario = diario.reindex(todos, fill_value=0)
    especiais = {pd.Timestamp(d) for d in datas_especiais}
    excluidos = {pd.Timestamp(d) for d in dias_excluidos}
    linhas = []
    for d, nome in datas_especiais.items():
        d = pd.Timestamp(d)
        vizinhos = [d + pd.Timedelta(weeks=k) for k in range(-janela_semanas, janela_semanas + 1) if k != 0]
        vizinhos = [v for v in vizinhos if v in diario.index and v not in especiais and v not in excluidos]
        linhas.append({"data": d.date(), "nome": nome, "observado": int(diario.get(d, 0)),
                       "esperado": diario[vizinhos].mean(), "excluida": d in excluidos})
    tabela = pd.DataFrame(linhas)
    validas = tabela[~tabela["excluida"]]
    obs, esp = validas["observado"].sum(), validas["esperado"].sum()
    lo = stats.chi2.ppf(0.025, 2 * obs) / 2 if obs > 0 else 0.0
    hi = stats.chi2.ppf(0.975, 2 * (obs + 1)) / 2
    return tabela, {"observado": int(obs), "esperado": esp, "razao": obs / esp, "ic_inf": lo / esp, "ic_sup": hi / esp}


def independencia(df, categoria, flag):
    """Qui-quadrado de independência entre uma categoria e uma flag binária."""
    tabela = pd.crosstab(df[categoria], df[flag].astype(bool))
    qui2, p, gl, _ = stats.chi2_contingency(tabela)
    n = tabela.values.sum()
    v_cramer = np.sqrt(qui2 / (n * (min(tabela.shape) - 1)))
    return {"qui2": qui2, "gl": gl, "p": p, "v_cramer": v_cramer}


def coocorrencia(df, colunas):
    """Matriz de registros com ambas as flags e número de flags ativas por registro."""
    m = df[colunas].astype(int)
    pares = m.T @ m
    return pares, m.sum(axis=1).value_counts().sort_index()


def concentracao(contagens, fracoes=(0.01, 0.05, 0.10, 0.20)):
    """Participação das unidades mais ativas no total (curva de concentração)."""
    ordenado = np.sort(np.asarray(contagens))[::-1]
    total = ordenado.sum()
    acumulado = np.cumsum(ordenado) / total
    resultado = {f: acumulado[max(int(np.ceil(f * len(ordenado))) - 1, 0)] for f in fracoes}
    metade = int(np.searchsorted(acumulado, 0.5) + 1)
    return resultado, {"unidades": len(ordenado), "unidades_para_50pct": metade, "gini": gini(ordenado)}


def gini(valores):
    """Coeficiente de Gini de valores não negativos."""
    x = np.sort(np.asarray(valores, dtype=float))
    n = len(x)
    if n == 0 or x.sum() == 0:
        return np.nan
    return (2 * np.sum(np.arange(1, n + 1) * x) / (n * x.sum())) - (n + 1) / n


def intervalos_entre_chamados(df, chave, coluna_data):
    """Dias entre chamados consecutivos de uma mesma chave de endereço."""
    ordenado = df[[chave, coluna_data]].dropna().sort_values([chave, coluna_data])
    delta = ordenado.groupby(chave)[coluna_data].diff().dt.total_seconds() / 86400
    return delta.dropna()


def razao_taxas(eventos1, tempo1, eventos0, tempo0, z=1.96):
    """Razão de taxas de Poisson (por exemplo, ocorrências por dia em dois conjuntos de dias)."""
    rr = (eventos1 / tempo1) / (eventos0 / tempo0)
    ep = np.sqrt(1 / eventos1 + 1 / eventos0)
    return {"rr": rr, "ic_inf": rr * np.exp(-z * ep), "ic_sup": rr * np.exp(z * ep)}


def nome_ra(nome):
    """Nome de RA para exibição: 'RECANTO DAS EMAS' -> 'Recanto das Emas'; 'CEILANDIA' -> 'Ceilândia'."""
    def palavra(m):
        p = m.group(0)
        if p in _SIGLAS:
            return p
        if p in _PARTICULAS and m.start() > 0:
            return p.lower()
        return _GRAFIA_RA.get(p, p.capitalize())
    return re.sub(r"[^\W\d_]+", palavra, str(nome).strip().upper())


def tabela_markdown(df):
    """Tabela pipe em markdown; renderiza igual em HTML e PDF, sem depender do Styler.

    Colunas numéricas, inclusive as já formatadas como texto ("12.123", "40,3%", "1,39 (1,32–1,46)"),
    alinham à direita; as demais, à esquerda.
    """
    def numerica(coluna):
        if pd.api.types.is_numeric_dtype(coluna):
            return True
        return coluna.astype(str).str.fullmatch(_NUMERO_FORMATADO).all()

    # O número de traços define a largura relativa de cada coluna quando o pandoc quebra linhas.
    # Textos longos são limitados para não esmagar as colunas numéricas; a folga de 2 evita cabeçalhos colados.
    larguras = [min(max(len(str(c)), *(len(str(v)) for v in df[c])), 30) + 2 for c in df.columns]
    cab = "| " + " | ".join(map(str, df.columns)) + " |"
    sep = "|" + "|".join("-" * (w - 1) + ":" if numerica(df[c]) else ":" + "-" * (w - 1)
                         for c, w in zip(df.columns, larguras)) + "|"
    linhas = ["| " + " | ".join(map(str, r)) + " |" for r in df.itertuples(index=False)]
    return "\n".join([cab, sep, *linhas])


def formatar_pct(p, casas=1):
    """Percentual no padrão brasileiro: 0,4033 -> '40,3%' (sinal de menos tipográfico)."""
    return f"{p * 100:.{casas}f}%".replace(".", ",").replace("-", "−")


def formatar_num(x, casas=0):
    """Número no padrão brasileiro: 12123 -> '12.123'; 1,5 -> '1,5'."""
    texto = f"{x:,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".").replace("-", "−")
