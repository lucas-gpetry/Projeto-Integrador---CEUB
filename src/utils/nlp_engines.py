import re
import spacy

# Este código define funções para estruturação da coluna textual na base de dados
# Dicionários de padrões
REGEX_PATTERNS = {
    'flag_alcool': r'\b(alc[oo]l|embriag\w*|bebeu|bebida|cerveja|cacha[çc]a|vinho|vodka|pinga|beber)\b',
    'flag_drogas': r'\b(droga|entorpecente|maconha|crack|coca[ií]na|pino|lan[çc]a)\b',
    'flag_arma_fogo': r'\b(arma de fogo|rev[oó]lver|pistola|garrucha|tiro|disparo|fuzil)\b',
    'flag_arma_branca': r'\b(faca|canivete|tesoura|estilete|fac[ãa]o|punhal)\b',
    'flag_tornozeleira': r'\b(tornozeleira|monitoramento eletr[oô]nico)\b',
    'flag_medida_protetiva': r'\b(medida protetiva|m\.p\.|protetiva|descumprimento de medida)\b'
}

LEMAS_VIOLENCIA = {
    "v_fisica": {"agredir", "bater", "chutar", "empurrar", "soco", "chute", "lesao", "tapa", "espancar", "puxao"},
    "v_psicologica": {"ameaçar", "humilhar", "xingar", "proibir", "isolar", "perseguir", "medo", "gritar", "importunar", "importunacao"},
    "v_patrimonial": {"quebrar", "rasgar", "subtrair", "destruir", "danificar", "arrombar", "incendiar", "queimar",
                        "tomar", "furtar", "roubar", "extorquir", "estragar", "celular", "aparelho", "veiculo", "carro",
                        "moto", "moveis", "televisao", "tv", "vidro", "portao", "janela", "porta", "dinheiro", "cartao", "carteira"},
    "v_sexual": {"estuprar", "estupro", "sexo", "libidinoso", "vulneravel", "toque"},
    "v_moral": {
        "caluniar", "difamar", "injuriar", "honra", "fofoca", "reputacao", "boato", "ofender", "ofensa", "xingar", "palavrao", "difamacao", "injuria", "calunia"
    },

}

LEMAS_CONTEXTO = {
    'flag_separacao': {'separar', 'terminar', 'fim', 'rompimento', 'ex-marido', 'ex-companheiro'},
    'flag_filhos': {'filho', 'filha', 'crianca', 'menor', 'bebe'},
    'desfecho_dp': {'conduzir', 'encaminhar', 'apresentar', 'prender', 'dp', 'delegacia'},
    'desfecho_local': {'orientar', 'resolver', 'local', 'advertir', 'acordo'}
}

def extrair_flags_adicionais(doc):
    """
    Nova função para capturar as flags que você solicitou via spaCy.
    """
    resultados = {
        'flag_separacao': False,
        'flag_filhos': False,
        'desfecho': 'nao_identificado'
    }

    text_low = doc.text.lower()

    for token in doc:
        lema = token.lemma_

        # 1. Filhos (Verificando se pertencem à vítima/casal)
        if lema in LEMAS_CONTEXTO['flag_filhos']:
            possessivos = [child.lemma_ for child in token.children if child.pos_ == "PRON"]
            if any(p in ['meu', 'nosso', 'dela'] for p in possessivos) or "casal" in text_low:
                resultados['flag_filhos'] = True

        # 2. Separação Recente
        if lema in LEMAS_CONTEXTO['flag_separacao']:
            if not any(t.dep_ == "neg" for t in token.children):
                resultados['flag_separacao'] = True

        # 3. Desfecho (Hierarquia: Prioriza DP sobre Local)
        if lema in LEMAS_CONTEXTO['desfecho_dp']:
            resultados['desfecho'] = 'encaminhado_dp'
        elif lema in LEMAS_CONTEXTO['desfecho_local'] and resultados['desfecho'] != 'encaminhado_dp':
            resultados['desfecho'] = 'resolvido_local'

    return resultados

def extrair_flags_regex(texto):
    """
    Varre o texto em busca de termos fixos usando Regex.
    Retorna um dicionário com True/False para cada flag.
    """
    if not isinstance(texto, str) or texto == "":
        return {key: False for key in REGEX_PATTERNS.keys()}
    
    resultados = {}
    for flag, pattern in REGEX_PATTERNS.items():
        if re.search(pattern, texto, re.IGNORECASE):
            resultados[flag] = True
        else:
            resultados[flag] = False
    return resultados


def extrair_tipos_spacy(doc):
    """
    Versão com desambiguação e filtro de improcedência.
    """
    resultados = {key: False for key in LEMAS_VIOLENCIA.keys()}
    texto_bruto = doc.text.lower()
    termos_improcedencia = ["nada constatado", "nada foi constatado", "negativo quanto", "ausencia de indicios", "nao houve constatacao"]
    if any(termo in texto_bruto for termo in termos_improcedencia):
        return resultados

    for token in doc:
        lema = token.lemma_
        for categoria, termos in LEMAS_VIOLENCIA.items():
            if lema in termos:
                
                # 1. Filtro de Negação Local
                tem_negacao = any(child.dep_ == "neg" for child in token.children) or \
                              any(child.dep_ == "neg" for child in token.head.children)
                if tem_negacao: continue

                # 2. Filtro de Gênero
                if lema == "sexo":
                    vizinhos_genero = [child.lemma_ for child in token.children]
                    if any(g in vizinhos_genero for g in ["feminino", "masculino", "fem", "masc"]):
                        continue 
                
                # Refinamento de Violência Patrimonial
                if categoria == "v_patrimonial":
                    if lema == "quebrar":
                        vizinhos = [c.lemma_ for c in token.children] + [token.head.lemma_]
                        termos_juridicos = ["medida", "decisao", "judicial", "protetiva", "regra", "ordem"]
                        if any(v in termos_juridicos for v in vizinhos):
                            continue 

                    if lema in ["celular", "dinheiro", "cartao", "carteira", "aparelho", "veiculo"]:
                        texto_contexto = doc.text.lower()
                        # Lista de verbos que indicam agressão ao patrimônio
                        verbos_acao = ["quebrou", "quebrar", "danificou", "danificar", "tomou", "tomar", 
                                       "subtraiu", "subtrair", "roubou", "roubar", "rasgou", "rasgar"]
                        if not any(v in texto_contexto for v in verbos_acao):
                            continue

                # 3. Tratamento Inteligente de Importunação
                if lema in ["importunar", "importunacao"]:
                    eh_sexual = any(c.lemma_ == "sexual" for c in token.children)
                    if eh_sexual: 
                        resultados["v_sexual"] = True
                    else: 
                        resultados["v_psicologica"] = True
                    continue

                if categoria == "v_moral":
                    if lema == "mentira":
                        texto_contexto = doc.text.lower()
                        indicadores_crime = ["contou", "espalhou", "falou", "inventou"]
                        negativas_autor = ["autor disse", "autor alegou", "ser mentira", "diz ser"]
                        
                        if any(n in texto_contexto for n in negativas_autor):
                            continue
                        if not any(i in texto_contexto for i in indicadores_crime):
                            continue

                    # 2. Refinamento de Ofensas/Xingamentos (Verifica se houve o ato de proferir)
                    if lema in ["ofender", "ofensa", "xingar", "palavrao"]:
                        vizinhos = [c.lemma_ for c in token.children] + [token.head.lemma_]

                resultados[categoria] = True
    return resultados