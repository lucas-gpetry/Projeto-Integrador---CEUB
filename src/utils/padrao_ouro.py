"""Padrão-ouro das flags textuais da PMDF: amostra estratificada, rotulagem dupla e métricas.

A rotulagem é feita pelo grupo, em planilha local, sem plataforma ou API externa (LGPD).
Os testes deste módulo usam só texto sintético.
"""

import subprocess
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Alignment, Font
from openpyxl.worksheet.datavalidation import DataValidation

from src.utils.report_stats import wilson_ci

ROTULOS = {
    "v_fisica": "Violência física",
    "v_psicologica": "Violência psicológica",
    "v_moral": "Violência moral",
    "v_patrimonial": "Violência patrimonial",
    "v_sexual": "Violência sexual",
    "flag_alcool": "Álcool (autor)",
    "flag_drogas": "Drogas (autor)",
    "flag_arma_fogo": "Arma de fogo",
    "flag_arma_branca": "Arma branca",
    "flag_tornozeleira": "Tornozeleira",
    "flag_medida_protetiva": "Medida protetiva",
    "flag_separacao": "Separação ou ex-parceiro",
    "flag_filhos": "Filhos",
}
FLAGS = list(ROTULOS)
SIM_NAO = ("sim", "nao")
DESFECHOS = ("encaminhado_dp", "resolvido_local", "nao_identificado")
ANOTADORES = tuple("ABCDE")
SEMENTE = 20241231
LIMITE_RARO = 0.10
PISO_RARO = 25
PISO_COMUM = 15
PISO_SEM_FLAG = 40

GUIA = [
    ("Guia de rotulagem", True),
    ("Sigilo", True),
    ("As narrativas têm dados pessoais. Mantenha esta planilha só no seu computador.", False),
    ("Não envie o arquivo por e-mail, mensagem ou nuvem, e não cole o texto em ferramentas online.", False),
    ("Não copie nomes, endereços ou trechos da narrativa para a coluna de comentário.", False),
    ("Como rotular", True),
    ("Preencha todas as colunas de cada linha só com o que está escrito na narrativa. Não consulte o outro anotador.", False),
    ("sim: o texto relata o fato como ocorrido, segundo a vítima, uma testemunha, o autor ou o policial. Não precisa estar comprovado.", False),
    ("nao: o fato não aparece, foi negado ou o termo tem outro sentido, como em \"isolou o local\" ou \"bateu na porta\".", False),
    ("Não avaliável: marque sim quando o texto não descreve o fato (texto curto, modelo padronizado ou remissão a outro documento) e deixe as demais colunas em branco.", False),
    ("Definições (Lei nº 11.340/2006, art. 7º, nas formas de violência)", True),
    ("Violência física: conduta que ofende a integridade ou a saúde corporal, como soco, chute, tapa, empurrão, enforcamento ou espancamento.", False),
    ("Violência psicológica: ameaça, humilhação, constrangimento, isolamento, perseguição, chantagem, insulto ou outra conduta que cause dano emocional ou controle a vítima.", False),
    ("Violência moral: calúnia, difamação ou injúria. Xingamento conta aqui e na psicológica.", False),
    ("Violência patrimonial: retenção, subtração ou destruição de objetos, documentos, bens ou valores da vítima.", False),
    ("Violência sexual: estupro, ato libidinoso ou outra conduta sexual sem consentimento, incluindo a importunação sexual.", False),
    ("Álcool (autor): consumo ou embriaguez do autor. Menção só à vítima ou a terceiros é nao.", False),
    ("Drogas (autor): uso de entorpecentes pelo autor.", False),
    ("Arma de fogo: uso ou ameaça com arma de fogo, como revólver, pistola ou disparo.", False),
    ("Arma branca: uso ou ameaça com faca, canivete, facão, tesoura ou similar.", False),
    ("Tornozeleira: autor sob monitoramento eletrônico.", False),
    ("Medida protetiva: qualquer menção, vigente, solicitada ou descumprida.", False),
    ("Separação ou ex-parceiro: término ou separação do relacionamento, ou autor citado como ex-parceiro.", False),
    ("Filhos: filhos da vítima ou do casal presentes ou envolvidos na ocorrência.", False),
    ("Desfecho", True),
    ("encaminhado_dp: a PM conduziu alguém à delegacia ou houve prisão.", False),
    ("resolvido_local: orientação, advertência ou acordo, sem condução. Inclui orientar a vítima a procurar a delegacia.", False),
    ("nao_identificado: o texto não informa o que foi feito.", False),
]


