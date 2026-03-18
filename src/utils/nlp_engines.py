import re
import spacy

# Dicionários de padrões
REGEX_PATTERNS = {
    'flag_alcool': r'\b(alc[oo]l|embriag\w*|bebeu|bebida|cerveja|cacha[çc]a|vinho|vodka|pinga)\b',
    'flag_drogas': r'\b(droga|entorpecente|maconha|crack|coca[ií]na|pino|lan[çc]a)\b',
    'flag_arma_fogo': r'\b(arma de fogo|rev[oó]lver|pistola|garrucha|tiro|disparo|fuzil)\b',
    'flag_arma_branca': r'\b(faca|canivete|tesoura|estilete|fac[ãa]o|punhal)\b',
    'flag_tornozeleira': r'\b(tornozeleira|monitoramento eletr[oô]nico)\b',
    'flag_medida_protetiva': r'\b(medida protetiva|m\.p\.|protetiva|descumprimento)\b',
    'flag_saida_temporaria': r'\b(saidinha|said[ãa]o|vpt|visita peri[óo]dica|sa[íi]da tempor[áa]ria|alvar[áa])\b'
}

LEMAS_VIOLENCIA = {
    "v_fisica": {"agredir", "bater", "chutar", "empurrar", "soco", "chute", "lesao", "tapa", "espancar", "puxao"},
    "v_psicologica": {"ameaçar", "humilhar", "xingar", "proibir", "isolar", "perseguir", "medo", "gritar"},
    "v_patrimonial": {"quebrar", "rasgar", "subtrair", "destruir", "celular", "cartao", "dinheiro", "carteira"},
    "v_sexual": {"estuprar", "estupro", "sexo", "libidinoso", "vulneravel", "toque"},
    "v_moral": {"caluniar", "difamar", "injuriar", "honra", "mentira", "fofoca"},

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
    Versão com desambiguação de 'sexo'e 'importunação'
    """
    resultados = {key: False for key in LEMAS_VIOLENCIA.keys()}

    for token in doc:
        lema = token.lemma_
        
        for categoria, termos in LEMAS_VIOLENCIA.items():
            if lema in termos:
                
                # 1. Filtro de Negação
                tem_negacao = any(child.dep_ == "neg" for child in token.children) or \
                              any(child.dep_ == "neg" for child in token.head.children)
                if tem_negacao: continue

                # 2. FILTRO DE GÊNERO (O problema do 'sexo feminino/masculino')
                if lema == "sexo":
                    vizinhos_genero = [child.lemma_ for child in token.children]
                    if "feminino" in vizinhos_genero or "masculino" in vizinhos_genero:
                        continue # Ignora, pois é descrição de gênero, não ato sexual
                
                # 3. Tratamento de Importunação (que já tínhamos)
                if lema in ["importunar", "importunacao"]:
                    eh_sexual = any(c.lemma_ == "sexual" for c in token.children)
                    if eh_sexual: resultados["v_sexual"] = True
                    else: resultados["v_psicologica"] = True
                    continue

                resultados[categoria] = True
    return resultados