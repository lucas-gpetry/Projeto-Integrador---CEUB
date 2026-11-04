"""Associações entre formas de violência e fatores agravantes, na PMDF e no SINAN.

Estende as associações pontuais do relatório (relatorio_final.qmd) a todas as combinações
fator × forma de violência de cada fonte. Para cada par: coeficiente phi, razão de
prevalência bruta e ajustada (Mantel-Haenszel) e p-valor corrigido por Benjamini-Hochberg
dentro da matriz. O ajuste segue o confundidor principal de cada fonte: tamanho do
histórico na PMDF (decis de palavras) e faixa etária no SINAN.

As duas fontes só se encontram no nível das estimativas: nenhum registro é cruzado.

Uso, a partir da raiz do projeto:
    python src/agravantes.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import sinan_eda as se  # noqa: E402
from src.sinan_pipeline import NO, SINAN_RAW_PATH, YES  # noqa: E402
from src.utils import report_stats as rs  # noqa: E402

PMDF_PATH = ROOT / "data" / "base_analisada.csv"
OUTPUT_DIR = ROOT / "outputs" / "agravantes"
ANO = 2024

VIOLENCIAS_PMDF = {
    "v_fisica": "Física", "v_psicologica": "Psicológica", "v_patrimonial": "Patrimonial",
    "v_moral": "Moral", "v_sexual": "Sexual",
}
AGRAVANTES_PMDF = {
    "flag_alcool": "Álcool", "flag_drogas": "Drogas", "flag_arma_fogo": "Arma de fogo",
    "flag_arma_branca": "Arma branca", "flag_separacao": "Separação ou ex-parceiro",
    "flag_medida_protetiva": "Medida protetiva (menção)", "flag_filhos": "Filhos",
    "flag_tornozeleira": "Tornozeleira eletrônica",
}
VIOLENCIAS_SINAN = {
    "VIOL_FISIC": "Física", "VIOL_PSICO": "Psicológica/moral", "VIOL_FINAN": "Financeira", "VIOL_SEXU": "Sexual",
}
# Arma de fogo e perfurocortante são meios de agressão da ficha; ex-parceiro reúne ex-cônjuge e
# ex-namorado(a), o equivalente estruturado da flag de separação da PMDF.
AGRAVANTES_SINAN = {
    "AUTOR_ALCO": "Álcool", "AG_FOGO": "Arma de fogo", "AG_CORTE": "Perfurocortante",
    "ex_parceiro": "Ex-parceiro", "OUT_VEZES": "Violência de repetição", "DEF_TRANS": "Deficiência/transtorno",
}

# Pares medidos nas duas fontes. Na PMDF, psicológica e moral são unidas porque o SINAN as
# registra num só campo; a patrimonial corresponde à financeira/econômica.
COMPARAVEIS = [
    ("Álcool", "Física", "Álcool", "Física"),
    ("Álcool", "Psicológica ou moral", "Álcool", "Psicológica/moral"),
    ("Álcool", "Patrimonial", "Álcool", "Financeira"),
    ("Arma de fogo", "Física", "Arma de fogo", "Física"),
    ("Arma de fogo", "Psicológica ou moral", "Arma de fogo", "Psicológica/moral"),
    ("Arma branca", "Física", "Perfurocortante", "Física"),
    ("Arma branca", "Psicológica ou moral", "Perfurocortante", "Psicológica/moral"),
    ("Separação ou ex-parceiro", "Física", "Ex-parceiro", "Física"),
    ("Separação ou ex-parceiro", "Psicológica ou moral", "Ex-parceiro", "Psicológica/moral"),
    ("Separação ou ex-parceiro", "Patrimonial", "Ex-parceiro", "Financeira"),
]


def flags_pmdf(df: pd.DataFrame) -> pd.DataFrame:
    """Flags da PMDF com rótulos de exibição e o estrato de tamanho do histórico."""
    palavras = df["historico_limpo"].fillna("").str.split().str.len()
    base = df[[*VIOLENCIAS_PMDF, *AGRAVANTES_PMDF]].astype(bool).rename(columns={**VIOLENCIAS_PMDF, **AGRAVANTES_PMDF})
    base["Psicológica ou moral"] = base["Psicológica"] | base["Moral"]
    base["decil_palavras"] = pd.qcut(palavras, 10, labels=False, duplicates="drop")
    return base


def _flag(serie: pd.Series) -> pd.Series:
    """Sim/não da ficha SINAN como booleano; ignorado e vazio viram NaN."""
    return serie.map({YES: True, NO: False})


def flags_sinan(df: pd.DataFrame) -> pd.DataFrame:
    """Formas de violência e agravantes do SINAN como booleanos com NaN para resposta inválida."""
    base = pd.DataFrame({rotulo: _flag(df[col]) for col, rotulo in {**VIOLENCIAS_SINAN, **AGRAVANTES_SINAN}.items()
                         if col in df}, index=df.index)
    ex = df[["REL_EXCON", "REL_EXNAM"]]
    # Sim em qualquer um basta; "não" exige resposta válida nos dois campos.
    base["Ex-parceiro"] = np.where(ex.eq(YES).any(axis=1), 1.0, np.where(ex.isin([YES, NO]).all(axis=1), 0.0, np.nan))
    base["faixa_etaria"] = df["faixa_etaria"].astype(object)
    return base


def matriz_pmdf(base: pd.DataFrame) -> pd.DataFrame:
    return rs.matriz_associacoes(base, list(AGRAVANTES_PMDF.values()), list(VIOLENCIAS_PMDF.values()), "decil_palavras")


def matriz_sinan(base: pd.DataFrame) -> pd.DataFrame:
    agravantes = [r for r in AGRAVANTES_SINAN.values() if r in base]
    return rs.matriz_associacoes(base, agravantes, [r for r in VIOLENCIAS_SINAN.values() if r in base], "faixa_etaria")


def comparar_fontes(pmdf: pd.DataFrame, sinan: pd.DataFrame) -> pd.DataFrame:
    """RP ajustadas dos pares medidos nas duas fontes, lado a lado, e se apontam a mesma direção.

    `pmdf` deve conter as linhas de 'Psicológica ou moral'; `sinan` é a matriz de um recorte SINAN.
    """
    ip = pmdf.set_index(["exposicao", "desfecho"])
    isn = sinan.set_index(["exposicao", "desfecho"])
    linhas = []
    for exp_p, out_p, exp_s, out_s in COMPARAVEIS:
        if (exp_p, out_p) not in ip.index or (exp_s, out_s) not in isn.index:
            continue
        p, s = ip.loc[(exp_p, out_p)], isn.loc[(exp_s, out_s)]
        razao = lambda r: {"rp": r["ajustada_rp"], "ic_inf": r["ajustada_inf"], "ic_sup": r["ajustada_sup"]}  # noqa: E731
        dif = rs.diferenca_razoes(razao(p), razao(s))
        linhas.append({
            "fator_pmdf": exp_p, "violencia_pmdf": out_p, "fator_sinan": exp_s, "violencia_sinan": out_s,
            **{f"pmdf_{k}": p[k] for k in ["ajustada_rp", "ajustada_inf", "ajustada_sup", "p_bh"]},
            **{f"sinan_{k}": s[k] for k in ["ajustada_rp", "ajustada_inf", "ajustada_sup", "p_bh", "n_validos"]},
            "razao_pmdf_sinan": dif["rp"], "p_diferenca": dif["p"],
        })
    t = pd.DataFrame(linhas)
    # Direção pelo p corrigido de cada matriz: "+" e "−" só quando a associação sobrevive ao BH.
    direcao = lambda rp, p: np.select([(p < 0.05) & (rp > 1), (p < 0.05) & (rp < 1), rp.isna()], ["+", "−", "n.d."], default="0")  # noqa: E731
    t["direcao_pmdf"] = direcao(t["pmdf_ajustada_rp"], t["pmdf_p_bh"])
    t["direcao_sinan"] = direcao(t["sinan_ajustada_rp"], t["sinan_p_bh"])
    t["p_diferenca_bh"] = rs.benjamini_hochberg(t["p_diferenca"])
    return t


def calcular(df_pmdf: pd.DataFrame, sinan_ano: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Todas as matrizes e a comparação entre fontes.

    `df_pmdf` é a base_analisada; `sinan_ano`, a coorte SINAN do ano já preparada por
    `sinan_eda.preparar_coorte` (com `faixa_etaria` e `recorte_domestico`).
    """
    pmdf = flags_pmdf(df_pmdf)
    sinan, sinan_dom = flags_sinan(sinan_ano), flags_sinan(sinan_ano[sinan_ano["recorte_domestico"]])
    m_pmdf = matriz_pmdf(pmdf)
    # Família separada: a coluna unida só existe para a comparação e não entra na correção da matriz principal.
    m_pmdf_psi_moral = rs.matriz_associacoes(pmdf, list(AGRAVANTES_PMDF.values()), ["Psicológica ou moral"], "decil_palavras")
    m_sinan, m_sinan_dom = matriz_sinan(sinan), matriz_sinan(sinan_dom)
    pmdf_comparavel = pd.concat([m_pmdf, m_pmdf_psi_moral])
    return {
        "matriz_pmdf": m_pmdf,
        "matriz_sinan": m_sinan,
        "matriz_sinan_domestico": m_sinan_dom,
        "comparacao_fontes": comparar_fontes(pmdf_comparavel, m_sinan_dom),
        "comparacao_fontes_sinan_total": comparar_fontes(pmdf_comparavel, m_sinan),
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _, _, coorte = se.preparar_coorte(SINAN_RAW_PATH, "coorte_pmdf_primaria")
    resultados = calcular(pd.read_csv(PMDF_PATH, low_memory=False), coorte[coorte["ano_analitico"].eq(ANO)])
    for nome, tabela in resultados.items():
        tabela.to_csv(OUTPUT_DIR / f"{nome}_{ANO}.csv", index=False, encoding="utf-8-sig")
    print(f"Associações geradas em: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
