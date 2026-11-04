"""Auditoria das flags textuais da PMDF sem leitura de narrativas: só contagens agregadas.

Não mede precisão nem recall, que dependem do padrão-ouro (padrao_ouro.py). Mede quanto cada flag
depende do dicionário: os termos que a sustentam, os termos ambíguos e as menções que ficam de fora.
"""

import re
from collections import defaultdict

import pandas as pd

from src.utils.report_stats import razao_prevalencia_mh
from src.utils.nlp_engines import (
    doc_improcedente,
    gatilhos_adicionais,
    gatilhos_regex,
    gatilhos_tipos,
    mencoes_nao_negadas,
)

FORMAS = ["v_fisica", "v_psicologica", "v_moral", "v_patrimonial", "v_sexual"]
CONTEXTOS = ["flag_alcool", "flag_drogas", "flag_arma_fogo", "flag_arma_branca", "flag_tornozeleira",
             "flag_medida_protetiva", "flag_separacao", "flag_filhos"]
FLAGS = FORMAS + CONTEXTOS

# Termos do dicionário com outro sentido frequente. Se uma flag só tem esses termos, ela pode ser falso positivo.
TERMOS_AMBIGUOS = {
    "v_fisica": {"lesao", "bater"},
    "v_psicologica": {"medo", "gritar", "proibir", "isolar", "perseguir", "perseguicao"},
    "v_moral": {"honra", "ofensa", "ofender"},
    "v_patrimonial": {"queimar", "roubar", "furtar"},
    "v_sexual": {"toque", "sexo", "vulneravel"},
    "flag_alcool": {"beber", "bebeu"},
    "flag_drogas": {"pino", "pinos", "lanca"},
    "flag_arma_fogo": {"tiro", "tiros", "disparo", "disparos"},
    "flag_arma_branca": {"tesoura", "tesouras"},
    "flag_tornozeleira": set(),
    "flag_medida_protetiva": {"mpu", "mpus"},
    "flag_separacao": {"separar", "separado"},
    "flag_filhos": {"menor", "crianca", "bebe"},
}

