"""Gera a amostra do padrão-ouro e uma planilha de rotulagem por anotador.

Entrada: data/base_analisada.csv
Saída: outputs/padrao_ouro/ (ignorado pelo Git, porque as planilhas têm narrativas)

A saída no terminal traz só contagens. Executar a partir da raiz: python scripts/amostra_padrao_ouro.py
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from src.utils import padrao_ouro as po  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--total", type=int, default=300)
    parser.add_argument("--semente", type=int, default=po.SEMENTE)
    parser.add_argument("--sobrescrever", action="store_true", help="Apaga rótulos já preenchidos. Use só antes de começar a rotulagem.")
    args = parser.parse_args()

    saida = RAIZ / "outputs" / "padrao_ouro"
    if not po.saida_ignorada_pelo_git(saida.relative_to(RAIZ), RAIZ):
        raise SystemExit("A saída não está no .gitignore. Nada foi gravado.")
    if saida.exists() and any(saida.iterdir()) and not args.sobrescrever:
        raise SystemExit("A amostra já existe. Para não perder rótulos, nada foi alterado.")
    saida.mkdir(parents=True, exist_ok=True)

    colunas = ["historico", "desfecho", *po.FLAGS]
    base = pd.read_csv(RAIZ / "data" / "base_analisada.csv", usecols=colunas, low_memory=False)
    amostra = po.sortear_amostra(base[po.FLAGS].astype(bool), args.total, args.semente)
    amostra = po.distribuir_pares(amostra, semente=args.semente)
    gabarito = amostra.join(base[["desfecho", *po.FLAGS]], on="indice_base")
    gabarito.to_csv(saida / "gabarito_amostra.csv", index=False, encoding="utf-8-sig")

    for anotador in po.ANOTADORES:
        linhas = amostra[amostra["anotador_1"].eq(anotador) | amostra["anotador_2"].eq(anotador)]
        pares = [(r.id_amostra, base.at[r.indice_base, "historico"]) for r in linhas.itertuples()]
        po.gravar_planilha_anotador(saida / f"anotador_{anotador}.xlsx", pares)
        print(f"Anotador {anotador}: {len(pares)} históricos")

    resumo = pd.DataFrame({
        "base": po.atribuir_estratos(base[po.FLAGS].astype(bool)).value_counts(),
        "amostra": amostra["estrato"].value_counts(),
    }).sort_values("base")
    print(resumo.to_string())
    print("Positivos previstos na amostra, por flag:")
    print(gabarito[po.FLAGS].astype(bool).sum().to_string())


if __name__ == "__main__":
    main()