def saida_ignorada_pelo_git(caminho, raiz=None):
    """Indica se o Git ignora o diretório: as planilhas têm narrativas e não podem entrar em commit."""
    teste = Path(caminho) / "verificacao.xlsx"
    return subprocess.run(["git", "check-ignore", "-q", str(teste)], cwd=raiz, check=False).returncode == 0


def atribuir_estratos(predicoes):
    """Cada histórico entra no estrato da sua flag positiva mais rara, ou em 'nenhuma_flag'."""
    por_raridade = predicoes[FLAGS].sum().sort_values(kind="stable").index
    estrato = pd.Series("nenhuma_flag", index=predicoes.index, dtype=object)
    for flag in reversed(por_raridade):
        estrato[predicoes[flag]] = flag
    return estrato


def pisos_por_estrato(predicoes):
    """Mínimo de sorteios por estrato: mais nas flags raras e em 'nenhuma_flag', de onde vêm os falsos negativos."""
    taxas = predicoes[FLAGS].mean()
    pisos = {flag: PISO_RARO if taxas[flag] < LIMITE_RARO else PISO_COMUM for flag in FLAGS}
    pisos["nenhuma_flag"] = PISO_SEM_FLAG
    return pd.Series(pisos)


def alocar_estratos(tamanhos, total, pisos=10):
    """Aloca pela raiz quadrada do tamanho (entre o proporcional e o igual), com piso e teto em cada estrato."""
    if total > tamanhos.sum():
        raise ValueError("A amostra é maior que a base.")
    pisos = np.minimum(pd.Series(pisos, index=tamanhos.index), tamanhos)
    alvo = np.sqrt(tamanhos.astype(float))
    n = np.minimum(np.maximum((alvo / alvo.sum() * total).round().astype(int), pisos), tamanhos)
    while n.sum() != total:
        if n.sum() < total:
            livres = n.index[n < tamanhos]
            n[(alvo[livres] / n[livres].clip(lower=1)).idxmax()] += 1
        else:
            redutiveis = n.index[n > pisos]
            if redutiveis.empty:
                raise ValueError("Os pisos por estrato não cabem no total da amostra.")
            n[(n[redutiveis] / alvo[redutiveis]).idxmax()] -= 1
    return n


def sortear_amostra(predicoes, total=300, semente=SEMENTE):
    """Amostra aleatória simples dentro de cada estrato; o peso é o inverso da probabilidade de seleção."""
    estratos = atribuir_estratos(predicoes)
    tamanhos = estratos.value_counts().sort_index()
    alocacao = alocar_estratos(tamanhos, total, pisos_por_estrato(predicoes).reindex(tamanhos.index))
    rng = np.random.default_rng(semente)
    partes = []
    for estrato in tamanhos.index:
        indices = estratos.index[estratos == estrato].to_numpy()
        escolhidos = rng.choice(indices, size=int(alocacao[estrato]), replace=False)
        partes.append(pd.DataFrame({"indice_base": escolhidos, "estrato": estrato, "peso": tamanhos[estrato] / alocacao[estrato]}))
    return pd.concat(partes, ignore_index=True)


def distribuir_pares(amostra, anotadores=ANOTADORES, semente=SEMENTE):
    """Dá dois anotadores a cada histórico, com todos os pares igualmente representados em cada estrato."""
    rng = np.random.default_rng(semente)
    pares = list(combinations(anotadores, 2))
    ordem = amostra.assign(_acaso=rng.random(len(amostra))).sort_values(["estrato", "_acaso"]).reset_index(drop=True)
    sorteio = rng.permutation(len(pares))
    ordem["anotador_1"] = [pares[sorteio[i % len(pares)]][0] for i in range(len(ordem))]
    ordem["anotador_2"] = [pares[sorteio[i % len(pares)]][1] for i in range(len(ordem))]
    ordem = ordem.drop(columns="_acaso").sample(frac=1, random_state=semente).reset_index(drop=True)
    ordem.insert(0, "id_amostra", [f"N{i + 1:03d}" for i in range(len(ordem))])
    return ordem


def _texto_seguro(texto):
    """Tira caracteres que o Excel rejeita e garante que o texto não seja lido como fórmula."""
    return ILLEGAL_CHARACTERS_RE.sub(" ", str(texto))


def _aba_guia(planilha):
    aba = planilha.create_sheet("Guia", 0)
    aba.column_dimensions["A"].width = 130
    for linha, (texto, titulo) in enumerate(GUIA, start=1):
        celula = aba.cell(row=linha, column=1, value=texto)
        celula.alignment = Alignment(wrap_text=True, vertical="top")
        celula.font = Font(bold=titulo)


