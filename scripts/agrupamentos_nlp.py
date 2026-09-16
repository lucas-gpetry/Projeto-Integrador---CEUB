"""Gera agrupamentos e planilhas das categorias extraídas pelo NLP.

Entrada: data/base_analisada.csv
Saída padrão: outputs/agrupamentos_nlp/

Os arquivos são artefatos locais de validação. A base contém dados sensíveis e
o diretório de saída é ignorado pelo Git.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd


VIOLENCE_COLUMNS = {
    "v_fisica": "Violência física",
    "v_psicologica": "Violência psicológica",
    "v_patrimonial": "Violência patrimonial",
    "v_sexual": "Violência sexual",
    "v_moral": "Violência moral",
}

CONTEXT_COLUMNS = {
    "flag_alcool": "Consumo de álcool",
    "flag_drogas": "Drogas/entorpecentes",
    "flag_arma_fogo": "Arma de fogo",
    "flag_arma_branca": "Arma branca",
    "flag_tornozeleira": "Tornozeleira/monitoramento",
    "flag_medida_protetiva": "Medida protetiva",
    "flag_separacao": "Separação/término",
    "flag_filhos": "Filhos/crianças",
}

BASE_COLUMNS = [
    "numero", "data hora", "ano", "mes", "dia", "hora", "cidade", "quadra",
    "complemento", "TIPO_MORADIA", "TURNO", "id_celula", "reincidencia_endereco",
    "endereco_chave", "historico_limpo",
]


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=root / "data" / "base_analisada.csv")
    parser.add_argument("--output-dir", type=Path, default=root / "outputs" / "agrupamentos_nlp")
    return parser.parse_args()


def as_bool(series: pd.Series) -> pd.Series:
    """Converte booleans CSV e valores 0/1 para uma série booleana."""
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    normalized = series.astype("string").str.strip().str.lower()
    return normalized.isin({"true", "1", "sim", "yes", "y", "t"})


def repair_mojibake(value: object) -> object:
    """Corrige texto UTF-8 que tenha sido interpretado como Latin-1."""
    if not isinstance(value, str):
        return value
    has_mojibake = any(
        ord(value[index]) in (0xC3, 0xC2, 0xE2, 0xF0)
        and 0x80 <= ord(value[index + 1]) <= 0xBF
        for index in range(len(value) - 1)
    )
    if not has_mojibake:
        return value
    try:
        return value.encode("latin1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value


def normalize_address(df: pd.DataFrame) -> pd.Series:
    parts = []
    for column in ("cidade", "quadra", "complemento"):
        if column in df.columns:
            parts.append(df[column].fillna("").astype("string").str.upper())
        else:
            parts.append(pd.Series("", index=df.index, dtype="string"))
    address = parts[0] + " " + parts[1] + " " + parts[2]
    return address.str.replace(r"\s+", " ", regex=True).str.strip()


def safe_filename(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_]+", "_", value).strip("_").lower()
    return value or "categoria"


def select_case_columns(df: pd.DataFrame) -> list[str]:
    return [column for column in BASE_COLUMNS if column in df.columns]


def build_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    total = len(df)
    for column, label in {**VIOLENCE_COLUMNS, **CONTEXT_COLUMNS}.items():
        if column not in df.columns:
            continue
        count = int(df[column].sum())
        rows.append({
            "grupo": "violencia" if column in VIOLENCE_COLUMNS else "contexto",
            "coluna": column,
            "categoria": label,
            "registros": count,
            "percentual_registros": round(100 * count / total, 2) if total else 0.0,
            "definicao": "flag booleana derivada do histórico por spaCy/Regex",
        })

    if "desfecho" in df.columns:
        counts = df["desfecho"].fillna("nao_identificado").value_counts()
        for value, count in counts.items():
            rows.append({
                "grupo": "desfecho",
                "coluna": "desfecho",
                "categoria": str(value),
                "registros": int(count),
                "percentual_registros": round(100 * count / total, 2) if total else 0.0,
                "definicao": "classe categórica derivada do histórico por spaCy",
            })
    return pd.DataFrame(rows)


def build_address_category(df: pd.DataFrame, category_columns: list[str]) -> pd.DataFrame:
    rows = []
    date = pd.to_datetime(df["data hora"], errors="coerce", dayfirst=True) if "data hora" in df else pd.Series(pd.NaT, index=df.index)
    for column in category_columns:
        selected = df[df[column]].copy()
        if selected.empty:
            continue
        selected["_data"] = date.loc[selected.index]
        grouped = selected.groupby(["endereco_chave", "TIPO_MORADIA"], dropna=False)
        for (address, housing), group in grouped:
            dates = group["_data"].dropna()
            rows.append({
                "categoria": column,
                "rotulo_categoria": VIOLENCE_COLUMNS.get(column, CONTEXT_COLUMNS.get(column, column)),
                "endereco_chave": address,
                "tipo_moradia": housing,
                "ocorrencias": len(group),
                "endereco_repetido": len(group) > 1,
                "celulas_distintas": group["id_celula"].dropna().nunique() if "id_celula" in group else 0,
                "primeira_data": dates.min() if not dates.empty else pd.NaT,
                "ultima_data": dates.max() if not dates.empty else pd.NaT,
            })
    result = pd.DataFrame(rows)
    if not result.empty:
        result = result.sort_values(["categoria", "ocorrencias"], ascending=[True, False])
    return result


def gerar_agrupamentos_nlp(input_path: Path, output_dir: Path) -> Path:
    """Gera os agrupamentos NLP e retorna o diretório de saída."""
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    if not input_path.exists():
        raise FileNotFoundError(f"Base de entrada não encontrada: {input_path}")
    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(input_path, encoding="utf-8-sig", low_memory=False)
    if df.empty:
        raise ValueError("A base de entrada está vazia.")

    for column in df.select_dtypes(include=["object", "string"]).columns:
        df[column] = df[column].map(repair_mojibake)

    df["endereco_chave"] = normalize_address(df)
    bool_columns = [column for column in {**VIOLENCE_COLUMNS, **CONTEXT_COLUMNS} if column in df.columns]
    for column in bool_columns:
        df[column] = as_bool(df[column])

    case_columns = select_case_columns(df)
    summary = build_summary(df)
    summary.to_csv(output_dir / "resumo_nlp.csv", index=False, encoding="utf-8-sig")

    # Um arquivo por flag para facilitar a conferência manual dos históricos.
    for column in bool_columns:
        cases = df.loc[df[column], case_columns].copy()
        cases = cases.sort_values(["endereco_chave", "data hora"], na_position="last")
        cases.to_csv(output_dir / f"casos_{safe_filename(column)}.csv", index=False, encoding="utf-8-sig")

    if "desfecho" in df.columns:
        for value, cases in df.groupby(df["desfecho"].fillna("nao_identificado"), dropna=False):
            cases = cases.loc[:, case_columns + ["desfecho"]]
            cases.to_csv(output_dir / f"casos_desfecho_{safe_filename(str(value))}.csv", index=False, encoding="utf-8-sig")

    category_labels = {**VIOLENCE_COLUMNS, **CONTEXT_COLUMNS}
    long_rows = []
    for column in bool_columns:
        selected_columns = [c for c in ["numero", "data hora", "endereco_chave", "id_celula"] if c in df.columns]
        selected = df.loc[df[column], selected_columns].copy()
        selected["categoria"] = column
        selected["rotulo_categoria"] = category_labels[column]
        long_rows.append(selected)
    long_df = pd.concat(long_rows, ignore_index=True) if long_rows else pd.DataFrame()
    long_df.to_csv(output_dir / "casos_nlp_formato_longo.csv", index=False, encoding="utf-8-sig")

    # Combinações de flags: útil para validar coocorrência de fatores no mesmo registro.
    combo_rows = pd.DataFrame()
    if bool_columns:
        combination = df[bool_columns].astype(int).astype(str).agg(" + ".join, axis=1)
        combo_rows = (pd.DataFrame({"combinacao_flags": combination})
                      .value_counts()
                      .rename("registros")
                      .reset_index()
                      .sort_values("registros", ascending=False))
        combo_rows["flags_ativas"] = combo_rows["combinacao_flags"].map(
            lambda value: ", ".join(column for column, bit in zip(bool_columns, value.split(" + ")) if bit == "1")
        )
        combo_rows.to_csv(output_dir / "combinacoes_flags_nlp.csv", index=False, encoding="utf-8-sig")

    address_category = build_address_category(df, bool_columns)
    address_category.to_csv(output_dir / "agrupamento_endereco_categoria.csv", index=False, encoding="utf-8-sig")

    # Livro Excel com abas de resumo e casos, quando openpyxl estiver disponível.
    workbook = output_dir / "agrupamentos_nlp.xlsx"
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="resumo", index=False)
        if not combo_rows.empty:
            combo_rows.to_excel(writer, sheet_name="combinacoes", index=False)
        address_category.to_excel(writer, sheet_name="endereco_categoria", index=False)
        for column in bool_columns:
            df.loc[df[column], case_columns].to_excel(writer, sheet_name=safe_filename(column)[:31], index=False)
        if "desfecho" in df.columns:
            df.loc[:, case_columns + ["desfecho"]].to_excel(writer, sheet_name="desfecho", index=False)

    readme = """# Agrupamentos NLP

