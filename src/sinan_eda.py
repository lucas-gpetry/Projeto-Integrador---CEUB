"""Análise exploratória das notificações SINAN de violência contra a mulher no DF.

Espelha a análise da base PMDF (relatorio_final.qmd): qualidade, padrões temporais,
formas de violência, perfil da vítima e do autor, local, repetição, associações e
concentração. Parte da camada tratada de `sinan_pipeline.preparar_sinan` e usa as mesmas
funções de `report_stats` e `report_figures`, para que as duas fontes sejam descritas
pelos mesmos métodos.

A unidade de análise é a **notificação**, não a mulher. Todas as saídas são agregadas.

Uso, a partir da raiz do projeto:
    python src/sinan_eda.py                      # coorte primária, foco em 2024
    python src/sinan_eda.py --ano 2023 --coorte coorte_pmdf_sensibilidade
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.sinan_pipeline import NO, SINAN_RAW_PATH, YES, preparar_sinan  # noqa: E402
from src.utils import report_figures as rf  # noqa: E402
from src.utils import report_stats as rs  # noqa: E402
from src.utils.report_theme import set_report_theme  # noqa: E402

OUTPUT_DIR = ROOT / "outputs" / "sinan_eda"
fp, fn = rs.formatar_pct, rs.formatar_num

# Na ficha SINAN, 9/99 é "ignorado" e 8/88 "não se aplica"; vazio é campo não preenchido.
NAO_INFORMADO = {"", "9", "99"}
NAO_SE_APLICA = {"8", "88"}

# ---------- Dicionários da ficha de notificação individual de violência ----------
# A ficha agrupa violência psicológica e moral num só campo, ao contrário das flags PMDF.
FORMAS_VIOLENCIA = {
    "VIOL_FISIC": "Física", "VIOL_PSICO": "Psicológica/moral", "VIOL_SEXU": "Sexual",
    "VIOL_TORT": "Tortura", "VIOL_FINAN": "Financeira/econômica", "VIOL_NEGLI": "Negligência/abandono",
    "VIOL_TRAF": "Tráfico de seres humanos", "VIOL_INFAN": "Trabalho infantil",
    "VIOL_LEGAL": "Intervenção legal", "VIOL_OUTR": "Outra",
}
MEIOS_AGRESSAO = {
    "AG_FORCA": "Força corporal/espancamento", "AG_ENFOR": "Enforcamento", "AG_OBJETO": "Objeto contundente",
    "AG_CORTE": "Objeto perfurocortante", "AG_QUENTE": "Substância/objeto quente",
    "AG_ENVEN": "Envenenamento/intoxicação", "AG_FOGO": "Arma de fogo", "AG_AMEACA": "Ameaça", "AG_OUTROS": "Outro",
}
VIOLENCIA_SEXUAL = {
    "SEX_ASSEDI": "Assédio sexual", "SEX_ESTUPR": "Estupro", "SEX_PORNO": "Pornografia infantil",
    "SEX_EXPLO": "Exploração sexual", "SEX_OUTRO": "Outra",
}
VINCULOS = {
    "REL_PAI": "Pai", "REL_MAE": "Mãe", "REL_PAD": "Padrasto", "REL_MAD": "Madrasta",
    "REL_CONJ": "Cônjuge", "REL_EXCON": "Ex-cônjuge", "REL_NAMO": "Namorado(a)", "REL_EXNAM": "Ex-namorado(a)",
    "REL_FILHO": "Filho(a)", "REL_IRMAO": "Irmão(ã)", "REL_CONHEC": "Amigo(a)/conhecido(a)",
    "REL_DESCO": "Desconhecido(a)", "REL_CUIDA": "Cuidador(a)", "REL_PATRAO": "Patrão/chefe",
    "REL_INST": "Relação institucional", "REL_POL": "Policial/agente da lei",
    "REL_PROPRI": "Própria pessoa", "REL_OUTROS": "Outro vínculo",
}
# Hierarquia para um vínculo único por notificação: o primeiro grupo marcado prevalece.
GRUPOS_VINCULO = [
    ("Parceiro ou ex-parceiro íntimo", ["REL_CONJ", "REL_EXCON", "REL_NAMO", "REL_EXNAM"]),
    ("Familiar", ["REL_PAI", "REL_MAE", "REL_PAD", "REL_MAD", "REL_FILHO", "REL_IRMAO"]),
    ("Conhecido(a)", ["REL_CONHEC", "REL_CUIDA", "REL_PATRAO", "REL_INST"]),
    ("Desconhecido(a)", ["REL_DESCO"]),
    ("Outro", ["REL_POL", "REL_PROPRI", "REL_OUTROS"]),
]
# A ficha mudou os campos de encaminhamento em 2015; usa-se o que vier na exportação.
ENCAMINHAMENTOS = {
    "REDE_SAU": "Rede de saúde", "ASSIST_SOC": "Assistência social", "REDE_EDUCA": "Rede de educação",
    "ATEND_MULH": "Atendimento especializado à mulher", "CONS_TUTEL": "Conselho Tutelar",
    "CONS_IDO": "Conselho do Idoso", "DELEG_IDOS": "Delegacia do Idoso", "DIR_HUMAN": "Direitos humanos",
    "MPU": "Ministério Público", "DELEG_CRIA": "Delegacia da Criança e do Adolescente",
    "DELEG_MULH": "Delegacia da Mulher", "DELEG": "Outras delegacias", "INFAN_JUV": "Justiça da Infância e Juventude",
    "DEFEN_PUBL": "Defensoria Pública",
    "ENC_SAUDE": "Rede de saúde (ficha anterior)", "ENC_TUTELA": "Conselho Tutelar (ficha anterior)",
    "ENC_DEAM": "Delegacia da Mulher (ficha anterior)", "ENC_DELEG": "Outras delegacias (ficha anterior)",
    "ENC_MPU": "Ministério Público (ficha anterior)", "ENC_MULHER": "Centro de referência da mulher (ficha anterior)",
    "ENC_CREAS": "CREAS/CRAS (ficha anterior)", "ENC_IML": "IML (ficha anterior)",
    "ENC_VARA": "Vara da Infância e Juventude (ficha anterior)", "ENC_ABRIGO": "Abrigo (ficha anterior)",
    "ENC_SENTIN": "Programa Sentinela (ficha anterior)", "ENC_DPCA": "Delegacia da Criança (ficha anterior)",
    "ENC_OUTR": "Outros (ficha anterior)",
}
CATEGORIAS = {
    "CS_RACA": ("Raça/cor", {"1": "Branca", "2": "Preta", "3": "Amarela", "4": "Parda", "5": "Indígena"}),
    "CS_ESCOL_N": ("Escolaridade", {
        "0": "Analfabeta", "1": "1ª a 4ª série incompleta", "2": "4ª série completa",
        "3": "5ª a 8ª série incompleta", "4": "Fundamental completo", "5": "Médio incompleto",
        "6": "Médio completo", "7": "Superior incompleto", "8": "Superior completo",
    }),
    "SIT_CONJUG": ("Situação conjugal", {"1": "Solteira", "2": "Casada/união consensual", "3": "Viúva", "4": "Separada"}),
    "CS_GESTANT": ("Gestação", {
        "1": "1º trimestre", "2": "2º trimestre", "3": "3º trimestre", "4": "Idade gestacional ignorada", "5": "Não gestante",
    }),
    "ORIENT_SEX": ("Orientação sexual", {"1": "Heterossexual", "2": "Lésbica", "3": "Bissexual"}),
    "IDENT_GEN": ("Identidade de gênero", {"1": "Travesti", "2": "Mulher transexual", "3": "Homem transexual"}),
    "LOCAL_OCOR": ("Local de ocorrência", {
        "1": "Residência", "2": "Habitação coletiva", "3": "Escola", "4": "Local de prática esportiva",
        "5": "Bar ou similar", "6": "Via pública", "7": "Comércio/serviços", "8": "Indústria/construção", "9": "Outro",
    }),
    "VIOL_MOTIV": ("Motivação da violência", {
        "1": "Sexismo", "2": "Homo/lesbo/bi/transfobia", "3": "Racismo", "4": "Intolerância religiosa",
        "5": "Xenofobia", "6": "Conflito geracional", "7": "Situação de rua", "8": "Deficiência", "9": "Outros",
    }),
    "AUTOR_SEXO": ("Sexo do autor", {"1": "Masculino", "2": "Feminino", "3": "Ambos os sexos"}),
    "NUM_ENVOLV": ("Número de autores", {"1": "Um", "2": "Dois ou mais"}),
    "CICL_VID": ("Ciclo de vida do autor", {
        "1": "Criança (0–9)", "2": "Adolescente (10–19)", "3": "Jovem (20–24)",
        "4": "Pessoa adulta (25–59)", "5": "Pessoa idosa (60+)",
    }),
}
# Códigos fora do padrão 9/99/8 que também não são resposta válida.
IGNORADOS_ESPECIFICOS = {"LOCAL_OCOR": {"", "99"}}
NAO_SE_APLICA_ESPECIFICOS = {"CS_ESCOL_N": {"10"}, "CS_GESTANT": {"6"}, "SIT_CONJUG": {"8"}}

FAIXAS_IDADE = [0, 10, 15, 20, 30, 40, 50, 60, 200]
ROTULOS_IDADE = ["0–9", "10–14", "15–19", "20–29", "30–39", "40–49", "50–59", "60+"]

FLAGS_CONTEXTO = {
    "AUTOR_ALCO": "Suspeita de álcool pelo autor", "OUT_VEZES": "Violência de repetição",
    "DEF_TRANS": "Vítima com deficiência/transtorno", "LES_AUTOP": "Lesão autoprovocada",
}

# Associações espelhadas no relatório PMDF; a faixa etária é o confundidor principal no SINAN,
# porque a violência sexual concentra-se na infância e a física por parceiro na vida adulta.
ASSOCIACOES = [
    ("AUTOR_ALCO", "VIOL_FISIC", "Álcool → violência física"),
    ("AUTOR_ALCO", "VIOL_PSICO", "Álcool → violência psicológica/moral"),
    ("AG_FOGO", "VIOL_PSICO", "Arma de fogo → violência psicológica/moral"),
    ("vinculo_intimo", "VIOL_FISIC", "Vínculo íntimo → violência física"),
    ("vinculo_intimo", "OUT_VEZES", "Vínculo íntimo → violência de repetição"),
    ("residencia", "VIOL_FISIC", "Residência → violência física"),
]


# ---------- Preparação ----------

def normalizar_codigos(serie: pd.Series) -> pd.Series:
    """'01' -> '1', '1.0' -> '1', ' 9 ' -> '9'; preserva vazios e textos."""
    s = serie.fillna("").astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    digitos = s.str.fullmatch(r"\d+")
    return s.where(~digitos, s[digitos].str.lstrip("0").replace("", "0"))


def decodificar_idade(serie: pd.Series) -> pd.Series:
    """Idade em anos a partir de NU_IDADE_N.

    O SINAN codifica a unidade no primeiro dígito: 4025 = 25 anos; 1xxx, 2xxx e 3xxx são
    horas, dias e meses (menos de 1 ano). Exportações já convertidas trazem anos (0–120).
    """
    n = pd.to_numeric(serie, errors="coerce")
    anos = np.select(
        [n.between(4000, 4130), n.between(1000, 3999), n.between(0, 120)],
        [n - 4000, 0, n],
        default=np.nan,
    )
    return pd.Series(anos, index=serie.index, dtype=float)


def hora_ocorrencia(serie: pd.Series) -> pd.Series:
    """Hora (0–23) de HORA_OCOR em 'HH:MM', 'HHhMM', 'HHMM', 'HMM' ou 'HH'."""
    s = serie.fillna("").astype(str).str.strip()
    com_separador = s.str.extract(r"^(\d{1,2})\s*[:hH]", expand=False)
    so_digitos = s.where(s.str.fullmatch(r"\d{1,4}"))
    sem_separador = so_digitos.where(so_digitos.str.len() <= 2, so_digitos.str[:-2])
    hora = pd.to_numeric(com_separador.fillna(sem_separador), errors="coerce")
    return hora.where(hora.between(0, 23))


def grupo_vinculo(df: pd.DataFrame) -> pd.Series:
    """Vínculo único por notificação, pela hierarquia de GRUPOS_VINCULO."""
    condicoes, nomes = [], []
    for nome, colunas in GRUPOS_VINCULO:
        presentes = [c for c in colunas if c in df]
        if presentes:
            condicoes.append(df[presentes].eq(YES).any(axis=1))
            nomes.append(nome)
    if not condicoes:
        return pd.Series("Não informado", index=df.index)
    return pd.Series(np.select(condicoes, nomes, default="Não informado"), index=df.index)


def preparar_coorte(caminho: Path, coorte: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Camada tratada completa, tabela de qualidade e a coorte com campos derivados."""
    tratada, qualidade = preparar_sinan(Path(caminho))
    base = tratada.loc[tratada[coorte]].copy()
    codificadas = [
        *FORMAS_VIOLENCIA, *MEIOS_AGRESSAO, *VIOLENCIA_SEXUAL, *VINCULOS, *ENCAMINHAMENTOS,
        *CATEGORIAS, *FLAGS_CONTEXTO,
    ]
    for coluna in dict.fromkeys(codificadas):
        if coluna in base:
            base[coluna] = normalizar_codigos(base[coluna])
    base["idade"] = decodificar_idade(base["NU_IDADE_N"]) if "NU_IDADE_N" in base else np.nan
    base["faixa_etaria"] = pd.cut(base["idade"], FAIXAS_IDADE, right=False, labels=ROTULOS_IDADE)
    base["hora"] = hora_ocorrencia(base["HORA_OCOR"]) if "HORA_OCOR" in base else np.nan
    # Dia 1 tem cerca de 2,7 vezes a frequência dos demais dias do mês: é o valor digitado quando só
    # o mês (ou, em 01/01, só o ano) é conhecido. 00:00 cumpre o mesmo papel para a hora.
    base["dia_imputado"] = base["data_ocorrencia"].dt.day.eq(1)
    base["hora_padrao"] = base["HORA_OCOR"].str.strip().isin(["00:00", "0000"]) if "HORA_OCOR" in base else False
    base["grupo_vinculo"] = grupo_vinculo(base)
    if "LOCAL_OCOR" in base:
        base["residencia"] = base["LOCAL_OCOR"].eq("1")
    # Recorte mais próximo do escopo da Lei Maria da Penha (relação íntima ou familiar, mulher adulta).
    base["recorte_domestico"] = base["idade"].ge(18) & base["grupo_vinculo"].isin(
        ["Parceiro ou ex-parceiro íntimo", "Familiar"])
    return tratada, qualidade, base