def _cabecalho(aba, titulos):
    for coluna, titulo in enumerate(titulos, start=1):
        celula = aba.cell(row=1, column=coluna, value=titulo)
        celula.font = Font(bold=True)
        celula.alignment = Alignment(wrap_text=True, vertical="top")
    aba.freeze_panes = "C2"


def _lista_suspensa(aba, valores, coluna, ultima_linha):
    validacao = DataValidation(type="list", formula1='"' + ",".join(valores) + '"', allow_blank=True)
    aba.add_data_validation(validacao)
    validacao.add(f"{coluna}2:{coluna}{ultima_linha}")


def gravar_planilha_anotador(caminho, linhas):
    """Grava a planilha de um anotador: id e narrativa, sem as predições das regras."""
    planilha = Workbook()
    aba = planilha.active
    aba.title = "Rotulos"
    _aba_guia(planilha)
    titulos = ["id_amostra", "historico", *ROTULOS.values(), "desfecho", "nao_avaliavel", "comentario"]
    _cabecalho(aba, titulos)
    for i, (id_amostra, historico) in enumerate(linhas, start=2):
        aba.cell(row=i, column=1, value=id_amostra)
        celula = aba.cell(row=i, column=2)
        celula.value = _texto_seguro(historico)
        celula.data_type = "s"
        celula.alignment = Alignment(wrap_text=True, vertical="top")
    aba.column_dimensions["A"].width = 11
    aba.column_dimensions["B"].width = 90
    ultima = max(len(linhas) + 1, 2)
    letras = [aba.cell(row=1, column=c).column_letter for c in range(1, len(titulos) + 1)]
    for letra in letras[2:2 + len(FLAGS)]:
        aba.column_dimensions[letra].width = 12
        _lista_suspensa(aba, SIM_NAO, letra, ultima)
    _lista_suspensa(aba, DESFECHOS, letras[2 + len(FLAGS)], ultima)
    _lista_suspensa(aba, SIM_NAO, letras[3 + len(FLAGS)], ultima)
    aba.column_dimensions[letras[2 + len(FLAGS)]].width = 18
    aba.column_dimensions[letras[-1]].width = 30
    planilha.active = planilha.sheetnames.index("Rotulos")
    planilha.save(caminho)


def ler_planilha_anotador(caminho, anotador):
    """Lê só os rótulos, em formato longo; nem a narrativa nem o comentário são carregados."""
    aba = load_workbook(caminho, read_only=True, data_only=True)["Rotulos"]
    linhas = aba.iter_rows(values_only=True)
    titulos = list(next(linhas))
    por_titulo = {titulo: coluna for coluna, titulo in ROTULOS.items()} | {"desfecho": "desfecho", "nao_avaliavel": "nao_avaliavel"}
    posicoes = {por_titulo[t]: i for i, t in enumerate(titulos) if t in por_titulo}
    id_pos = titulos.index("id_amostra")
    registros = []
    for linha in linhas:
        if linha[id_pos] is None:
            continue
        for coluna, pos in posicoes.items():
            valor = linha[pos]
            rotulo = "" if valor is None else str(valor).strip().lower()
            permitidos = DESFECHOS if coluna == "desfecho" else SIM_NAO
            if rotulo and rotulo not in permitidos:
                raise ValueError(f"Valor inválido em {Path(caminho).name}, {linha[id_pos]}, coluna {coluna}.")
            registros.append({"id_amostra": linha[id_pos], "coluna": coluna, "anotador": anotador, "rotulo": rotulo})
    return pd.DataFrame(registros)


def conferir_preenchimento(longo):
    """Conta, por anotador, as células em branco nas linhas que não foram marcadas como não avaliáveis."""
    nao_avaliaveis = set(map(tuple, longo.query("coluna == 'nao_avaliavel' and rotulo == 'sim'")[["id_amostra", "anotador"]].to_numpy()))
    obrigatorias = longo[longo["coluna"].ne("nao_avaliavel")]
    exigida = np.array([(i, a) not in nao_avaliaveis for i, a in zip(obrigatorias["id_amostra"], obrigatorias["anotador"])], dtype=bool)
    em_branco = obrigatorias[obrigatorias["rotulo"].eq("").to_numpy() & exigida]
    return em_branco.groupby("anotador").size().reindex(sorted(longo["anotador"].unique()), fill_value=0)


