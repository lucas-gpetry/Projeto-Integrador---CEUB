"""Calcula precisão, recall, F1 e kappa a partir das planilhas preenchidas pelo grupo.

Entrada: outputs/padrao_ouro/ (planilhas dos anotadores e, se houver, adjudicacao.xlsx)
Saída: no mesmo diretório. Enquanto houver divergências sem decisão, grava adjudicacao.xlsx e para.

Executar a partir da raiz: python scripts/avaliar_padrao_ouro.py
"""

import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from src.utils import padrao_ouro as po  # noqa: E402


def main():
    pasta = RAIZ / "outputs" / "padrao_ouro"
    gabarito = pd.read_csv(pasta / "gabarito_amostra.csv", encoding="utf-8-sig")
    longo = pd.concat([po.ler_planilha_anotador(pasta / f"anotador_{a}.xlsx", a) for a in po.ANOTADORES], ignore_index=True)

    em_branco = po.conferir_preenchimento(longo)
    if em_branco.sum():
        print("Células em branco por anotador:")
        print(em_branco.to_string())
        raise SystemExit("Termine a rotulagem antes de calcular as métricas.")

    caminho_adj = pasta / "adjudicacao.xlsx"
    adjudicacao = po.ler_adjudicacao(caminho_adj) if caminho_adj.exists() else None
    ouro, pendencias = po.consolidar(longo, adjudicacao)
    po.concordancia(longo).to_csv(pasta / "concordancia.csv", index=False, encoding="utf-8-sig")
    if not pendencias.empty:
        base = pd.read_csv(RAIZ / "data" / "base_analisada.csv", usecols=["historico"], low_memory=False)
        narrativas = {r.id_amostra: base.at[r.indice_base, "historico"] for r in gabarito.itertuples()}
        po.gravar_adjudicacao(caminho_adj, pendencias, narrativas)
        raise SystemExit(f"{len(pendencias)} divergências para decidir em {caminho_adj.name}. Preencha rotulo_final e rode de novo.")

    metricas = po.avaliar_flags(gabarito, ouro).merge(po.concordancia(longo), left_on="flag", right_on="coluna", how="left").drop(columns="coluna")
    metricas.to_csv(pasta / "metricas_flags.csv", index=False, encoding="utf-8-sig")
    po.matriz_desfecho(gabarito, ouro).to_csv(pasta / "matriz_desfecho.csv", encoding="utf-8-sig")
    colunas = ["flag", "prevalencia_regra", "prevalencia_ouro", "precisao", "recall", "f1", "kappa"]
    print(metricas[colunas].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