# "radical:" são formas dos termos que já estão no dicionário e a regra não reconheceu; os demais rótulos estão fora dele.
LEXICO_AMPLIADO = {
    "v_fisica": {
        "radical: agred-": r"\bagred\w+",
        "radical: chut-/empurr-/espanc-": r"\b(chut|empurr|espanc)\w+",
        "radical: lesao/tapa/soco": r"\b(lesoes|lesao|tapas?|socos?)\b",
        "agressao": r"\bagress(ao|oes)\b(?! verba)",
        "estrangulamento": r"\b(esgan|enforc|estrangul|sufoc)\w+",
        "mordida/arranhao/cuspe": r"\b(mord|arranh|cusp)\w+",
        "socar/murro/pancada": r"\b(socou|socar|socava|murros?|pancadas?|bofetad\w+|estape\w+)\b",
        "vias de fato": r"\bvias de fato\b",
        "ferimento": r"\b(hematomas?|machuc\w+|lesion\w+|ferid\w+|feriment\w+|sangr\w+)\b",
        "puxar cabelo": r"\bpux\w+( \w+){0,3} cabelos?\b",
    },
    "v_psicologica": {
        "radical: ameac-": r"\bameac\w+",
        "radical: humilh-/xing-/persegu-": r"\b(humilh|xing|persegu)\w+",
        "constrangimento/chantagem": r"\b(constrang|chantag)\w+",
        "intimidacao/coacao": r"\b(intimid|coag|coacao|amedront|atemoriz|assust)\w*",
        "perturbacao": r"\bperturb\w+",
        "promessa de morte": r"\b(matar|mataria|matarei)\b",
    },
    "v_moral": {
        "radical: xing-/ofens-/ofend-": r"\b(xing|ofens|ofend)\w+",
        "radical: injuri-/calun-/difam-": r"\b(injuri|calun|difam)\w+",
        "insulto": r"\b(insult\w+|baixo calao|palavroes?)\b",
        "insulto literal": r"\b(vagabund\w+|vadia\w*|piranha\w*|puta|putas|safad\w+|biscate\w*)\b",
    },
    "v_patrimonial": {
        "radical: quebr-": r"\bquebr\w+(?! (a |de |da )?(medida|protetiva|decisao|ordem))",
        "radical: destru-/danific-/arromb-/rasg-": r"\b(destru|danific|arromb|rasg)\w+",
        "radical: furt-/roub-/subtra-": r"\b(furt|roub|subtra)\w+",
        "dano": r"\bdanos?\b",
        "retencao": r"\b(reten\w+|reteve|retem|retinha)\b",
        "pegar/levar bem": r"\b(pegou|levou|escondeu)( \w+){0,3} (celular|chave|carteira|documentos?|dinheiro|cartao)\b",
    },
    "v_sexual": {
        "radical: estupr-": r"\bestupr\w+",
        "sexual": r"\bsexua\w+",
        "abuso": r"\b(abusou|abusad[ao]|abus\w+ sexua\w+)\b",
        "assedio": r"\bassedi\w+",
        "ato libidinoso": r"\b(libidinos\w+|conjuncao carnal|partes intimas|nudes?)\b",
    },
    "flag_alcool": {
        "bebado": r"\b(bebad[oa]s?|bebendo|bebia|bebiam|ebri\w+|etilic\w+)\b",
    },
    "flag_drogas": {
        "dependencia": r"\b(dependen\w+ quimic\w+|usuari\w+ de)\b",
        "outras substancias": r"\b(merla|skunk|ecstasy|haxixe|lsd|cannabis|psicoativ\w+|substancias? ilicitas?)\b",
    },
    "flag_arma_fogo": {
        "municao/calibre": r"\b(municao|municoes|calibre)\b",
        "espingarda/simulacro": r"\b(espingardas?|escopetas?|rifles?|simulacros?)\b",
        "arma sem especificar": r"\b(armas?(?! de fogo)(?! branca)|armad[oa]s?)\b",
    },
    "flag_arma_branca": {
        "arma branca": r"\barmas? brancas?\b",
        "outros cortantes": r"\b(peixeiras?|foices?|machados?|facadas?|navalhas?|giletes?|perfuro ?cortantes?)\b",
    },
    "flag_tornozeleira": {
        "monitorado": r"\b(monitorad[oa]s?|monitoracao)\b",
    },
    "flag_medida_protetiva": {
        "descumprimento": r"\bdescumpr\w+",
        "outras medidas": r"\b(medidas? cautelar\w*|medidas? de protecao)\b",
    },
    "flag_separacao": {
        "ex": r"\bex\b",
        "separacao": r"\b(separ(ou|aram|ada|ado|adas|ados|acao)|divorc\w+)\b",
    },
    "flag_filhos": {
        "filho": r"\bfilh[oa]s?\b",
        "enteado/crianca": r"\b(entead[oa]s?|criancas?)\b",
    },
}

# Na regra, "acordo" e "resolver" marcam resolução no local, e qualquer citação à delegacia marca encaminhamento.
_ACORDO = re.compile(r"\bacordo\b")
_DE_ACORDO = re.compile(r"\bde acordo\b")
_ORIENTOU_DELEGACIA = re.compile(r"\borient\w+( \w+){0,8} (delegacia|deam|dp)\b")
_ENCAMINHOU_SAUDE = re.compile(r"\bencaminh\w+( \w+){0,4} (hospital|upa|hran|hrt|hmib|samu|ubs|posto)\b")
_SO_CITA_DELEGACIA = {"delegacia", "dp", "deam"}
CENARIOS = ["observado", "sem_de_acordo", "sem_resolver", "orientacao_nao_conduz"]