def consolidar(longo, adjudicacao=None):
    """Junta os dois rótulos: o acordo vale, a divergência vai para o terceiro integrante.

    Devolve o padrão-ouro em formato largo e a lista de divergências ainda sem decisão.
    """
    adjudicado = {} if adjudicacao is None else {(r.id_amostra, r.coluna): r.rotulo_final for r in adjudicacao.itertuples() if r.rotulo_final}
    dados = longo.assign(rotulo=lambda d: d["rotulo"].where(d["coluna"].ne("nao_avaliavel") | d["rotulo"].ne(""), "nao"))
    ouro, pendentes = {}, []
    for (id_amostra, coluna), grupo in dados.groupby(["id_amostra", "coluna"], sort=True):
        valores = [v for v in grupo["rotulo"] if v]
        if len(valores) == 2 and valores[0] == valores[1]:
            ouro[id_amostra, coluna] = valores[0]
        elif (id_amostra, coluna) in adjudicado:
            ouro[id_amostra, coluna] = adjudicado[id_amostra, coluna]
        else:
            pendentes.append({"id_amostra": id_amostra, "coluna": coluna, "rotulos": tuple(grupo["rotulo"])})
    largo = pd.Series(ouro, dtype=object).unstack() if ouro else pd.DataFrame()
    largo.index.name = "id_amostra"
    pendencias = pd.DataFrame(pendentes, columns=["id_amostra", "coluna", "rotulos"])
    # Em linha não avaliável por decisão final, as demais colunas não precisam de decisão.
    if not largo.empty and "nao_avaliavel" in largo:
        excluidas = set(largo.index[largo["nao_avaliavel"].eq("sim")])
        pendencias = pendencias[~pendencias["id_amostra"].isin(excluidas) | pendencias["coluna"].eq("nao_avaliavel")].reset_index(drop=True)
    return largo, pendencias


def kappa_cohen(a, b):
    """Kappa de Cohen entre dois anotadores, para qualquer número de categorias."""
    a, b = pd.Series(a).reset_index(drop=True), pd.Series(b).reset_index(drop=True)
    if a.empty:
        return float("nan")
    observado = (a == b).mean()
    categorias = set(a) | set(b)
    esperado = sum((a == c).mean() * (b == c).mean() for c in categorias)
    return float((observado - esperado) / (1 - esperado)) if esperado < 1 else float("nan")


def concordancia(longo):
    """Kappa e concordância simples por coluna, só nas linhas com os dois rótulos."""
    linhas = []
    dados = longo[longo["rotulo"].ne("")].sort_values("anotador")
    for coluna, grupo in dados.groupby("coluna"):
        pares = grupo.groupby("id_amostra")["rotulo"].agg(list)
        pares = pares[pares.map(len) == 2]
        a, b = pares.map(lambda p: p[0]), pares.map(lambda p: p[1])
        linhas.append({"coluna": coluna, "pares": len(pares), "concordancia": float((a == b).mean()) if len(pares) else float("nan"), "kappa": kappa_cohen(a, b)})
    return pd.DataFrame(linhas)


def tamanho_efetivo(pesos):
    """Tamanho efetivo de Kish: quanto a variação dos pesos reduz a informação da amostra."""
    pesos = np.asarray(pesos, float)
    return float(pesos.sum() ** 2 / (pesos**2).sum()) if pesos.size else 0.0


def _f1(predito, ouro, pesos):
    tp = pesos[predito & ouro].sum()
    denominador = 2 * tp + pesos[predito & ~ouro].sum() + pesos[~predito & ouro].sum()
    return 2 * tp / denominador if denominador else float("nan")


def ic_f1_bootstrap(predito, ouro, pesos, estratos, semente=SEMENTE, repeticoes=2000):
    """IC 95% do F1 por bootstrap dentro de cada estrato, respeitando o desenho da amostra."""
    predito, ouro, pesos, estratos = map(np.asarray, (predito, ouro, pesos, estratos))
    rng = np.random.default_rng(semente)
    grupos = [np.flatnonzero(estratos == e) for e in np.unique(estratos)]
    valores = np.empty(repeticoes)
    for r in range(repeticoes):
        idx = np.concatenate([rng.choice(g, g.size, replace=True) for g in grupos])
        valores[r] = _f1(predito[idx], ouro[idx], pesos[idx])
    return tuple(np.nanpercentile(valores, [2.5, 97.5]))


def _proporcao_ponderada(k, n, pesos):
    """Proporção ponderada com IC de Wilson calculado sobre o tamanho efetivo."""
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    efetivo = tamanho_efetivo(pesos)
    p = k / n
    return wilson_ci(p * efetivo, efetivo)


