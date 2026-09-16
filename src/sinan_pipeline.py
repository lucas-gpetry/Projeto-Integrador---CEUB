"""Tratamento do SINAN e integração analítica agregada com a base PMDF.

O SINAN registra notificações de saúde; a base PMDF registra chamados policiais.
Por isso este módulo nunca vincula registros individuais, pessoas ou endereços entre
as fontes. A comparação é mensal, agregada e exploratória.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

try:
    from scipy.stats import pearsonr, spearmanr
    SCIPY_AVAILABLE = True
except ImportError:  # A correlação continua disponível no ambiente mínimo do projeto.
    SCIPY_AVAILABLE = False


ROOT = Path(__file__).resolve().parents[1]
SINAN_RAW_PATH = ROOT / "data" / "violencia_mulher_DF_2010_2025.csv"
PMDF_PATH = ROOT / "data" / "base_analisada.csv"
TREATED_PATH = ROOT / "data" / "sinan_mulher_df_tratada.csv"
OUTPUT_DIR = ROOT / "outputs" / "sinan_integracao"

YES, NO, UNKNOWN = "1", "2", "9"
DF_IBGE_CODE = "530010"
COMPARISON_YEAR = 2024
START_YEAR, END_YEAR = 2010, 2025


# Métricas que têm significado operacional suficientemente próximo nas duas fontes.
COMPARABLE_METRICS: list[dict[str, str | None]] = [
    {"id": "volume_total", "rotulo": "Volume de registros", "pmdf": None, "sinan": None},
    {"id": "violencia_fisica", "rotulo": "Violência física", "pmdf": "v_fisica", "sinan": "VIOL_FISIC"},
    {"id": "violencia_psicologica", "rotulo": "Violência psicológica", "pmdf": "v_psicologica", "sinan": "VIOL_PSICO"},
    {"id": "violencia_sexual", "rotulo": "Violência sexual", "pmdf": "v_sexual", "sinan": "VIOL_SEXU"},
    {"id": "arma_fogo", "rotulo": "Uso de arma de fogo", "pmdf": "flag_arma_fogo", "sinan": "AG_FOGO"},
    {"id": "arma_branca", "rotulo": "Uso de objeto perfurocortante", "pmdf": "flag_arma_branca", "sinan": "AG_CORTE"},
    {"id": "alcool", "rotulo": "Suspeita de uso de álcool pelo autor", "pmdf": "flag_alcool", "sinan": "AUTOR_ALCO"},
]


def _read_csv(path: Path) -> pd.DataFrame:
    """Lê códigos sem inferência numérica para preservar a codificação SINAN."""
    return pd.read_csv(path, dtype=str, keep_default_na=False, low_memory=False, encoding="utf-8-sig")


def _parse_sinan_date(series: pd.Series) -> pd.Series:
    values = series.replace("", pd.NA)
    return pd.to_datetime(values, format="%Y%m%d", errors="coerce")


def _pmdf_true(series: pd.Series) -> pd.Series:
    """Normaliza flags booleanas exportadas como bool, 0/1 ou texto."""
    return series.astype(str).str.strip().str.lower().isin({"true", "1", "sim", "yes"})


def _ensure_columns(frame: pd.DataFrame, columns: set[str], source_name: str) -> None:
    missing = sorted(columns.difference(frame.columns))
    if missing:
        raise ValueError(f"Colunas ausentes em {source_name}: {', '.join(missing)}")


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def preparar_sinan(input_path: Path = SINAN_RAW_PATH) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Cria uma camada tratada e uma tabela de qualidade sem alterar o CSV bruto."""
    raw = _read_csv(input_path)
    required = {
        "CS_SEXO", "DT_OCOR", "DT_NOTIFIC", "ID_MN_OCOR", "ID_MN_RESI", "LES_AUTOP",
        "VIOL_FISIC", "VIOL_PSICO", "VIOL_SEXU", "AG_FOGO", "AG_CORTE", "AUTOR_ALCO",
        "OUT_VEZES", "REL_CONJ", "REL_EXCON", "REL_NAMO", "REL_EXNAM",
    }
    _ensure_columns(raw, required, "SINAN")

    treated = raw.copy()
    treated.insert(0, "id_linha_origem", np.arange(1, len(treated) + 1))
    treated["data_ocorrencia"] = _parse_sinan_date(treated["DT_OCOR"])
    treated["data_notificacao"] = _parse_sinan_date(treated["DT_NOTIFIC"])
    treated["data_analitica"] = treated["data_ocorrencia"].fillna(treated["data_notificacao"])
    treated["fonte_data_analitica"] = np.where(
        treated["data_ocorrencia"].notna(), "ocorrencia",
        np.where(treated["data_notificacao"].notna(), "notificacao", "ausente"),
    )
    treated["ano_analitico"] = treated["data_analitica"].dt.year.astype("Int64")
    treated["mes_analitico"] = treated["data_analitica"].dt.to_period("M").astype(str)
    treated["data_valida_periodo"] = treated["ano_analitico"].between(START_YEAR, END_YEAR).fillna(False)
    treated["ocorrencia_df"] = treated["ID_MN_OCOR"].eq(DF_IBGE_CODE)
    treated["residencia_df"] = treated["ID_MN_RESI"].eq(DF_IBGE_CODE)
    treated["sexo_feminino"] = treated["CS_SEXO"].eq("F")
    treated["autoprovocada_confirmada"] = treated["LES_AUTOP"].eq(YES)
    treated["interpersonal_confirmada"] = treated["LES_AUTOP"].eq(NO)
    treated["autoprovocada_desconhecida"] = treated["LES_AUTOP"].isin([UNKNOWN, ""])
    base_scope = treated["sexo_feminino"] & treated["ocorrencia_df"] & treated["data_valida_periodo"]
    treated["coorte_pmdf_primaria"] = base_scope & treated["interpersonal_confirmada"]
    treated["coorte_pmdf_sensibilidade"] = base_scope & ~treated["autoprovocada_confirmada"]
    treated["vinculo_intimo"] = treated[["REL_CONJ", "REL_EXCON", "REL_NAMO", "REL_EXNAM"]].eq(YES).any(axis=1)
    treated["atraso_notificacao_dias"] = (
        treated["data_notificacao"] - treated["data_ocorrencia"]
    ).dt.days.astype("Int64")

    for column in ["VIOL_FISIC", "VIOL_PSICO", "VIOL_SEXU", "AG_FOGO", "AG_CORTE", "AUTOR_ALCO", "OUT_VEZES"]:
        treated[f"{column.lower()}_sim"] = treated[column].eq(YES)
        treated[f"{column.lower()}_ignorado"] = treated[column].isin([UNKNOWN, ""])

    exact_duplicates = int(raw.duplicated().sum())
    quality_rows: list[dict[str, Any]] = [
        {"indicador": "linhas_brutas", "valor": len(raw), "observacao": "Arquivo original preservado; nenhuma linha é removida nesta camada."},
        {"indicador": "sexo_feminino", "valor": int(treated["sexo_feminino"].sum()), "observacao": "Filtro da base recebida."},
        {"indicador": "data_ocorrencia_ausente_ou_invalida", "valor": int(treated["data_ocorrencia"].isna().sum()), "observacao": "Usa-se data de notificação apenas como fallback analítico."},
        {"indicador": "datas_fora_de_2010_2025", "valor": int((~treated["data_valida_periodo"]).sum()), "observacao": "Excluídas apenas das coortes analíticas."},
        {"indicador": "ocorrencias_no_df", "valor": int(treated["ocorrencia_df"].sum()), "observacao": f"ID_MN_OCOR = {DF_IBGE_CODE}."},
        {"indicador": "residentes_no_df", "valor": int(treated["residencia_df"].sum()), "observacao": f"ID_MN_RESI = {DF_IBGE_CODE}; não é o filtro territorial primário."},
        {"indicador": "autoprovocada_confirmada", "valor": int(treated["autoprovocada_confirmada"].sum()), "observacao": "LES_AUTOP = 1; fora da coorte comparável ao PMDF."},
        {"indicador": "les_autoprovocada_ignorada_ou_vazia", "valor": int(treated["autoprovocada_desconhecida"].sum()), "observacao": "Incluída somente na análise de sensibilidade."},
        {"indicador": "duplicatas_exatas", "valor": exact_duplicates, "observacao": "Duplicidade literal em todas as 159 colunas; a identificação oficial de duplicidade não veio preenchida."},
        {"indicador": "coorte_pmdf_primaria", "valor": int(treated["coorte_pmdf_primaria"].sum()), "observacao": "Mulheres, ocorrência no DF, data válida e violência não autoprovocada confirmada."},
        {"indicador": "coorte_pmdf_sensibilidade", "valor": int(treated["coorte_pmdf_sensibilidade"].sum()), "observacao": "Igual à primária, mas inclui LES_AUTOP ignorado/vazio."},
    ]
    return treated, pd.DataFrame(quality_rows)


