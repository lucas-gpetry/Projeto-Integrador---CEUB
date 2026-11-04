"""Audita as flags textuais da PMDF e confere se as regras reproduzem a base analisada.

Entrada: data/base_analisada.csv
Saída: outputs/validacao_flags/ (só agregados; o diretório é ignorado pelo Git)

Nenhuma narrativa é gravada nem exibida. Executar a partir da raiz do projeto: python scripts/auditar_flags.py
"""

import sys
from pathlib import Path

import pandas as pd
import spacy
from tqdm import tqdm

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from src.utils import auditoria_flags as af  # noqa: E402
from src.utils.nlp_engines import normalizar_para_nlp  # noqa: E402


def main():
    saida = RAIZ / "outputs" / "validacao_flags"
    saida.mkdir(parents=True, exist_ok=True)
    colunas = ["historico", "historico_limpo", "desfecho", *af.FLAGS]
    base = pd.read_csv(RAIZ / "data" / "base_analisada.csv", usecols=colunas, low_memory=False)
    base["historico_limpo"] = base["historico_limpo"].fillna("")

    nlp = spacy.load("pt_core_news_sm", disable=["ner", "textcat"])
    textos_nlp = base["historico"].map(normalizar_para_nlp).tolist()
    registros = [
        af.analisar_documento(doc, limpo)
        for doc, limpo in zip(tqdm(nlp.pipe(textos_nlp, batch_size=500), total=len(base)), base["historico_limpo"])
    ]

    divergencias = {flag: int(sum(af.flag_positiva(r, flag) != bool(v) for r, v in zip(registros, base[flag]))) for flag in af.FLAGS}
    divergencias["desfecho"] = int(sum(af.desfecho(r) != v for r, v in zip(registros, base["desfecho"])))
    pd.Series(divergencias, name="divergencias").rename_axis("flag").reset_index().to_csv(saida / "reproducao.csv", index=False, encoding="utf-8-sig")

    termos = af.suprimir_contagens(af.resumir_termos(registros), ["historicos", "unico_sustento"])
    termos.to_csv(saida / "termos_por_flag.csv", index=False, encoding="utf-8-sig")
    candidatos = af.suprimir_contagens(af.candidatos_por_rotulo(registros), ["historicos_sem_flag"])
    candidatos.to_csv(saida / "candidatos_fora_da_flag.csv", index=False, encoding="utf-8-sig")
    faixas = af.faixas_por_flag(registros).merge(af.taxas_por_extensao(registros), on="flag")
    faixas.to_csv(saida / "faixas_por_flag.csv", index=False, encoding="utf-8-sig")
    af.cenarios_desfecho(registros).rename_axis("desfecho").reset_index().to_csv(saida / "cenarios_desfecho.csv", index=False, encoding="utf-8-sig")
    af.razoes_por_cenario(registros).to_csv(saida / "razoes_desfecho_por_cenario.csv", index=False, encoding="utf-8-sig")
    print(f"Auditoria concluída: {len(registros)} históricos; divergências: {sum(divergencias.values())}. Saída em {saida}")


if __name__ == "__main__":
    main()