def metricas_flag(predito, ouro, pesos, estratos=None):
    """Precisão, recall, F1 e prevalências de uma flag, com os pesos da amostra."""
    predito, ouro, pesos = np.asarray(predito, bool), np.asarray(ouro, bool), np.asarray(pesos, float)
    tp = pesos[predito & ouro].sum()
    fp = pesos[predito & ~ouro].sum()
    fn = pesos[~predito & ouro].sum()
    precisao = _proporcao_ponderada(tp, tp + fp, pesos[predito])
    recall = _proporcao_ponderada(tp, tp + fn, pesos[ouro])
    prev_ouro = _proporcao_ponderada(pesos[ouro].sum(), pesos.sum(), pesos)
    resultado = {
        "n_rotulados": int(predito.size),
        "positivos_ouro": int(ouro.sum()),
        "positivos_regra": int(predito.sum()),
        "acertos": int((predito & ouro).sum()),
        "prevalencia_regra": float(pesos[predito].sum() / pesos.sum()),
        "prevalencia_ouro": prev_ouro[0], "prevalencia_ouro_inf": prev_ouro[1], "prevalencia_ouro_sup": prev_ouro[2],
        "precisao": precisao[0], "precisao_inf": precisao[1], "precisao_sup": precisao[2],
        "recall": recall[0], "recall_inf": recall[1], "recall_sup": recall[2],
        "f1": _f1(predito, ouro, pesos),
    }
    if estratos is not None:
        resultado["f1_inf"], resultado["f1_sup"] = ic_f1_bootstrap(predito, ouro, pesos, estratos)
    return resultado


def avaliar_flags(gabarito, ouro):
    """Tabela de métricas por flag, sem as linhas que o padrão-ouro considerou não avaliáveis."""
    base = gabarito.set_index("id_amostra").join(ouro, rsuffix="_ouro", how="inner")
    if "nao_avaliavel" in base:
        base = base[base["nao_avaliavel"].ne("sim")]
    linhas = []
    for flag in FLAGS:
        validos = base[base[f"{flag}_ouro"].isin(SIM_NAO)]
        linhas.append({"flag": flag, **metricas_flag(validos[flag].astype(bool), validos[f"{flag}_ouro"].eq("sim"), validos["peso"], validos["estrato"])})
    return pd.DataFrame(linhas)


def matriz_desfecho(gabarito, ouro):
    """Matriz de confusão ponderada do desfecho: regra nas linhas, padrão-ouro nas colunas."""
    base = gabarito.set_index("id_amostra").join(ouro[["desfecho", *(["nao_avaliavel"] if "nao_avaliavel" in ouro else [])]], rsuffix="_ouro", how="inner")
    if "nao_avaliavel" in base:
        base = base[base["nao_avaliavel"].ne("sim")]
    base = base[base["desfecho_ouro"].isin(DESFECHOS)]
    return base.pivot_table(index="desfecho", columns="desfecho_ouro", values="peso", aggfunc="sum", fill_value=0.0).reindex(index=DESFECHOS, columns=DESFECHOS, fill_value=0.0)


def gravar_adjudicacao(caminho, pendencias, narrativas):
    """Grava as divergências para o terceiro integrante, sem indicar a predição das regras."""
    planilha = Workbook()
    aba = planilha.active
    aba.title = "Adjudicacao"
    _cabecalho(aba, ["id_amostra", "historico", "coluna", "rotulo_1", "rotulo_2", "rotulo_final"])
    for i, r in enumerate(pendencias.itertuples(), start=2):
        aba.cell(row=i, column=1, value=r.id_amostra)
        celula = aba.cell(row=i, column=2)
        celula.value = _texto_seguro(narrativas[r.id_amostra])
        celula.data_type = "s"
        celula.alignment = Alignment(wrap_text=True, vertical="top")
        aba.cell(row=i, column=3, value=r.coluna)
        aba.cell(row=i, column=4, value=r.rotulos[0])
        aba.cell(row=i, column=5, value=r.rotulos[1] if len(r.rotulos) > 1 else "")
    aba.column_dimensions["B"].width = 90
    _lista_suspensa(aba, (*SIM_NAO, *DESFECHOS), "F", max(len(pendencias) + 1, 2))
    planilha.save(caminho)


def ler_adjudicacao(caminho):
    """Lê as decisões do terceiro integrante, sem carregar a narrativa."""
    aba = load_workbook(caminho, read_only=True, data_only=True)["Adjudicacao"]
    linhas = aba.iter_rows(values_only=True)
    titulos = list(next(linhas))
    i_id, i_col, i_final = titulos.index("id_amostra"), titulos.index("coluna"), titulos.index("rotulo_final")
    registros = [{"id_amostra": l[i_id], "coluna": l[i_col], "rotulo_final": "" if l[i_final] is None else str(l[i_final]).strip().lower()}
                 for l in linhas if l[i_id] is not None]
    return pd.DataFrame(registros, columns=["id_amostra", "coluna", "rotulo_final"])