# ---------- Tabelas ----------

def tabela_flags(df: pd.DataFrame, colunas: dict[str, str]) -> pd.DataFrame:
    """Proporção de 'sim' entre respostas válidas (1/2), com IC de Wilson e o peso do não informado."""
    linhas = []
    for coluna, rotulo in colunas.items():
        if coluna not in df:
            continue
        sim, nao = df[coluna].eq(YES), df[coluna].eq(NO)
        validas = int((sim | nao).sum())
        p, lo, hi = rs.wilson_ci(int(sim.sum()), validas)
        linhas.append({
            "rotulo": rotulo, "coluna": coluna, "sim": int(sim.sum()), "nao": int(nao.sum()),
            "nao_informado": len(df) - validas, "pct_nao_informado": 1 - validas / len(df) if len(df) else np.nan,
            "p": p, "ic_inf": lo, "ic_sup": hi, "p_sobre_total": sim.mean() if len(df) else np.nan,
        })
    return pd.DataFrame(linhas)


def distribuicao(serie: pd.Series, rotulos: dict[str, str], ignorados=NAO_INFORMADO, nao_se_aplica=NAO_SE_APLICA) -> pd.DataFrame:
    """Frequência por categoria, com percentual sobre o total e sobre as respostas válidas."""
    s = serie.fillna("").astype(str)
    categoria = s.map(rotulos)
    categoria = categoria.where(categoria.notna(), np.where(
        s.isin(ignorados), "Ignorado/vazio", np.where(s.isin(nao_se_aplica), "Não se aplica", "Código não previsto")))
    contagem = categoria.value_counts()
    ordem = [r for r in rotulos.values() if r in contagem] + [
        r for r in ["Não se aplica", "Ignorado/vazio", "Código não previsto"] if r in contagem]
    contagem = contagem.reindex(ordem)
    validas = contagem.reindex(list(rotulos.values())).dropna()
    return pd.DataFrame({
        "categoria": contagem.index, "n": contagem.values.astype(int),
        "pct_total": contagem.values / len(s),
        "pct_validas": [contagem[c] / validas.sum() if c in validas.index else np.nan for c in contagem.index],
    })


