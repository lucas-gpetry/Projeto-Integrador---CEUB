"""Taxas por habitante (Censo 2022) de ocorrências PMDF (2024) e feminicídios (PCDF) por RA.

Uso: python src/taxas_ra.py <raiz do projeto> <csv de saída>
Requer data/populacao_ra_censo2022.csv (IBGE, Censo 2022, agregado por RA pelo IPEDF).
"""
import sys
import numpy as np
import pandas as pd
from scipy import stats
from unidecode import unidecode

RAIZ = sys.argv[1]
OUT = sys.argv[2]

ALIAS = {  # mesmo agrupamento do relatório (RAs criadas em 2019 vão para a RA de origem)
    "BRASILIA": "PLANO PILOTO", "SUDOESTE/OCTOGONAL": "SUDOESTE", "SCIA/ESTRUTURAL": "SCIA",
    "SCIA E ESTRUTURAL": "SCIA", "SIA (SETOR DE INDUSTRIA E ABASTECIMENTO)": "SIA",
    "JARDIM BOTANICO A": "JARDIM BOTANICO", "JARDIM BOTANICO B": "JARDIM BOTANICO",
    "PARK WAY A": "PARK WAY", "PARK WAY B": "PARK WAY",
    "ARNIQUEIRAS": "AGUAS CLARAS", "ARNIQUEIRA": "AGUAS CLARAS",
    "POR DO SOL/SOL NASCENTE": "CEILANDIA", "SOL NASCENTE/POR DO SOL": "CEILANDIA",
}
norm = lambda s: ALIAS.get(unidecode(str(s)).strip().upper(), unidecode(str(s)).strip().upper())

pop = pd.read_csv(f"{RAIZ}/data/populacao_ra_censo2022.csv", sep=";")
pop = pop.assign(k=pop["ra"].map(norm)).groupby("k")["populacao_2022"].sum()
pmdf = pd.read_csv(f"{RAIZ}/data/base_analisada.csv", usecols=["cidade"])["cidade"].map(norm).value_counts()
fem = pd.read_csv(f"{RAIZ}/data/feminicidios_pcdf.csv", encoding="latin1", sep=";")
fem["ano"] = pd.to_datetime(fem["Data do Crime"], dayfirst=True, errors="coerce").dt.year
fem["k"] = fem["RA"].map(norm)
anos = fem["ano"].nunique()

t = pd.concat([pop.rename("pop"), pmdf.rename("pmdf"),
               fem["k"].value_counts().rename("fem"),
               fem.loc[fem["ano"].eq(2024), "k"].value_counts().rename("fem24")], axis=1).fillna(0)
sem_pop = t.index[t["pop"].eq(0)].tolist()
assert not sem_pop, f"RAs sem população: {sem_pop}"
assert t["pmdf"].sum() == 12123 and t["fem"].sum() == 230, (t["pmdf"].sum(), t["fem"].sum())

t["tx_pmdf"] = t["pmdf"] / t["pop"] * 1e4                       # ocorrências por 10 mil hab., 2024
t["tx_fem"] = t["fem"] / (t["pop"] * anos) * 1e5                # feminicídios por 100 mil hab./ano, 2015-2025
t["tx_fem24"] = t["fem24"] / t["pop"] * 1e5

# Suavização bayesiana empírica global (Marshall, 1991) para RAs pequenas
def eb(casos, expo):
    m = casos.sum() / expo.sum()
    r = casos / expo
    s2 = (expo * (r - m) ** 2).sum() / expo.sum()
    a = max(s2 - m / expo.mean(), 0)
    w = a / (a + m / expo)
    return w * r + (1 - w) * m
t["tx_fem_eb"] = eb(t["fem"], t["pop"] * anos) * 1e5
t["tx_fem24_eb"] = eb(t["fem24"], t["pop"]) * 1e5

def sp(a, b, mask=None):
    x = t if mask is None else t[mask]
    r = stats.spearmanr(x[a], x[b]); return round(r.statistic, 2), round(r.pvalue, 3), len(x)

res = {
    "n_ras": len(t), "anos_fem": anos, "taxa_fem_df": t["fem"].sum() / (t["pop"].sum() * anos) * 1e5,
    "taxa_pmdf_df": t["pmdf"].sum() / t["pop"].sum() * 1e4,
    "sp_contagens_acum": sp("pmdf", "fem"), "sp_contagens_24": sp("pmdf", "fem24"),
    "sp_pop_pmdf": sp("pop", "pmdf"), "sp_pop_fem": sp("pop", "fem"),
    "sp_taxas_acum": sp("tx_pmdf", "tx_fem"), "sp_taxas_acum_eb": sp("tx_pmdf", "tx_fem_eb"),
    "sp_taxas_24": sp("tx_pmdf", "tx_fem24"), "sp_taxas_24_eb": sp("tx_pmdf", "tx_fem24_eb"),
    "sp_taxas_acum_50k": sp("tx_pmdf", "tx_fem", t["pop"] >= 50000),
}

# Regressão de Poisson: fem ~ log(taxa PMDF), offset log(pop*anos); IRLS + dispersão (quasi-Poisson)
def poisson(y, x, off):
    X = np.column_stack([np.ones_like(x), x]); b = np.zeros(2); b[0] = np.log(y.sum() / np.exp(off).sum())
    for _ in range(50):
        mu = np.exp(X @ b + off); z = X @ b + (y - mu) / mu
        W = mu; b_new = np.linalg.solve(X.T @ (W[:, None] * X), X.T @ (W * z))
        if np.allclose(b_new, b, atol=1e-10): b = b_new; break
        b = b_new
    mu = np.exp(X @ b + off); phi = (((y - mu) ** 2) / mu).sum() / (len(y) - 2)
    cov = np.linalg.inv(X.T @ (mu[:, None] * X)) * max(phi, 1)
    se = np.sqrt(cov[1, 1]); z = b[1] / se
    return dict(beta=b[1], rr_dobro=2 ** b[1], ic=(2 ** (b[1] - 1.96 * se), 2 ** (b[1] + 1.96 * se)),
                p=2 * stats.norm.sf(abs(z)), phi=phi)
lx = np.log(t["tx_pmdf"].values)
res["poisson_acum"] = poisson(t["fem"].values.astype(float), lx, np.log(t["pop"].values * anos))
res["poisson_24"] = poisson(t["fem24"].values.astype(float), lx, np.log(t["pop"].values))

for k, v in res.items(): print(k, v)
cols = ["pop", "pmdf", "tx_pmdf", "fem", "tx_fem", "tx_fem_eb", "fem24", "tx_fem24"]
print(t[cols].sort_values("tx_fem_eb", ascending=False).round(2).to_string())
t[cols + ["tx_fem_eb", "tx_fem24_eb"]].to_csv(OUT, sep=";", decimal=",")
