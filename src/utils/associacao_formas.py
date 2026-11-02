"""Associação entre categorias (idade, vínculo, local, desfecho) e formas de violência.

Funções puras sobre DataFrames: o relatório só formata o que sai daqui. As formas se
sobrepõem (um registro pode ter várias), então cada uma é testada como variável binária
própria. Flags textuais da PMDF são booleanas, e falso significa "não identificado"; campos
do SINAN são códigos, e o denominador são as respostas válidas (1 = sim, 2 = não).
"""

import numpy as np
import pandas as pd
from scipy import stats
from unidecode import unidecode

from . import report_stats as rs

SIM, NAO = "1", "2"


def respostas_validas(df, flag):
    """Registros com resposta válida na flag, com o valor booleano na coluna `_sim`."""
    if pd.api.types.is_bool_dtype(df[flag]):
        return df.assign(_sim=df[flag])
    validas = df[df[flag].isin([SIM, NAO])]
    return validas.assign(_sim=validas[flag].eq(SIM))


def associacao(df, categoria, flag):
    """Qui-quadrado e V de Cramér de categoria × flag, com o menor esperado para checar o teste."""
    v = respostas_validas(df, flag).dropna(subset=[categoria])
    esperado = stats.contingency.expected_freq(pd.crosstab(v[categoria], v["_sim"]))
    return {
        "n": len(v), "casos": int(v["_sim"].sum()), **rs.independencia(v, categoria, "_sim"),
        "esperado_min": esperado.min(), "pct_esperado_menor_5": (esperado < 5).mean(),
    }


def spearman(df, variavel, flag):
    """Correlação de postos entre uma variável ordinal e a flag; não capta relação em U."""
    v = respostas_validas(df, flag).dropna(subset=[variavel])
    r = stats.spearmanr(v[variavel], v["_sim"])
    return {"rho": r.statistic, "p_rho": r.pvalue}


def razoes(df, exposicao, flag, estrato, k=1):
    """Razão de prevalência da flag entre expostos e não expostos, bruta e ajustada por estrato.

    O intervalo de confiança permite recuperar as contagens da tabela 2×2; por isso a razão
    fica vazia quando alguma delas é menor que k.
    """
    v = respostas_validas(df, flag).dropna(subset=[estrato])
    b = rs.razao_prevalencia(v, exposicao, "_sim")
    a = rs.razao_prevalencia_mh(v, exposicao, "_sim", estrato)
    expostos = v[exposicao].astype(bool)
    if min(b["a"], b["c"], int(expostos.sum()) - b["a"], int((~expostos).sum()) - b["c"]) < k:
        b = a = {"rp": np.nan, "ic_inf": np.nan, "ic_sup": np.nan}
    return {
        "bruta_rp": b["rp"], "bruta_inf": b["ic_inf"], "bruta_sup": b["ic_sup"],
        "ajustada_rp": a["rp"], "ajustada_inf": a["ic_inf"], "ajustada_sup": a["ic_sup"],
    }


def tabela_associacoes(df, categoria, flags, exposicao=None, estrato=None, variavel=None, k=1):
    """Uma linha por forma: V de Cramér e, quando pedidos, Spearman e razões de prevalência."""
    linhas = []
    for coluna, rotulo in flags.items():
        linha = {"rotulo": rotulo, "coluna": coluna, **associacao(df, categoria, coluna)}
        if variavel is not None:
            linha.update(spearman(df, variavel, coluna))
        if exposicao is not None:
            linha.update(razoes(df, exposicao, coluna, estrato, k))
        linhas.append(linha)
    return pd.DataFrame(linhas)


def ajustar_familia(tabelas, ajuste):
    """Ajusta todos os p-valores das tabelas como uma só família de testes (colunas p_bh e p_rho_bh)."""
    pilha = pd.concat({
        nome: t.set_index("coluna").reindex(columns=["p", "p_rho"]).stack().dropna() for nome, t in tabelas.items()
    })
    ajustados = ajuste(pilha)
    saida = {}
    for nome, t in tabelas.items():
        t = t.copy()
        for origem, destino in [("p", "p_bh"), ("p_rho", "p_rho_bh")]:
            if origem in t:
                t[destino] = [ajustados.get((nome, c, origem), np.nan) for c in t["coluna"]]
        saida[nome] = t
    return saida


def _suprimir(casos, n, k):
    """Máscara de células a ocultar: contagem ou complemento entre 1 e k−1, ou base menor que k.

    Com uma só célula oculta na linha, a segunda menor também sai: do contrário, a primeira
    seria recuperável pela diferença com o total da forma.
    """
    resto = n - casos
    oculta = casos.between(1, k - 1) | resto.between(1, k - 1) | n.lt(k)
    if oculta.sum() == 1:
        oculta.loc[casos.where(~oculta).idxmin()] = True
    return oculta


def percentuais(df, categoria, flags, k):
    """% de cada forma por categoria, com IC de Wilson; p fica vazio nas células suprimidas."""
    blocos = []
    for coluna, rotulo in flags.items():
        v = respostas_validas(df, coluna).dropna(subset=[categoria])
        grupos = v.groupby(categoria, observed=True)["_sim"]
        casos, n = grupos.sum().astype(int), grupos.size()
        oculta = _suprimir(casos, n, k)
        ic = [rs.wilson_ci(c, t) for c, t in zip(casos, n)]
        bloco = pd.DataFrame({
            "rotulo": rotulo, "coluna": coluna, "categoria": casos.index.astype(str), "n": n.values,
            "casos": casos.values, "p": [i[0] for i in ic], "ic_inf": [i[1] for i in ic], "ic_sup": [i[2] for i in ic],
            "suprimido": oculta.values,
        })
        bloco.loc[bloco["suprimido"], ["casos", "p", "ic_inf", "ic_sup"]] = np.nan
        blocos.append(bloco)
    return pd.concat(blocos, ignore_index=True)


def composicao_fontes(pmdf, bases_sinan, indicadores, k):
    """Proporção de cada indicador na PMDF e em cada recorte do SINAN, sem arredondamento prévio.

    `indicadores` são tuplas (rótulo, flags da PMDF, coluna do SINAN); mais de uma flag equivale
    a "qualquer uma delas". Na PMDF o denominador são as ocorrências; no SINAN, as respostas válidas.
    """
    linhas = []
    for rotulo, flags_pmdf, coluna in indicadores:
        linha = {"rotulo": rotulo, "pmdf_casos": int(pmdf[flags_pmdf].any(axis=1).sum()), "pmdf_n": len(pmdf)}
        for nome, base in bases_sinan.items():
            v = respostas_validas(base, coluna)
            linha |= {f"{nome}_casos": int(v["_sim"].sum()), f"{nome}_n": len(v), f"{nome}_ignorado": len(base) - len(v)}
        linhas.append(linha)
    t = pd.DataFrame(linhas)
    for nome in ["pmdf", *bases_sinan]:
        t[f"{nome}_p"] = t[f"{nome}_casos"] / t[f"{nome}_n"]
        t.loc[t[f"{nome}_casos"].between(1, k - 1), [f"{nome}_casos", f"{nome}_p"]] = np.nan
    return t


def narrativa_improcedente(textos, termos):
    """Mesmo teste das regras de PLN: narrativas com esses termos ficam sem nenhuma forma de violência."""
    return textos.fillna("").map(lambda s: any(t in unidecode(s.lower()) for t in termos))