def completude(df: pd.DataFrame, colunas: list[str]) -> pd.DataFrame:
    """Percentual de 'ignorado' ou vazio por variável (completude da ficha)."""
    linhas = []
    for coluna in colunas:
        if coluna in df:
            ignorados = IGNORADOS_ESPECIFICOS.get(coluna, NAO_INFORMADO)
            linhas.append({"coluna": coluna, "pct_ignorado_ou_vazio": df[coluna].isin(ignorados).mean()})
    return pd.DataFrame(linhas).sort_values("pct_ignorado_ou_vazio", ascending=False)


def completude_por_ano(df: pd.DataFrame, colunas: list[str]) -> pd.DataFrame:
    """Evolução anual do percentual de ignorado/vazio: mudanças de preenchimento alteram as séries."""
    presentes = [c for c in colunas if c in df]
    return pd.DataFrame({
        c: df[c].isin(IGNORADOS_ESPECIFICOS.get(c, NAO_INFORMADO)).groupby(df["ano_analitico"]).mean()
        for c in presentes
    })


def _binaria(df: pd.DataFrame, nome: str) -> tuple[pd.Series, pd.Series]:
    """(valor booleano, resposta válida) de uma flag SINAN ou de um campo derivado."""
    if nome == "vinculo_intimo":
        return df["grupo_vinculo"].eq("Parceiro ou ex-parceiro íntimo"), df["grupo_vinculo"].ne("Não informado")
    if nome == "residencia":
        return df["residencia"], ~df["LOCAL_OCOR"].isin(IGNORADOS_ESPECIFICOS["LOCAL_OCOR"])
    return df[nome].eq(YES), df[nome].isin([YES, NO])