def candidatos_ampliados(texto_limpo):
    """Rótulos do léxico ampliado com ao menos uma menção não negada, por flag."""
    achados = {}
    for flag, padroes in LEXICO_AMPLIADO.items():
        rotulos = {rotulo for rotulo, padrao in padroes.items() if next(mencoes_nao_negadas(padrao, texto_limpo), None)}
        if rotulos:
            achados[flag] = rotulos
    return achados


def analisar_documento(doc, texto_limpo):
    """Resume um histórico sem guardar o texto: só os termos do dicionário e os sinais agregáveis."""
    gatilhos = defaultdict(set)
    for origem in (gatilhos_regex(texto_limpo), gatilhos_tipos(doc), gatilhos_adicionais(doc)):
        for chave, termo in origem:
            gatilhos[chave].add(termo)
    return {
        "gatilhos": dict(gatilhos),
        "improcedente": doc_improcedente(doc),
        "candidatos": candidatos_ampliados(texto_limpo),
        "palavras": len(texto_limpo.split()),
        "acordo_idiomatico": len(_ACORDO.findall(texto_limpo)) == len(_DE_ACORDO.findall(texto_limpo)),
        "orientou_delegacia": bool(_ORIENTOU_DELEGACIA.search(texto_limpo)),
        "encaminhou_saude": bool(_ENCAMINHOU_SAUDE.search(texto_limpo)),
    }


def flag_positiva(registro, flag):
    """Reproduz o valor da flag: nas formas de violência, a improcedência zera as menções."""
    if flag in FORMAS and registro["improcedente"]:
        return False
    return flag in registro["gatilhos"]


def desfecho(registro, cenario="observado"):
    """Desfecho pela regra e por cenários que retiram os gatilhos suspeitos, de forma cumulativa."""
    dp = set(registro["gatilhos"].get("desfecho_dp", ()))
    local = set(registro["gatilhos"].get("desfecho_local", ()))
    if cenario in ("sem_de_acordo", "sem_resolver", "orientacao_nao_conduz"):
        if registro["acordo_idiomatico"]:
            local.discard("acordo")
    if cenario in ("sem_resolver", "orientacao_nao_conduz"):
        local.discard("resolver")
    if cenario == "orientacao_nao_conduz":
        if dp and dp <= _SO_CITA_DELEGACIA and registro["orientou_delegacia"]:
            return "resolvido_local"
        if dp == {"encaminhar"} and registro["encaminhou_saude"]:
            dp = set()
    if dp:
        return "encaminhado_dp"
    return "resolvido_local" if local else "nao_identificado"


def resumir_termos(registros):
    """Para cada flag e termo: históricos que o citam e históricos em que ele é o único sustento."""
    total, exclusivos, positivos = defaultdict(int), defaultdict(int), defaultdict(int)
    for registro in registros:
        for flag in FLAGS:
            if not flag_positiva(registro, flag):
                continue
            positivos[flag] += 1
            termos = registro["gatilhos"][flag]
            for termo in termos:
                total[flag, termo] += 1
                if len(termos) == 1:
                    exclusivos[flag, termo] += 1
    n = len(registros)
    linhas = [{
        "flag": flag, "termo": termo, "ambiguo": termo in TERMOS_AMBIGUOS.get(flag, ()),
        "historicos": qtd, "unico_sustento": exclusivos[flag, termo],
        "prevalencia_sem_o_termo": (positivos[flag] - exclusivos[flag, termo]) / n,
    } for (flag, termo), qtd in total.items()]
    return pd.DataFrame(linhas).sort_values(["flag", "historicos"], ascending=[True, False]).reset_index(drop=True)