Arquivos gerados a partir de `data/base_analisada.csv` pelo quarto estágio do
`main.py` (ou diretamente por `scripts/agrupamentos_nlp.py`).

## Arquivos

- `resumo_nlp.csv`: quantidade e percentual de registros por categoria.
- `casos_*.csv`: registros classificados em cada flag, com histórico e localização.
- `casos_desfecho_*.csv`: registros separados por classe de desfecho.
- `casos_nlp_formato_longo.csv`: uma linha por registro e categoria ativa.
- `combinacoes_flags_nlp.csv`: coocorrências das flags booleanas.
- `agrupamento_endereco_categoria.csv`: contagem de cada categoria por endereço textual.
- `agrupamentos_nlp.xlsx`: planilha consolidada com abas para validação manual.

## Interpretação

As flags representam classificações derivadas do texto do boletim por Regex e spaCy.
Uma flag `False` não prova que o fator não ocorreu; significa apenas que ele não foi
identificado pelo dicionário, regra ou contexto sintático atual. A repetição de uma
categoria em um mesmo endereço é repetição de registros, não confirmação de que se
trata da mesma vítima ou do mesmo agressor.
"""
    (output_dir / "LEIA-ME.md").write_text(readme, encoding="utf-8")
    print(f"Agrupamentos NLP gerados em: {output_dir}")
    return output_dir


def main() -> None:
    args = parse_args()
    gerar_agrupamentos_nlp(args.input, args.output_dir)


if __name__ == "__main__":
    main()