def associacoes(df: pd.DataFrame, pares=ASSOCIACOES, estrato="faixa_etaria") -> pd.DataFrame:
    """Razões de prevalência brutas e ajustadas (Mantel-Haenszel) entre respostas válidas."""
    linhas = []
    for exposicao, desfecho, rotulo in pares:
        if not {exposicao, desfecho}.issubset(set(df.columns) | {"vinculo_intimo"}):
            continue
        exp, exp_ok = _binaria(df, exposicao)
        out, out_ok = _binaria(df, desfecho)
        validos = exp_ok & out_ok & df[estrato].notna()
        sub = pd.DataFrame({"exp": exp, "out": out, "estrato": df[estrato]}).loc[validos]
        b = rs.razao_prevalencia(sub, "exp", "out")
        a = rs.razao_prevalencia_mh(sub, "exp", "out", "estrato")
        linhas.append({
            "rotulo": rotulo, "n_validos": len(sub), "p_expostos": b["p_expostos"], "p_nao_expostos": b["p_nao_expostos"],
            "bruta_rp": b["rp"], "bruta_inf": b["ic_inf"], "bruta_sup": b["ic_sup"],
            "ajustada_rp": a["rp"], "ajustada_inf": a["ic_inf"], "ajustada_sup": a["ic_sup"],
        })
    return pd.DataFrame(linhas)


def distribuicao_calendario(datas: pd.Series, chave: str, ano: int, dias_excluidos=()) -> tuple[pd.DataFrame, dict]:
    """Como rs.distribuicao_calendario, mas no ano civil inteiro e descontando dias excluídos do esperado.

    Necessário porque as datas imputadas (dia 1) são retiradas do observado; sem descontá-las
    do número de dias, as segundas-feiras e os meses perderiam ocorrências sem perder dias.
    """
    from scipy import stats
    dias = pd.date_range(f"{ano}-01-01", f"{ano}-12-31").difference(pd.DatetimeIndex(dias_excluidos))
    datas = pd.to_datetime(datas)
    datas = datas[datas.dt.normalize().isin(dias)]
    if chave == "dia_semana":
        rotulo, rotulo_dias, nomes = datas.dt.weekday, dias.weekday, rs.DIAS_SEMANA
    else:
        rotulo, rotulo_dias, nomes = datas.dt.month - 1, dias.month - 1, rs.MESES
    n_dias = pd.Series(1, index=rotulo_dias).groupby(level=0).sum()
    obs = rotulo.value_counts().reindex(n_dias.index, fill_value=0)
    esperado = n_dias / n_dias.sum() * obs.sum()
    qui2, p = stats.chisquare(obs.values, esperado.values)
    tabela = pd.DataFrame({
        "categoria": [nomes[i] for i in n_dias.index], "dias": n_dias.values, "observado": obs.values,
        "esperado": esperado.values, "media_diaria": obs.values / n_dias.values,
    })
    tabela["razao_obs_esp"] = tabela["observado"] / tabela["esperado"]
    return tabela, {"qui2": qui2, "gl": len(obs) - 1, "p": p}


def atraso_notificacao(df: pd.DataFrame) -> dict[str, float]:
    """Dias entre a ocorrência e a notificação; negativos são inconsistências de data."""
    d = df["atraso_notificacao_dias"].dropna().astype(float)
    validos = d[d >= 0]
    return {
        "n": len(d), "negativos": int((d < 0).sum()), "mediana": validos.median(), "p90": validos.quantile(0.9),
        "mesmo_dia": (validos == 0).mean(), "ate_7_dias": (validos <= 7).mean(), "mais_30_dias": (validos > 30).mean(),
    }


# ---------- Execução ----------

def _salvar(objeto, pasta: Path, nome: str) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    if isinstance(objeto, pd.DataFrame):
        objeto.to_csv(pasta / f"{nome}.csv", index=False, encoding="utf-8-sig")
    else:
        objeto.savefig(pasta / f"{nome}.png")
        plt.close(objeto)