def faixas_por_flag(registros):
    """Prevalência observada e o quanto ela muda sem os termos ambíguos e com as menções fora do dicionário."""
    n = len(registros)
    linhas = []
    for flag in FLAGS:
        ambiguos = TERMOS_AMBIGUOS.get(flag, set())
        pos = so_ambiguos = radical = fora = zerados = 0
        for r in registros:
            if flag_positiva(r, flag):
                pos += 1
                so_ambiguos += r["gatilhos"][flag] <= ambiguos
                continue
            if flag in FORMAS and r["improcedente"]:
                zerados += flag in r["gatilhos"]
                continue
            achados = r["candidatos"].get(flag, ())
            if any(a.startswith("radical:") for a in achados):
                radical += 1
            elif achados:
                fora += 1
        linhas.append({
            "flag": flag, "positivos": pos, "prevalencia": pos / n,
            "so_termos_ambiguos": so_ambiguos, "prevalencia_sem_ambiguos": (pos - so_ambiguos) / n,
            "radical_nao_reconhecido": radical, "mencao_fora_do_dicionario": fora,
            "prevalencia_com_candidatos": (pos + radical + fora) / n,
            "cobertura_pior_cenario": pos / (pos + radical + fora) if pos + radical + fora else float("nan"),
            "zerados_por_improcedencia": zerados,
        })
    return pd.DataFrame(linhas)


def candidatos_por_rotulo(registros):
    """Históricos sem a flag que têm cada rótulo do léxico ampliado."""
    contagem = defaultdict(int)
    for r in registros:
        for flag, rotulos in r["candidatos"].items():
            if flag_positiva(r, flag) or (flag in FORMAS and r["improcedente"]):
                continue
            for rotulo in rotulos:
                contagem[flag, rotulo] += 1
    linhas = [{"flag": f, "rotulo": rot, "historicos_sem_flag": q} for (f, rot), q in contagem.items()]
    return pd.DataFrame(linhas).sort_values(["flag", "historicos_sem_flag"], ascending=[True, False]).reset_index(drop=True)


def cenarios_desfecho(registros):
    """Distribuição do desfecho em cada cenário, com a contagem de históricos por classe."""
    return pd.DataFrame({c: pd.Series([desfecho(r, c) for r in registros]).value_counts() for c in CENARIOS}).fillna(0).astype(int)


def razoes_por_cenario(registros, formas=("v_fisica", "v_psicologica", "v_moral", "v_patrimonial")):
    """RP de cada forma entre encaminhamento e resolução no local, ajustada pelo tamanho do texto, em cada cenário."""
    palavras = pd.Series([r["palavras"] for r in registros], name="palavras")
    base = pd.DataFrame({forma: [flag_positiva(r, forma) for r in registros] for forma in formas})
    base["decil"] = pd.qcut(palavras, 10, labels=False, duplicates="drop")
    linhas = []
    for cenario in CENARIOS:
        classe = pd.Series([desfecho(r, cenario) for r in registros])
        v = base[classe.ne("nao_identificado")].assign(encaminhado=classe.eq("encaminhado_dp"))
        for forma in formas:
            rp = razao_prevalencia_mh(v, "encaminhado", forma, "decil")
            linhas.append({"cenario": cenario, "forma": forma, "encaminhados": int(v["encaminhado"].sum()), "resolvidos": int((~v["encaminhado"]).sum()),
                           "rp": rp["rp"], "ic_inf": rp["ic_inf"], "ic_sup": rp["ic_sup"]})
    return pd.DataFrame(linhas)


def taxas_por_extensao(registros, decis=10):
    """Taxa de cada flag no decil mais curto e no mais longo: mede o viés de detecção pelo tamanho do texto."""
    palavras = pd.Series([r["palavras"] for r in registros])
    grupo = pd.qcut(palavras.rank(method="first"), decis, labels=False)
    linhas = []
    for flag in FLAGS:
        valores = pd.Series([flag_positiva(r, flag) for r in registros])
        linhas.append({"flag": flag, "taxa_decil_curto": valores[grupo == 0].mean(), "taxa_decil_longo": valores[grupo == decis - 1].mean()})
    return pd.DataFrame(linhas)


def suprimir_contagens(tabela, colunas, k=5):
    """Troca contagens abaixo de k por '<k' antes de gravar ou mostrar a tabela."""
    saida = tabela.copy()
    for coluna in colunas:
        saida[coluna] = saida[coluna].map(lambda v: f"<{k}" if 0 < v < k else v)
    return saida