def _monthly_metric_counts(frame: pd.DataFrame, date_column: str, metrics: list[dict[str, str | None]], source: str) -> pd.DataFrame:
    months = pd.date_range(f"{COMPARISON_YEAR}-01-01", f"{COMPARISON_YEAR}-12-01", freq="MS")
    data = pd.DataFrame({"mes": months})
    filtered = frame.loc[frame[date_column].dt.year.eq(COMPARISON_YEAR)].copy()
    filtered["mes"] = filtered[date_column].dt.to_period("M").dt.to_timestamp()
    for metric in metrics:
        key = str(metric["id"])
        column = metric[source]
        selected = filtered if column is None else filtered.loc[_pmdf_true(filtered[column]) if source == "pmdf" else filtered[column].eq(YES)]
        counts = selected.groupby("mes").size().reindex(months, fill_value=0)
        data[f"{source}_{key}"] = counts.to_numpy(dtype=int)
    total = data[f"{source}_volume_total"].replace(0, np.nan)
    for metric in metrics:
        key = str(metric["id"])
        data[f"{source}_{key}_proporcao"] = (data[f"{source}_{key}"] / total).round(6)
    return data


def _correlation_rows(monthly: pd.DataFrame, sinan_prefix: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for metric in COMPARABLE_METRICS:
        key = str(metric["id"])
        for comparison, suffix in [("contagem mensal", ""), ("proporção mensal", "_proporcao")]:
            left = monthly[f"pmdf_{key}{suffix}"]
            right = monthly[f"{sinan_prefix}_{key}{suffix}"]
            valid = pd.DataFrame({"pmdf": left, "sinan": right}).dropna()
            if len(valid) < 3 or valid["pmdf"].nunique() < 2 or valid["sinan"].nunique() < 2:
                pearson, pearson_p, spearman, spearman_p = (np.nan, np.nan, np.nan, np.nan)
            else:
                pearson = valid["pmdf"].corr(valid["sinan"], method="pearson")
                # Evita o caminho interno do pandas que importa scipy para Spearman.
                # A definição é Pearson aplicado aos postos médios das duas séries.
                spearman = valid["pmdf"].rank(method="average").corr(
                    valid["sinan"].rank(method="average"), method="pearson"
                )
                if SCIPY_AVAILABLE:
                    _, pearson_p = pearsonr(valid["pmdf"], valid["sinan"])
                    _, spearman_p = spearmanr(valid["pmdf"], valid["sinan"])
                else:
                    pearson_p, spearman_p = np.nan, np.nan
            magnitude = "indisponível" if pd.isna(pearson) else (
                "forte" if abs(pearson) >= 0.70 else "moderada" if abs(pearson) >= 0.40 else "fraca"
            )
            rows.append({
                "coorte_sinan": sinan_prefix.removeprefix("sinan_"),
                "metrica": key,
                "rotulo": metric["rotulo"],
                "comparacao": comparison,
                "n_meses": len(valid),
                "correlacao_pearson": round(float(pearson), 4) if pd.notna(pearson) else np.nan,
                "p_valor_pearson": round(float(pearson_p), 4) if pd.notna(pearson_p) else np.nan,
                "correlacao_spearman": round(float(spearman), 4) if pd.notna(spearman) else np.nan,
                "p_valor_spearman": round(float(spearman_p), 4) if pd.notna(spearman_p) else np.nan,
                "p_valor_disponivel": SCIPY_AVAILABLE,
                "leitura": f"associação {magnitude}; exploratória, sem inferência causal",
            })
    return rows


def _prepare_pmdf(path: Path) -> pd.DataFrame:
    pmdf = _read_csv(path)
    required = {"data hora", "reincidencia_endereco"}.union({str(metric["pmdf"]) for metric in COMPARABLE_METRICS if metric["pmdf"]})
    _ensure_columns(pmdf, required, "PMDF")
    # A etapa de limpeza PMDF padroniza este campo como ISO 8601 (YYYY-MM-DD HH:MM:SS).
    # Usar dayfirst=True aqui invalidaria todas as datas cujo dia é maior que 12.
    pmdf["data_analitica"] = pd.to_datetime(pmdf["data hora"], errors="coerce")
    pmdf["reincidencia_endereco"] = pd.to_numeric(pmdf["reincidencia_endereco"], errors="coerce").fillna(0).astype(int)
    return pmdf


def _definitions() -> pd.DataFrame:
    rows = [
        {"elemento": "Unidade de integração", "definicao": "Mês de ocorrência em 2024; não há junção por pessoa, endereço, CPF ou protocolo."},
        {"elemento": "Coorte SINAN primária", "definicao": "CS_SEXO=F, ID_MN_OCOR=530010, data analítica válida e LES_AUTOP=2 (não autoprovocada confirmada)."},
        {"elemento": "Coorte SINAN de sensibilidade", "definicao": "Mesmo recorte, porém LES_AUTOP diferente de 1; inclui códigos ignorados/vazios."},
        {"elemento": "Território", "definicao": "O local da ocorrência (ID_MN_OCOR), e não a residência, define o evento no DF."},
        {"elemento": "Reincidência", "definicao": "OUT_VEZES do SINAN mede histórico informado pela vítima; reincidência de endereço PMDF mede repetição espacial. Não são comparáveis nem correlacionadas."},
        {"elemento": "Correlação", "definicao": "Pearson e Spearman calculadas sobre 12 meses. É associação exploratória; não mede causalidade, cobertura nem concordância de registros."},
    ]
    return pd.DataFrame(rows)


def _correlation_statistics(left: pd.Series, right: pd.Series) -> dict[str, float | int | bool]:
    """Correlação robusta a valores ausentes e sem dependência obrigatória de scipy."""
    valid = pd.DataFrame({"left": left, "right": right}).dropna()
    if len(valid) < 3 or valid["left"].nunique() < 2 or valid["right"].nunique() < 2:
        return {"n": len(valid), "pearson": np.nan, "pearson_p": np.nan, "spearman": np.nan, "spearman_p": np.nan}
    pearson = valid["left"].corr(valid["right"], method="pearson")
    spearman = valid["left"].rank(method="average").corr(valid["right"].rank(method="average"), method="pearson")
    if SCIPY_AVAILABLE:
        _, pearson_p = pearsonr(valid["left"], valid["right"])
        _, spearman_p = spearmanr(valid["left"], valid["right"])
    else:
        pearson_p, spearman_p = np.nan, np.nan
    return {"n": len(valid), "pearson": pearson, "pearson_p": pearson_p, "spearman": spearman, "spearman_p": spearman_p}


def _benjamini_hochberg(p_values: pd.Series) -> pd.Series:
    """Ajusta p-valores para múltiplos testes pelo controle FDR de Benjamini-Hochberg."""
    result = pd.Series(np.nan, index=p_values.index, dtype=float)
    valid = p_values.dropna().sort_values()
    if valid.empty:
        return result
    total = len(valid)
    adjusted = valid.to_numpy(dtype=float) * total / np.arange(1, total + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    result.loc[valid.index] = np.minimum(adjusted, 1.0)
    return result


def _comparative_profile(pmdf_2024: pd.DataFrame, sinan_2024: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for metric in COMPARABLE_METRICS[1:]:
        pmdf_column, sinan_column = str(metric["pmdf"]), str(metric["sinan"])
        pmdf_yes = int(_pmdf_true(pmdf_2024[pmdf_column]).sum())
        sinan_yes = int(sinan_2024[sinan_column].eq(YES).sum())
        sinan_no = int(sinan_2024[sinan_column].eq(NO).sum())
        sinan_unknown = int(sinan_2024[sinan_column].isin([UNKNOWN, ""]).sum())
        sinan_known = sinan_yes + sinan_no
        pmdf_pct = pmdf_yes / len(pmdf_2024) if len(pmdf_2024) else np.nan
        sinan_pct = sinan_yes / sinan_known if sinan_known else np.nan
        rows.append({
            "metrica": metric["id"], "rotulo": metric["rotulo"],
            "pmdf_sim": pmdf_yes, "pmdf_total": len(pmdf_2024), "pmdf_percentual": round(pmdf_pct * 100, 2),
            "sinan_sim": sinan_yes, "sinan_nao": sinan_no, "sinan_respostas_validas": sinan_known,
            "sinan_ignorado_ou_vazio": sinan_unknown, "sinan_percentual_entre_validas": round(sinan_pct * 100, 2),
            "diferenca_pontos_percentuais_pmdf_menos_sinan": round((pmdf_pct - sinan_pct) * 100, 2),
            "alerta_interpretacao": "Fontes e regras de registro distintas; diferença não mede prevalência populacional.",
        })
    return pd.DataFrame(rows)


def _cooccurrence_profile(pmdf_2024: pd.DataFrame, sinan_2024: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    metrics = COMPARABLE_METRICS[1:]
    sources = [
        ("PMDF", {str(metric["id"]): _pmdf_true(pmdf_2024[str(metric["pmdf"])]) for metric in metrics}),
        ("SINAN", {str(metric["id"]): sinan_2024[str(metric["sinan"])].eq(YES) for metric in metrics}),
    ]
    for source, flags in sources:
        total = len(next(iter(flags.values()))) if flags else 0
        metric_items = list(flags.items())
        for index, (left_id, left) in enumerate(metric_items):
            for right_id, right in metric_items[index + 1:]:
                both = int((left & right).sum())
                union = int((left | right).sum())
                left_rate, right_rate = left.mean(), right.mean()
                lift = (both / total) / (left_rate * right_rate) if total and left_rate and right_rate else np.nan
                rows.append({
                    "fonte": source, "indicador_a": left_id, "indicador_b": right_id,
                    "casos_conjuntos": both, "percentual_do_total": round((both / total) * 100, 2) if total else np.nan,
                    "jaccard": round(both / union, 4) if union else np.nan,
                    "lift": round(lift, 4) if pd.notna(lift) else np.nan,
                    "observacao": "No SINAN, campos ignorados/vazios permanecem fora do numerador, mas no denominador da coocorrência.",
                })
    return pd.DataFrame(rows).sort_values(["fonte", "casos_conjuntos"], ascending=[True, False])


def _lagged_correlations(monthly: pd.DataFrame) -> pd.DataFrame:
    """Explora deslocamentos de até três meses; não seleciona um lag como achado causal."""
    rows: list[dict[str, Any]] = []
    for metric in COMPARABLE_METRICS:
        key = str(metric["id"])
        pmdf_values = monthly[f"pmdf_{key}"].reset_index(drop=True)
        sinan_values = monthly[f"sinan_primaria_{key}"].reset_index(drop=True)
        for lag in range(-3, 4):
            if lag > 0:
                left, right = pmdf_values.iloc[:-lag].reset_index(drop=True), sinan_values.iloc[lag:].reset_index(drop=True)
                definition = "PMDF antecede SINAN"
            elif lag < 0:
                left, right = pmdf_values.iloc[-lag:].reset_index(drop=True), sinan_values.iloc[:lag].reset_index(drop=True)
                definition = "SINAN antecede PMDF"
            else:
                left, right, definition = pmdf_values, sinan_values, "mesmo mês"
            stats = _correlation_statistics(left, right)
            rows.append({
                "metrica": key, "rotulo": metric["rotulo"], "defasagem_meses": lag,
                "leitura_defasagem": definition, "n_meses": stats["n"],
                "correlacao_pearson": round(float(stats["pearson"]), 4) if pd.notna(stats["pearson"]) else np.nan,
                "p_valor_pearson": round(float(stats["pearson_p"]), 4) if pd.notna(stats["pearson_p"]) else np.nan,
                "correlacao_spearman": round(float(stats["spearman"]), 4) if pd.notna(stats["spearman"]) else np.nan,
                "p_valor_disponivel": SCIPY_AVAILABLE,
                "alerta_interpretacao": "Teste exploratório com 9 a 12 pontos e múltiplas defasagens; não é evidência causal.",
            })
    result = pd.DataFrame(rows)
    result["p_valor_pearson_ajustado_bh"] = _benjamini_hochberg(result["p_valor_pearson"])
    return result


def _seasonality_and_recurrence(pmdf_2024: pd.DataFrame, sinan_2024: pd.DataFrame, monthly: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    months_pt = {1: "jan", 2: "fev", 3: "mar", 4: "abr", 5: "mai", 6: "jun", 7: "jul", 8: "ago", 9: "set", 10: "out", 11: "nov", 12: "dez"}
    seasonality_rows = []
    for source, column in [("PMDF", "pmdf_volume_total"), ("SINAN - coorte primária", "sinan_primaria_volume_total")]:
        values = monthly[column]
        peak_index, trough_index = values.idxmax(), values.idxmin()
        seasonality_rows.append({
            "fonte": source, "total_2024": int(values.sum()), "media_mensal": round(float(values.mean()), 2),
            "coeficiente_variacao_percentual": round(float(values.std(ddof=0) / values.mean() * 100), 2),
            "mes_pico": months_pt[int(str(monthly.loc[peak_index, "mes"])[5:7])], "valor_pico": int(values.loc[peak_index]),
            "mes_menor": months_pt[int(str(monthly.loc[trough_index, "mes"])[5:7])], "valor_menor": int(values.loc[trough_index]),
        })
    sinan_repeat_yes = int(sinan_2024["OUT_VEZES"].eq(YES).sum())
    sinan_repeat_no = int(sinan_2024["OUT_VEZES"].eq(NO).sum())
    recurrence_rows = [
        {
            "fonte": "PMDF", "conceito": "repetição espacial de endereço", "numerador": int(pmdf_2024["reincidencia_endereco"].gt(1).sum()),
            "denominador_valido": len(pmdf_2024), "percentual": round(float(pmdf_2024["reincidencia_endereco"].gt(1).mean() * 100), 2),
            "observacao": "Contagem de ocorrências no mesmo endereço normalizado; não identifica reincidência de pessoa.",
        },
        {
            "fonte": "SINAN", "conceito": "histórico de violência relatado", "numerador": sinan_repeat_yes,
            "denominador_valido": sinan_repeat_yes + sinan_repeat_no,
            "percentual": round(sinan_repeat_yes / max(sinan_repeat_yes + sinan_repeat_no, 1) * 100, 2),
            "observacao": "OUT_VEZES = 1 entre respostas válidas; não é comparável à repetição espacial PMDF.",
        },
    ]
    return pd.DataFrame(seasonality_rows), pd.DataFrame(recurrence_rows)


def _linkage_feasibility(pmdf_2024: pd.DataFrame, sinan_2024: pd.DataFrame) -> pd.DataFrame:
    """Audita chaves de vínculo sem produzir ou expor pares de registros individuais."""
    pmdf_daily = pmdf_2024.groupby(pmdf_2024["data_analitica"].dt.normalize()).size().rename("pmdf")
    sinan_daily = sinan_2024.groupby(sinan_2024["data_analitica"].dt.normalize()).size().rename("sinan")
    daily = pd.concat([pmdf_daily, sinan_daily], axis=1, join="inner").fillna(0)
    candidates = daily["pmdf"] * daily["sinan"]
    date_pairs = int(candidates.sum())
    rows = [
        {
            "dimensao": "Pessoa", "campos_pmdf": "ausente na exportação analítica", "campos_sinan": "ausente na exportação recebida",
            "situacao": "inviável", "risco": "Não há identificador comum para uma associação individual.",
        },
        {
            "dimensao": "Protocolo", "campos_pmdf": "numero (protocolo PMDF)", "campos_sinan": "nenhum protocolo compartilhado",
            "situacao": "inviável", "risco": "Os sistemas usam identificadores próprios; não existe chave cruzada.",
        },
        {
            "dimensao": "Endereço", "campos_pmdf": "bairro, quadra, complemento", "campos_sinan": "município e categoria de local de ocorrência",
            "situacao": "inviável", "risco": "O SINAN recebido não possui endereço detalhado para normalização e comparação.",
        },
        {
            "dimensao": "Texto livre", "campos_pmdf": "historico", "campos_sinan": "nenhum campo narrativo equivalente",
            "situacao": "inviável", "risco": "Não há dois textos comparáveis; NLP não cria uma chave confiável.",
        },
        {
            "dimensao": "Data de ocorrência", "campos_pmdf": "data hora", "campos_sinan": "DT_OCOR / DT_NOTIFIC",
            "situacao": "insuficiente", "risco": (
                f"{date_pairs:,} pares candidatos em {len(daily):,} dias; "
                f"média de {date_pairs / max(len(sinan_2024), 1):.2f} atendimentos PMDF por notificação SINAN."
            ),
        },
    ]
    return pd.DataFrame(rows)


def _build_linkage_feasibility_report(feasibility: pd.DataFrame) -> str:
    date_row = feasibility.loc[feasibility["dimensao"].eq("Data de ocorrência")].iloc[0]
    lines = [
        "# Viabilidade de vinculação individual — SINAN × PMDF", "",
        "## Resultado", "",
        "Não é metodologicamente seguro produzir vínculo individual com os arquivos atualmente recebidos.",
        "Não há identificador pessoal, protocolo compartilhado, endereço detalhado nas duas fontes ou dois campos de texto livre comparáveis.",
        "", "## Teste de chave temporal", "",
        f"- {date_row['risco']}",
        "- Data e município apenas reduzem o universo de busca; não confirmam que dois registros representam o mesmo episódio.",
        "", "## Regra de decisão", "",
        "Não gerar pares individuais, escores de correspondência ou lista de supostos casos coincidentes a partir de data, endereço parcial ou texto livre.",
        "Essas regras têm alta probabilidade de falsos positivos e combinam dados policiais e de saúde sensíveis.",
        "", "## Condições mínimas para prosseguir", "",
        "1. Base legal, finalidade documentada e autorização institucional para vincular dados de saúde e segurança pública.",
        "2. Um identificador pseudonimizado comum, gerado pelas instituições de origem com HMAC/segredo institucional; não usar hashes simples de nome, CPF ou endereço.",
        "3. Ambiente restrito, registro de acesso, retenção limitada e validação humana por equipe autorizada em amostra independente.",
        "4. Avaliação prévia de precisão e falsos positivos antes de qualquer uso analítico ou operacional.",
        "", "## Uso permitido com as bases atuais", "",
        "Integração agregada por mês, território compatível e indicadores, conforme os relatórios já produzidos.",
    ]
    return "\n".join(lines) + "\n"


def _build_deep_dive_report(
    quality: pd.DataFrame, comparative: pd.DataFrame, cooccurrence: pd.DataFrame,
    lagged: pd.DataFrame, seasonality: pd.DataFrame, recurrence: pd.DataFrame,
) -> str:
    quality_values = quality.set_index("indicador")["valor"]
    pmdf_season = seasonality.loc[seasonality["fonte"].eq("PMDF")].iloc[0]
    sinan_season = seasonality.loc[seasonality["fonte"].eq("SINAN - coorte primária")].iloc[0]
    comparison_top = comparative.assign(abs_diff=comparative["diferenca_pontos_percentuais_pmdf_menos_sinan"].abs()).sort_values("abs_diff", ascending=False).head(3)
    cooccurrence_top = cooccurrence.groupby("fonte", group_keys=False).head(2)
    lag_same = lagged.loc[lagged["defasagem_meses"].eq(0)].sort_values("correlacao_pearson", key=lambda s: s.abs(), ascending=False).head(3)
    lag_significant = int(lagged["p_valor_pearson_ajustado_bh"].lt(0.05).sum())
    lines = [
        "# Deep dive — SINAN × PMDF (2024)", "",
        "## Base analítica e cautelas", "",
        f"- PMDF: {int(pmdf_season['total_2024']):,} atendimentos; SINAN: {int(sinan_season['total_2024']):,} notificações da coorte primária.",
        f"- SINAN bruto: {int(quality_values['linhas_brutas']):,} linhas, {int(quality_values['data_ocorrencia_ausente_ou_invalida']):,} datas de ocorrência ausentes/inválidas e {int(quality_values['duplicatas_exatas']):,} duplicatas exatas.",
        "- Não existe chave para associar os mesmos episódios entre as bases. Todas as leituras abaixo são agregadas por mês ou por composição de indicadores.", "",
        "## Sazonalidade", "",
        f"- PMDF: pico em {pmdf_season['mes_pico']} ({int(pmdf_season['valor_pico']):,}) e menor volume em {pmdf_season['mes_menor']} ({int(pmdf_season['valor_menor']):,}); coeficiente de variação de {pmdf_season['coeficiente_variacao_percentual']:.2f}%.",
        f"- SINAN: pico em {sinan_season['mes_pico']} ({int(sinan_season['valor_pico']):,}) e menor volume em {sinan_season['mes_menor']} ({int(sinan_season['valor_menor']):,}); coeficiente de variação de {sinan_season['coeficiente_variacao_percentual']:.2f}%.",
        "- Os picos não coincidem; portanto, não há suporte para usar o volume mensal de uma fonte como proxy direto da outra.", "",
        "## Diferenças de composição", "",
    ]
    for _, row in comparison_top.iterrows():
        lines.append(f"- {row['rotulo']}: PMDF {row['pmdf_percentual']:.2f}% versus SINAN {row['sinan_percentual_entre_validas']:.2f}% entre respostas válidas (diferença de {row['diferenca_pontos_percentuais_pmdf_menos_sinan']:+.2f} p.p.).")
    lines.extend(["", "## Coocorrências internas", ""])
    for _, row in cooccurrence_top.iterrows():
        lines.append(f"- {row['fonte']}: {row['indicador_a']} + {row['indicador_b']} em {int(row['casos_conjuntos']):,} casos ({row['percentual_do_total']:.2f}% da fonte; Jaccard {row['jaccard']:.4f}).")
    lines.extend(["", "## Associação temporal", ""])
    for _, row in lag_same.iterrows():
        lines.append(f"- {row['rotulo']}: Pearson no mesmo mês = {row['correlacao_pearson']:.4f}; p-valor = {row['p_valor_pearson']:.4f}. A amostra de 12 meses é insuficiente para inferência causal.")
    lines.append(f"- A varredura de 49 correlações com defasagem (−3 a +3 meses) teve {lag_significant} resultado(s) com p-valor ajustado por Benjamini-Hochberg abaixo de 0,05; sinais isolados não devem ser tratados como descoberta.")
    lines.extend(["", "## Reincidência: conceitos separados", ""])
    for _, row in recurrence.iterrows():
        lines.append(f"- {row['fonte']}: {row['percentual']:.2f}% ({int(row['numerador']):,}/{int(row['denominador_valido']):,}) — {row['conceito']}.")
    lines.extend(["", "## Próximo uso recomendado", "", "- Usar os resultados para comparar padrões de registro e direcionar investigações agregadas; não estimar prevalência, subnotificação ou risco individual.", "- Para aprofundar território, comparar por Região Administrativa somente após uma tabela de correspondência oficial e uma regra de supressão de células pequenas.", ""])
    return "\n".join(lines)


def _build_report(quality: pd.DataFrame, monthly: pd.DataFrame, correlations: pd.DataFrame) -> str:
    primary = correlations.loc[(correlations["coorte_sinan"] == "primaria") & (correlations["comparacao"] == "contagem mensal")]
    top = primary.reindex(primary["correlacao_pearson"].abs().sort_values(ascending=False).index).head(5)
    quality_lookup = quality.set_index("indicador")["valor"]
    pmdf_total = int(monthly["pmdf_volume_total"].sum())
    sinan_primary = int(monthly["sinan_primaria_volume_total"].sum())
    lines = [
        "# Integração analítica SINAN × PMDF",
        "",
        "## Escopo",
        "",
        f"- PMDF: {pmdf_total:,} registros em {COMPARISON_YEAR}.",
        f"- SINAN, coorte primária: {sinan_primary:,} notificações de mulheres, com ocorrência no DF e violência não autoprovocada confirmada.",
        f"- Base SINAN recebida: {int(quality_lookup['linhas_brutas']):,} linhas; {int(quality_lookup['duplicatas_exatas']):,} duplicatas literais.",
        "- A análise é mensal e agregada. As fontes retratam serviços e processos distintos; resultados não permitem estimar subnotificação, causalidade ou correspondência entre casos.",
        "",
        "## Correlações de contagem mensal (coorte primária)",
        "",
        "| Métrica | Pearson | p-valor | Spearman |",
        "|---|---:|---:|---:|",
    ]
    for _, row in top.iterrows():
        lines.append(f"| {row['rotulo']} | {row['correlacao_pearson']:.4f} | {row['p_valor_pearson']:.4f} | {row['correlacao_spearman']:.4f} |")
    lines.extend([
        "",
        "## Limites obrigatórios de interpretação",
        "",
        "- SINAN é uma notificação de saúde e o PMDF registra atendimentos/chamados policiais. Um mesmo episódio pode estar em uma, nas duas ou em nenhuma base.",
        "- A ficha SINAN inclui violências interpessoais, sexuais e autoprovocadas. A coorte primária exclui a última quando confirmada; a aba de sensibilidade mostra o efeito dos códigos ignorados.",
        "- Reincidência por endereço no PMDF e `OUT_VEZES` no SINAN respondem a conceitos diferentes e foram mantidos fora das correlações.",
        "",
        "## Referências",
        "",
        "- Ministério da Saúde. [VIVA/SINAN – Vigilância de Violências e Acidentes](https://www.gov.br/saude/pt-br/composicao/svsa/inqueritos-de-saude/viva-sinan).",
        "- Ministério da Saúde. [Instrutivo de notificação de violência interpessoal e autoprovocada](https://bvsms.saude.gov.br/bvs/publicacoes/viva_instrutivo_violencia_interpessoal_autoprovocada_2ed.pdf).",
    ])
    return "\n".join(lines) + "\n"


def processar_sinan_e_integrar_pmdf(
    sinan_path: Path = SINAN_RAW_PATH,
    pmdf_path: Path = PMDF_PATH,
    output_dir: Path = OUTPUT_DIR,
) -> Path:
    """Executa tratamento, qualidade e integração agregada SINAN × PMDF."""
    sinan, quality = preparar_sinan(Path(sinan_path))
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Camada tratada preserva códigos e acrescenta campos analíticos; o CSV bruto não é modificado.
    _write_csv(sinan, TREATED_PATH)
    _write_csv(quality, output_dir / "qualidade_sinan.csv")
    _write_csv(_definitions(), output_dir / "definicoes_metricas.csv")

    annual = (
        sinan.loc[sinan["coorte_pmdf_primaria"]]
        .groupby("ano_analitico", dropna=True)
        .size().rename("notificacoes_interpessoais_confirmadas")
        .reset_index()
    )
    _write_csv(annual, output_dir / "sinan_anual_2010_2025.csv")

    profile_2024 = sinan.loc[sinan["coorte_pmdf_primaria"] & sinan["data_analitica"].dt.year.eq(COMPARISON_YEAR)]
    profile_rows = []
    for metric in COMPARABLE_METRICS[1:]:
        col = str(metric["sinan"])
        profile_rows.append({
            "metrica": metric["id"], "rotulo": metric["rotulo"], "sim": int(profile_2024[col].eq(YES).sum()),
            "nao": int(profile_2024[col].eq(NO).sum()), "ignorado_ou_vazio": int(profile_2024[col].isin([UNKNOWN, ""]).sum()),
        })
    profile = pd.DataFrame(profile_rows)
    profile["percentual_sim_sobre_coorte"] = (profile["sim"] / max(len(profile_2024), 1) * 100).round(2)
    _write_csv(profile, output_dir / "perfil_sinan_2024.csv")

    pmdf = _prepare_pmdf(Path(pmdf_path))
    primary = sinan.loc[sinan["coorte_pmdf_primaria"]].copy()
    sensitivity = sinan.loc[sinan["coorte_pmdf_sensibilidade"]].copy()
    monthly = _monthly_metric_counts(pmdf, "data_analitica", COMPARABLE_METRICS, "pmdf")
    for prefix, frame in [("sinan_primaria", primary), ("sinan_sensibilidade", sensitivity)]:
        part = _monthly_metric_counts(frame, "data_analitica", COMPARABLE_METRICS, "sinan")
        part = part.rename(columns={column: column.replace("sinan_", f"{prefix}_") for column in part.columns if column.startswith("sinan_")})
        monthly = monthly.merge(part, on="mes", how="left")
    monthly["mes"] = monthly["mes"].dt.strftime("%Y-%m")
    _write_csv(monthly, output_dir / "pmdf_sinan_mensal_2024.csv")

    correlation_monthly = monthly.copy()
    correlation_monthly["mes"] = pd.to_datetime(correlation_monthly["mes"])
    correlations = pd.DataFrame(_correlation_rows(correlation_monthly, "sinan_primaria") + _correlation_rows(correlation_monthly, "sinan_sensibilidade"))
    _write_csv(correlations, output_dir / "correlacoes_pmdf_sinan_2024.csv")
    (output_dir / "relatorio_integracao_sinan_pmdf.md").write_text(_build_report(quality, monthly, correlations), encoding="utf-8")

    pmdf_2024 = pmdf.loc[pmdf["data_analitica"].dt.year.eq(COMPARISON_YEAR)].copy()
    comparative = _comparative_profile(pmdf_2024, profile_2024)
    cooccurrence = _cooccurrence_profile(pmdf_2024, profile_2024)
    lagged = _lagged_correlations(correlation_monthly)
    seasonality, recurrence = _seasonality_and_recurrence(pmdf_2024, profile_2024, monthly)
    _write_csv(comparative, output_dir / "perfil_comparativo_pmdf_sinan_2024.csv")
    _write_csv(cooccurrence, output_dir / "coocorrencias_pmdf_sinan_2024.csv")
    _write_csv(lagged, output_dir / "correlacoes_defasadas_pmdf_sinan_2024.csv")
    _write_csv(seasonality, output_dir / "sazonalidade_pmdf_sinan_2024.csv")
    _write_csv(recurrence, output_dir / "reincidencia_conceitos_2024.csv")
    linkage_feasibility = _linkage_feasibility(pmdf_2024, profile_2024)
    _write_csv(linkage_feasibility, output_dir / "viabilidade_vinculacao_individual.csv")
    (output_dir / "viabilidade_vinculacao_individual.md").write_text(
        _build_linkage_feasibility_report(linkage_feasibility), encoding="utf-8"
    )
    (output_dir / "deep_dive_sinan_pmdf_2024.md").write_text(
        _build_deep_dive_report(quality, comparative, cooccurrence, lagged, seasonality, recurrence), encoding="utf-8"
    )
    return output_dir


if __name__ == "__main__":
    destination = processar_sinan_e_integrar_pmdf()
    print(f"Integração SINAN × PMDF gerada em: {destination}")