def gerar_eda_sinan(entrada: Path = SINAN_RAW_PATH, saida: Path = OUTPUT_DIR, ano: int = 2024,
                    coorte: str = "coorte_pmdf_primaria") -> Path:
    """Gera tabelas (CSV), figuras (PNG) e um resumo em Markdown da coorte SINAN."""
    COLORS = set_report_theme()
    saida = Path(saida)
    tabelas, figuras = saida / "tabelas", saida / "figuras"
    tratada, qualidade, base = preparar_coorte(entrada, coorte)
    if base.empty:
        raise ValueError(f"A coorte {coorte} está vazia; confira o arquivo SINAN.")
    foco = base.loc[base["ano_analitico"].eq(ano)].copy()
    N, N_foco = len(base), len(foco)
    ausentes = sorted(c for c in [*FORMAS_VIOLENCIA, *MEIOS_AGRESSAO, *VINCULOS, *CATEGORIAS, "NU_IDADE_N", "HORA_OCOR", "ID_UNIDADE"]
                      if c not in base)
    resumo = [
        f"# Análise exploratória — SINAN, violência contra a mulher no DF", "",
        f"Coorte `{coorte}`: {fn(N)} notificações de {int(base['ano_analitico'].min())} a {int(base['ano_analitico'].max())}; "
        f"{fn(N_foco)} em {ano} (ano de foco, comparável à PMDF).", "",
        "Percentuais de flags SINAN são calculados entre respostas válidas (sim/não), salvo indicação; "
        "o peso do ignorado/vazio é reportado ao lado.", "",
    ]
    if ausentes:
        resumo += [f"Campos ausentes na exportação (análises correspondentes omitidas): {', '.join(ausentes)}.", ""]

    # 1. Qualidade e completude
    _salvar(qualidade, tabelas, "01_qualidade_base")
    campos = [*FORMAS_VIOLENCIA, *MEIOS_AGRESSAO, *CATEGORIAS, "AUTOR_ALCO", "OUT_VEZES", "DEF_TRANS"]
    comp = completude(foco, campos)
    _salvar(comp, tabelas, "02_completude_ano_foco")
    _salvar(completude_por_ano(base, ["CS_RACA", "CS_ESCOL_N", "AUTOR_ALCO", "OUT_VEZES", "LOCAL_OCOR", "VIOL_PSICO"]).reset_index(),
            tabelas, "03_completude_por_ano")
    atraso = atraso_notificacao(foco)
    fonte_data = foco["fonte_data_analitica"].value_counts(normalize=True)
    q = qualidade.set_index("indicador")["valor"]
    resumo += [
        "## 1. Dados e qualidade", "",
        f"- Base bruta: {fn(q['linhas_brutas'])} linhas; {fn(q['duplicatas_exatas'])} duplicatas exatas; "
        f"{fn(q['data_ocorrencia_ausente_ou_invalida'])} sem data de ocorrência válida.",
        f"- Em {ano}, {fp(fonte_data.get('notificacao', 0))} das notificações usam a data de notificação por falta da data de ocorrência; "
        "essas ficam fora das análises de dia da semana e hora.",
        f"- Atraso entre ocorrência e notificação: mediana de {fn(atraso['mediana'])} dias (p90 = {fn(atraso['p90'])}); "
        f"{fp(atraso['mesmo_dia'])} no mesmo dia, {fp(atraso['mais_30_dias'])} após 30 dias; {fn(atraso['negativos'])} com datas invertidas.",
    ]
    if "VIOL_SEXU" in foco:
        sex, outras = atraso_notificacao(foco.loc[foco["VIOL_SEXU"].eq(YES)]), atraso_notificacao(foco.loc[foco["VIOL_SEXU"].eq(NO)])
        resumo.append(f"- Notificação após 30 dias: {fp(sex['mais_30_dias'])} na violência sexual (mediana de {fn(sex['mediana'])} dias) "
                      f"contra {fp(outras['mais_30_dias'])} nas demais (mediana de {fn(outras['mediana'])} dias), compatível com revelação tardia.")
    proximo = base["data_notificacao"].dt.year.gt(ano) & base["ano_analitico"].eq(ano)
    resumo.append(f"- {fp(proximo.sum() / N_foco)} das ocorrências de {ano} só foram notificadas no ano seguinte; "
                  "por isso o ano mais recente da série tende a estar subestimado.")
    if not comp.empty:
        piores = comp.head(5)
        resumo.append("- Campos com mais ignorado/vazio em " + str(ano) + ": "
                      + "; ".join(f"{r.coluna} ({fp(r.pct_ignorado_ou_vazio)})" for r in piores.itertuples()) + ".")
    resumo.append("")

    # 2. Série histórica
    anual = base.groupby("ano_analitico").size().rename("notificacoes").reset_index()
    anual["variacao_pct"] = anual["notificacoes"].pct_change()
    formas_ano = pd.DataFrame({
        rotulo: base[col].eq(YES).groupby(base["ano_analitico"]).sum() / base[col].isin([YES, NO]).groupby(base["ano_analitico"]).sum()
        for col, rotulo in [("VIOL_FISIC", "Física"), ("VIOL_PSICO", "Psicológica/moral"), ("VIOL_SEXU", "Sexual")] if col in base
    })
    anual = anual.merge(formas_ano.add_prefix("p_").reset_index(), on="ano_analitico", how="left")
    _salvar(anual, tabelas, "04_serie_anual")
    anos = [str(a) for a in anual["ano_analitico"]]
    _salvar(rf.linhas_comparadas(anos, {"Notificações": anual["notificacoes"].tolist()}, COLORS,
                                 "Notificações de violência contra a mulher, DF", "Notificações por ano"), figuras, "01_serie_anual")
    if not formas_ano.empty:
        _salvar(rf.linhas_comparadas(anos, {k: (v * 100).tolist() for k, v in formas_ano.items()}, COLORS,
                                     "Formas de violência ao longo dos anos", "% das respostas válidas"), figuras, "02_formas_por_ano")
    pico = anual.loc[anual["notificacoes"].idxmax()]
    resumo += [
        "## 2. Série histórica", "",
        f"- De {fn(anual['notificacoes'].iloc[0])} notificações em {anos[0]} para {fn(anual['notificacoes'].iloc[-1])} em {anos[-1]}; "
        f"pico em {int(pico['ano_analitico'])} ({fn(pico['notificacoes'])}).",
        "- Crescimento de notificações reflete também a expansão da rede notificadora e da obrigatoriedade; "
        "não é, por si só, aumento da violência. O último ano pode estar incompleto (dados preliminares).",
        "",
    ]

    # 3. Padrões temporais no ano de foco (apenas com data de ocorrência real)
    com_data = foco.loc[foco["fonte_data_analitica"].eq("ocorrencia")]
    dias_imputados = pd.date_range(f"{ano}-01-01", f"{ano}-12-31", freq="MS")
    datas = com_data.loc[~com_data["dia_imputado"], "data_ocorrencia"]
    # O mês continua confiável no dia 1 dos demais meses; 01/01 pode ser apenas o ano.
    datas_mes = com_data.loc[com_data["data_ocorrencia"].dt.strftime("%m%d").ne("0101"), "data_ocorrencia"]
    resumo += [f"## 3. Padrões temporais em {ano}", "",
               f"- Datas no dia 1 do mês ({fp(com_data['dia_imputado'].mean())} das datas de ocorrência de {ano}) foram tratadas como "
               "imputadas e excluídas das análises por dia da semana e feriado; 01/01 também foi excluído da análise mensal."]
    if len(datas) > 30:
        tab_mes, teste_mes = distribuicao_calendario(datas_mes, "mes", ano, dias_excluidos=[pd.Timestamp(f"{ano}-01-01")])
        tab_sem, teste_sem = distribuicao_calendario(datas, "dia_semana", ano, dias_excluidos=dias_imputados)
        _salvar(tab_mes, tabelas, "05_mes_ano_foco")
        _salvar(tab_sem, tabelas, "06_dia_semana_ano_foco")
        _salvar(rf.barras_media_diaria(tab_sem, COLORS, f"Notificações por dia de ocorrência, segundo o dia da semana ({ano})",
                                       destaque=["Sábado", "Domingo"], ylabel="Notificações por dia (média)"), figuras, "03_dia_semana")
        fds = tab_sem["categoria"].isin(["Sábado", "Domingo"])
        rr_fds = rs.razao_taxas(tab_sem.loc[fds, "observado"].sum(), tab_sem.loc[fds, "dias"].sum(),
                                tab_sem.loc[~fds, "observado"].sum(), tab_sem.loc[~fds, "dias"].sum())
        mes_max = tab_mes.loc[tab_mes["razao_obs_esp"].idxmax()]
        resumo += [
            f"- Mês: distribuição {'não ' if teste_mes['p'] < 0.05 else ''}uniforme (qui² = {fn(teste_mes['qui2'], 1)}; "
            f"p {'< 0,001' if teste_mes['p'] < 0.001 else '= ' + fn(teste_mes['p'], 3)}); maior volume relativo em {mes_max['categoria']} "
            f"({fp(mes_max['razao_obs_esp'] - 1, 0)} acima do esperado).",
            f"- Dia da semana: qui² = {fn(teste_sem['qui2'], 1)} (p {'< 0,001' if teste_sem['p'] < 0.001 else '= ' + fn(teste_sem['p'], 3)}). "
            f"Fim de semana: {fn(rr_fds['rr'], 2)} vezes a média diária dos dias úteis "
            f"(IC 95%: {fn(rr_fds['ic_inf'], 2)}–{fn(rr_fds['ic_sup'], 2)}).",
        ]
        # Lacunas na data de notificação do próprio ano (análogo à falha de registro de setembro na PMDF).
        notificadas = base.loc[base["data_notificacao"].dt.year.eq(ano), "data_notificacao"]
        lacunas = rs.lacunas_de_registro(notificadas, minimo_dias=4)
        resumo.append(f"- Lacunas de 4+ dias sem nenhuma notificação em {ano}: "
                      + (", ".join(f"{a:%d/%m/%Y}–{b:%d/%m/%Y}" for a, b, _ in lacunas) if lacunas else "nenhuma") + ".")
        if ano == 2024:
            tab_fer, ef_fer = rs.efeito_datas(datas, rs.FERIADOS_2024, dias_excluidos=dias_imputados)
            _, ef_util = rs.efeito_datas(datas, {d: n for d, n in rs.FERIADOS_2024.items() if d.weekday() < 5},
                                         dias_excluidos=dias_imputados)
            _salvar(tab_fer, tabelas, "07_feriados_2024")
            resumo.append(f"- Feriados (exceto 01/01, imputado): razão observado/esperado de {fn(ef_fer['razao'], 2)} "
                          f"(IC 95%: {fn(ef_fer['ic_inf'], 2)}–{fn(ef_fer['ic_sup'], 2)}); em dias úteis, {fn(ef_util['razao'], 2)} "
                          f"(IC 95%: {fn(ef_util['ic_inf'], 2)}–{fn(ef_util['ic_sup'], 2)}).")
    hora_informada = com_data["hora"].notna()
    com_hora = com_data.loc[hora_informada & ~com_data["hora_padrao"] & ~com_data["dia_imputado"]]
    if len(com_hora) > 30 and len(datas) > 30:
        dias_sem = tab_sem.set_index("categoria")["dias"]
        matriz = (pd.crosstab(com_hora["data_ocorrencia"].dt.weekday.map(dict(enumerate(rs.DIAS_SEMANA))), com_hora["hora"].astype(int))
                  .reindex(index=rs.DIAS_SEMANA, columns=range(24), fill_value=0).div(dias_sem, axis=0))
        _salvar(matriz.reset_index(names="dia_semana"), tabelas, "08_hora_dia_semana")
        _salvar(rf.heatmap_hora_dia(matriz, COLORS, f"Notificações por hora e dia da semana da ocorrência ({ano})",
                                    legenda="Notificações por dia"), figuras, "04_hora_dia")
        noite = com_hora["hora"].between(20, 23).mean()
        resumo.append(f"- Hora informada em {fp(hora_informada.sum() / N_foco)} das notificações; {fp(com_data.loc[hora_informada, 'hora_padrao'].mean())} "
                      f"delas às 00:00 (valor-padrão, excluído). Entre as demais: pico às {int(com_hora['hora'].mode().iat[0])}h; "
                      f"{fp(noite)} entre 20h e 23h (16,7% sob distribuição uniforme).")
    resumo.append("")

    # 4. Perfil da vítima
    faixa = foco["faixa_etaria"].value_counts(sort=False)
    tab_idade = pd.DataFrame({"faixa_etaria": faixa.index.astype(str), "n": faixa.values, "pct_validas": faixa.values / faixa.sum()})
    _salvar(tab_idade, tabelas, "09_faixa_etaria")
    _salvar(rf.barras_ordenadas(tab_idade["faixa_etaria"], tab_idade["pct_validas"], COLORS, f"Faixa etária das vítimas ({ano})"),
            figuras, "05_faixa_etaria")
    resumo += ["## 4. Perfil da vítima", "",
               f"- Idade: mediana de {fn(foco['idade'].median())} anos; {fp(foco['idade'].lt(18).mean())} com menos de 18 anos; "
               f"idade ausente em {fp(foco['idade'].isna().mean())}."]
    perfis = {}
    for coluna, (titulo, rotulos) in CATEGORIAS.items():
        if coluna not in foco:
            continue
        t = distribuicao(foco[coluna], rotulos, IGNORADOS_ESPECIFICOS.get(coluna, NAO_INFORMADO),
                         NAO_SE_APLICA | NAO_SE_APLICA_ESPECIFICOS.get(coluna, set()))
        perfis[coluna] = t
        _salvar(t, tabelas, f"10_{coluna.lower()}")
    if "CS_RACA" in perfis:
        r = perfis["CS_RACA"].set_index("categoria")["pct_validas"]
        ign = perfis["CS_RACA"].set_index("categoria")["pct_total"].get("Ignorado/vazio", 0)
        resumo.append(f"- Raça/cor: mulheres negras (pretas e pardas) são {fp(r.get('Preta', 0) + r.get('Parda', 0))} "
                      f"das respostas válidas; ignorado em {fp(ign)}.")
    if "CS_ESCOL_N" in perfis:
        e = perfis["CS_ESCOL_N"].set_index("categoria")["pct_validas"]
        ate_fund = e.reindex(list(CATEGORIAS["CS_ESCOL_N"][1].values())[:5]).sum()
        resumo.append(f"- Escolaridade: {fp(ate_fund)} das respostas válidas têm até o fundamental completo.")
    deficiencia = tabela_flags(foco, {"DEF_TRANS": FLAGS_CONTEXTO["DEF_TRANS"]})
    if not deficiencia.empty:
        resumo.append(f"- Deficiência ou transtorno: {fp(deficiencia['p'].iat[0])} das respostas válidas.")
    resumo.append("")

    # 5. Formas de violência e meios de agressão
    domestico = foco.loc[foco["recorte_domestico"]]
    formas = tabela_flags(foco, FORMAS_VIOLENCIA)
    formas_dom = tabela_flags(domestico, FORMAS_VIOLENCIA)[["coluna", "p", "ic_inf", "ic_sup"]].add_suffix("_recorte_domestico")
    formas = formas.merge(formas_dom, left_on="coluna", right_on="coluna_recorte_domestico", how="left").drop(columns="coluna_recorte_domestico")
    _salvar(formas, tabelas, "11_formas_violencia")
    _salvar(rf.barras_prevalencia(formas.loc[formas["sim"] > 0], COLORS, f"Formas de violência notificadas ({ano})"), figuras, "06_formas_violencia")
    cols_formas = [c for c in FORMAS_VIOLENCIA if c in foco]
    flags_formas = foco[cols_formas].eq(YES).rename(columns=FORMAS_VIOLENCIA)
    pares, n_tipos = rs.coocorrencia(flags_formas, list(flags_formas.columns))
    _salvar(pares.reset_index(names="forma"), tabelas, "12_coocorrencia_formas")
    meios = tabela_flags(foco, MEIOS_AGRESSAO)
    _salvar(meios, tabelas, "13_meios_agressao")
    if not meios.empty:
        _salvar(rf.barras_prevalencia(meios.loc[meios["sim"] > 0], COLORS, f"Meios de agressão ({ano})"), figuras, "07_meios_agressao")
    pf = formas.set_index("rotulo")
    resumo += ["## 5. Formas de violência e meios de agressão", ""]
    for rotulo in ["Física", "Psicológica/moral", "Sexual"]:
        if rotulo in pf.index:
            r = pf.loc[rotulo]
            resumo.append(f"- {rotulo}: {fp(r['p'])} (IC 95%: {fp(r['ic_inf'])}–{fp(r['ic_sup'])}); "
                          f"no recorte doméstico adulto, {fp(r['p_recorte_domestico'])}; não informado em {fp(r['pct_nao_informado'])}.")
    resumo.append(f"- {fp(n_tipos[n_tipos.index >= 2].sum() / N_foco)} das notificações registram duas ou mais formas.")
    if {"Física", "Psicológica/moral"}.issubset(pares.index):
        resumo.append(f"- Física + psicológica/moral: {fn(pares.loc['Física', 'Psicológica/moral'])} notificações.")
    if not meios.empty:
        top = meios.sort_values("p", ascending=False).head(3)
        resumo.append("- Meios mais frequentes: " + "; ".join(f"{r.rotulo} ({fp(r.p)})" for r in top.itertuples()) + ".")
    resumo.append(f"- Recorte doméstico adulto (≥ 18 anos, autor parceiro/ex-parceiro ou familiar): {fn(len(domestico))} notificações "
                  f"({fp(len(domestico) / N_foco)}). É o subconjunto mais próximo do escopo da PMDF.")
    if "VIOL_SEXU" in foco:
        sexual = foco.loc[foco["VIOL_SEXU"].eq(YES)]
        tipos_sex = tabela_flags(sexual, VIOLENCIA_SEXUAL)
        _salvar(tipos_sex, tabelas, "14_tipos_violencia_sexual")
        resumo.append(f"- Violência sexual: {fp(sexual['idade'].lt(18).mean())} das vítimas têm menos de 18 anos"
                      + (f"; estupro em {fp(tipos_sex.set_index('coluna')['p'].get('SEX_ESTUPR', np.nan))} dos casos." if not tipos_sex.empty else "."))
    resumo.append("")

    # 6. Autor e vínculo
    vinculo = foco["grupo_vinculo"].value_counts()
    tab_vinculo = pd.DataFrame({"grupo": vinculo.index, "n": vinculo.values, "pct_total": vinculo.values / N_foco})
    _salvar(tab_vinculo, tabelas, "15_grupo_vinculo")
    _salvar(tabela_flags(foco, VINCULOS), tabelas, "16_vinculos_detalhados")
    informados = tab_vinculo.loc[tab_vinculo["grupo"].ne("Não informado")]
    _salvar(rf.barras_horizontais(informados["grupo"], informados["n"] / informados["n"].sum(), COLORS,
                                  f"Vínculo do autor com a vítima ({ano})"), figuras, "08_vinculo")
    contexto = tabela_flags(foco, {k: v for k, v in FLAGS_CONTEXTO.items() if k != "LES_AUTOP"})
    _salvar(contexto, tabelas, "17_fatores_contexto")
    resumo += ["## 6. Autor e vínculo", ""]
    for grupo in ["Parceiro ou ex-parceiro íntimo", "Familiar", "Desconhecido(a)"]:
        if grupo in vinculo.index:
            resumo.append(f"- {grupo}: {fp(vinculo[grupo] / informados['n'].sum())} das notificações com vínculo informado.")
    resumo.append(f"- Nenhum vínculo marcado (todos 'não' ou ignorados) em {fp(vinculo.get('Não informado', 0) / N_foco)}.")
    if "AUTOR_SEXO" in perfis:
        resumo.append(f"- Autor do sexo masculino em {fp(perfis['AUTOR_SEXO'].set_index('categoria')['pct_validas'].get('Masculino', np.nan))} "
                      "das respostas válidas.")
    for r in contexto.itertuples():
        resumo.append(f"- {r.rotulo}: {fp(r.p)} das respostas válidas (não informado em {fp(r.pct_nao_informado)}).")
    resumo.append("")

    # 7. Local e encaminhamentos
    resumo += ["## 7. Local e encaminhamentos", ""]
    if "LOCAL_OCOR" in perfis:
        loc = perfis["LOCAL_OCOR"].set_index("categoria")
        resumo.append(f"- Residência: {fp(loc['pct_validas'].get('Residência', np.nan))} das respostas válidas; "
                      f"via pública: {fp(loc['pct_validas'].get('Via pública', np.nan))}.")
    colunas_enc = {c: r for c, r in ENCAMINHAMENTOS.items() if c in foco}
    encaminhamentos = tabela_flags(foco, colunas_enc)
    # Campos da ficha anterior vêm vazios nos anos recentes; ficam de fora em vez de aparecer como 0%.
    encaminhamentos = encaminhamentos.loc[encaminhamentos["sim"] + encaminhamentos["nao"] > 0]
    if not encaminhamentos.empty:
        _salvar(encaminhamentos, tabelas, "18_encaminhamentos")
        top = encaminhamentos.sort_values("p", ascending=False).head(3)
        resumo.append("- Encaminhamentos mais frequentes: " + "; ".join(f"{r.rotulo} ({fp(r.p)})" for r in top.itertuples()) + ".")
    resumo.append("")

    # 8. Associações (bruta e ajustada por faixa etária)
    assoc = associacoes(foco)
    _salvar(assoc, tabelas, "19_associacoes")
    resumo += ["## 8. Associações", "",
               "Razões de prevalência entre respostas válidas, brutas e ajustadas por faixa etária (Mantel-Haenszel). "
               "Transversais; não autorizam leitura causal.", ""]
    if not assoc.empty:
        _salvar(rf.forest(assoc.dropna(subset=["bruta_rp"]), COLORS, f"Associações entre fatores e formas de violência ({ano})",
                          nomes=("Bruta", "Ajustada por faixa etária")), figuras, "09_associacoes")
        for r in assoc.itertuples():
            resumo.append(f"- {r.rotulo}: RP bruta {fn(r.bruta_rp, 2)} ({fn(r.bruta_inf, 2)}–{fn(r.bruta_sup, 2)}); "
                          f"ajustada {fn(r.ajustada_rp, 2)} ({fn(r.ajustada_inf, 2)}–{fn(r.ajustada_sup, 2)}); n = {fn(r.n_validos)}.")
    resumo.append("")

    # 9. Concentração por unidade notificadora (análogo à concentração espacial da PMDF)
    if "ID_UNIDADE" in foco:
        unidades = foco["ID_UNIDADE"].replace("", np.nan).dropna().value_counts()
        conc, info = rs.concentracao(unidades.values)
        _salvar(pd.DataFrame([{"fracao_unidades": k, "fracao_notificacoes": v} for k, v in conc.items()]), tabelas, "20_concentracao_unidades")
        _salvar(rf.curva_concentracao(unidades.values, COLORS, f"Concentração das notificações por unidade notificadora ({ano})",
                                      unidade="unidades", evento="notificações", xlabel="Unidades notificadoras (da mais à menos ativa)"),
                figuras, "10_concentracao_unidades")
        resumo += ["## 9. Concentração por unidade notificadora", "",
                   f"- {fn(info['unidades'])} unidades notificaram em {ano}; {fn(info['unidades_para_50pct'])} "
                   f"({fp(info['unidades_para_50pct'] / info['unidades'])}) concentram metade das notificações (Gini = {fn(info['gini'], 2)}).",
                   "- A concentração reflete onde há serviço que notifica (hospitais de referência, centros especializados), "
                   "não onde a violência ocorre.", ""]

    saida.mkdir(parents=True, exist_ok=True)
    (saida / "resumo_eda_sinan.md").write_text("\n".join(resumo) + "\n", encoding="utf-8")
    return saida


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--entrada", type=Path, default=SINAN_RAW_PATH, help="CSV SINAN bruto")
    parser.add_argument("--saida", type=Path, default=OUTPUT_DIR, help="pasta de saída")
    parser.add_argument("--ano", type=int, default=2024, help="ano de foco (padrão: 2024, o mesmo da PMDF)")
    parser.add_argument("--coorte", default="coorte_pmdf_primaria",
                        choices=["coorte_pmdf_primaria", "coorte_pmdf_sensibilidade"])
    args = parser.parse_args()
    destino = gerar_eda_sinan(args.entrada, args.saida, args.ano, args.coorte)
    print(f"EDA SINAN gerada em: {destino}")


if __name__ == "__main__":
    main()
