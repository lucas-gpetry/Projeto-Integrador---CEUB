import re
import spacy
from unidecode import unidecode

# Este código define funções para estruturação da coluna textual na base de dados
# Dicionários de padrões
# As regex rodam sobre o historico_limpo (sem acentos, minúsculo, só letras).
# Plurais e derivações explícitos: com \b no fim, "droga" não casaria com "drogas".
REGEX_PATTERNS = {
    'flag_alcool': r'\b(alcool\w*|embriag\w*|bebeu|bebidas?|cervejas?|cachacas?|vinhos?|vodkas?|pingas?|beber)\b',
    'flag_drogas': r'\b(drogas?|entorpecentes?|maconha|crack|cocaina|pinos?|lanca)\b',
    'flag_arma_fogo': r'\b(armas? de fogo|revolver(es)?|pistolas?|garruchas?|tiros?|disparos?|fuzil|fuzis)\b',
    'flag_arma_branca': r'\b(facas?|canivetes?|tesouras?|estiletes?|facao|facoes|punhal|punhais)\b',
    'flag_tornozeleira': r'\b(tornozeleiras?|monitoramento eletronico)\b',
    'flag_medida_protetiva': r'\b(medidas? protetivas?|protetivas?|descumprimento de medidas?|mpus?)\b'
}


def _sem_acento(termos):
    """Os lemas são comparados sem diacríticos para não depender da grafia do dicionário."""
    return {unidecode(termo) for termo in termos}


# Termos alinhados às definições do DICIONARIO_DE_DADOS.md (ex.: "empurrões", "ameaça
# verbal", "xingamento", "perseguição" constam da definição, mas não estavam nos lemas).
LEMAS_VIOLENCIA = {
    "v_fisica": _sem_acento({"agredir", "bater", "chutar", "empurrar", "empurrão", "soco", "chute", "lesão", "tapa",
                             "espancar", "espancamento", "puxão"}),
    "v_psicologica": _sem_acento({"ameaçar", "ameaça", "humilhar", "humilhação", "xingar", "xingamento", "proibir",
                                  "isolar", "perseguir", "perseguição", "medo", "gritar", "importunar", "importunação"}),
    # Objetos e "tomar" são candidatos: só contam com as condições de extrair_tipos_spacy.
    "v_patrimonial": _sem_acento({"quebrar", "rasgar", "subtrair", "destruir", "danificar", "arrombar", "incendiar", "queimar",
                                  "tomar", "furtar", "roubar", "extorquir", "estragar", "celular", "aparelho", "veículo", "carro",
                                  "moto", "móveis", "móvel", "televisão", "tv", "vidro", "portão", "janela", "porta", "dinheiro",
                                  "cartão", "carteira"}),
    "v_sexual": _sem_acento({"estuprar", "estupro", "sexo", "libidinoso", "vulnerável", "toque"}),
    "v_moral": _sem_acento({
        "caluniar", "difamar", "injuriar", "honra", "fofoca", "reputação", "boato", "ofender", "ofensa", "xingar",
        "xingamento", "palavrão", "difamação", "injúria", "calúnia"
    }),

}

LEMAS_CONTEXTO = {
    'flag_separacao': _sem_acento({'separar', 'separação', 'separado', 'terminar', 'término', 'fim', 'rompimento'}),
    'flag_filhos': _sem_acento({'filho', 'filha', 'criança', 'menor', 'bebê'}),
    # "apresentar" e "local" saíram: aparecem em quase todo histórico ("apresentava lesões",
    # "chegando ao local") e transformavam o desfecho em categoria residual. "deam" entra
    # porque era só o "apresentar" que capturava "apresentado na DEAM".
    'desfecho_dp': {'conduzir', 'encaminhar', 'prender', 'dp', 'delegacia', 'deam'},
    'desfecho_local': {'orientar', 'resolver', 'advertir', 'acordo'}
}

# "ex-marido" vira "ex marido" na normalização, então o termo é buscado como bigrama.
EX_PARCEIRO = {"marido", "mulher", "esposa", "companheiro", "companheira", "namorado", "namorada",
               "convivente", "noivo", "noiva"}
# Termos de término só indicam separação quando seguidos do relacionamento: exclui "por fim",
# "a fim de", "término do serviço", "terminar a ocorrência", "rompimento da tornozeleira".
LEMAS_TERMINO = {"fim", "termino", "terminar", "rompimento"}
RELACIONAMENTO = {"relacionamento", "casamento", "namoro", "uniao", "relacao", "noivado"}
# "separar a briga" / "separou os dois" descreve a intervenção policial, não o casal.
OBJETOS_SEPARAR_BRIGA = {"briga", "brigas", "confusao", "partes", "ambos", "ambas", "eles", "elas",
                         "dois", "duas", "casal", "envolvidos"}
# "separado" só como estado civil ("estavam separados"), não "ouvida em separado" / "quartos separados".
VERBOS_ESTADO = {"esta", "estao", "estava", "estavam", "estar", "sao", "eram", "vivem", "viviam", "ficaram", "ja"}

# Sozinho, o objeto não indica dano: "porta" e "portão" aparecem na rotina do atendimento ("abriu o
# portão", "bateu na porta"). O objeto só conta com um verbo de dano a até JANELA_OBJETO palavras;
# os verbos de dano do léxico ("quebrar", "arrombar"...) já contam por si.
OBJETOS_PATRIMONIO = _sem_acento({"celular", "aparelho", "veículo", "carro", "moto", "móveis", "móvel", "televisão", "tv",
                                  "vidro", "portão", "janela", "porta", "dinheiro", "cartão", "carteira"})
VERBOS_DANO_OBJETO = _sem_acento({"chutar", "forçar", "derrubar", "socar", "esmurrar", "jogar", "arremessar", "riscar", "furar"})
JANELA_OBJETO = 3
# "tomar" só é subtração quando o complemento é um bem ("tomou o celular"). Exclui "tomar
# conhecimento", "tomadas as providências", "tomou rumo ignorado", "tomar remédio".
OBJETOS_TOMAR = _sem_acento({"celular", "aparelho", "telefone", "dinheiro", "cartão", "carteira", "chave", "documento",
                             "bolsa", "veículo", "carro", "moto", "bem", "bens", "pertence", "pertences", "bicicleta"})
ANTES_DO_OBJETO = {"a", "o", "as", "os", "um", "uma", "seu", "sua", "seus", "suas", "lhe", "me", "te", "dela", "dele"}
# "Bater na porta", "bater palmas" e "bater boca" não são agressão física.
BATER_NAO_FISICO = {"porta", "portao", "campainha", "palma", "palmas", "boca", "janela"}

TERMOS_IMPROCEDENCIA =["nada constatado", "nada foi constatado", "negativo quanto", "ausencia de indicios", "nao houve constatacao"]

# Negação (NegEx adaptado): o gatilho só nega o termo se entre eles houver apenas palavras
# "transparentes" (artigos, clíticos, auxiliares e verbos de estado/posse). Assim "nao a agrediu"
# e "nao possui medida protetiva" são negados, mas "nao respeitou a medida protetiva",
# "nao parava de agredir" e "nao aceita o fim do relacionamento" não são.
GATILHOS_NEGACAO = {"nao", "nunca", "jamais", "nem", "sem"}
PALAVRAS_TRANSPARENTES = {
    "a", "o", "as", "os", "lhe", "lhes", "me", "te", "se", "de", "qualquer", "quaisquer", "nenhum", "nenhuma",
    "foi", "foram", "era", "eram", "estava", "estavam", "esta", "estao", "ser", "sido", "estar",
    "houve", "ha", "havia", "haviam", "tem", "tinha", "tinham", "teve", "teria", "ter",
    "possui", "possuia", "possuem", "possuiam", "portava", "portavam", "usou", "utilizou", "uso",
    "chegou", "chegaram", "apresenta", "apresentam", "apresentava", "apresentavam", "apresentou",
    "aparenta", "aparentava", "aparentavam", "sofreu", "sofrido", "sinal", "sinais", "marca", "marcas",
    "constatada", "constatado",
}
JANELA_NEGACAO = 4


def normalizar_para_nlp(texto):
    """
    Prepara o histórico para o spaCy preservando os acentos.
    O modelo foi treinado em português acentuado; sem acentos ele erra lemas
    ("lesoes" -> "lesoe") e a análise de dependências.
    """
    if not isinstance(texto, str):
        return ""
    texto = re.sub(r'[^a-záàâãéêíóôõúüç\s]', ' ', texto.lower())
    return " ".join(texto.split())


def termo_negado(palavras, posicao):
    """Indica se palavras[posicao] está no escopo de um gatilho de negação à esquerda."""
    for distancia in range(1, JANELA_NEGACAO + 1):
        anterior = posicao - distancia
        if anterior < 0:
            return False
        palavra = palavras[anterior]
        if palavra in GATILHOS_NEGACAO:
            return True
        if palavra not in PALAVRAS_TRANSPARENTES:
            return False
    return False


def _lema(token):
    return unidecode(token.lemma_.lower())


def _palavras(doc):
    return [unidecode(token.lower_) for token in doc]


def gatilhos_adicionais(doc):
    """Gera (chave, termo) para cada menção que sustenta filhos, separação ou desfecho."""
    text_low = unidecode(doc.text.lower())
    palavras = _palavras(doc)

    for token in doc:
        lema = _lema(token)
        seguintes = palavras[token.i + 1:token.i + 4]
        anteriores = palavras[max(token.i - 2, 0):token.i]

        # 1. Filhos (Verificando se pertencem à vítima/casal)
        if lema in LEMAS_CONTEXTO['flag_filhos']:
            possessivos = [_lema(child) for child in token.children if child.pos_ == "PRON"]
            if any(p in ['meu', 'nosso', 'dela'] for p in possessivos) or "casal" in text_low:
                yield 'flag_filhos', lema

        # 2. Separação Recente
        if palavras[token.i] == "ex" and seguintes and seguintes[0] in EX_PARCEIRO:
            yield 'flag_separacao', f"ex {seguintes[0]}"
        elif lema in LEMAS_CONTEXTO['flag_separacao'] and not termo_negado(palavras, token.i):
            termino_de_outra_coisa = lema in LEMAS_TERMINO and not RELACIONAMENTO.intersection(seguintes)
            separou_briga = lema == "separar" and OBJETOS_SEPARAR_BRIGA.intersection(seguintes[:2])
            # O particípio pode vir lematizado como "separar", por isso a regra olha a forma escrita.
            separado_sem_estado = palavras[token.i].startswith("separad") and not VERBOS_ESTADO.intersection(anteriores)
            if not (termino_de_outra_coisa or separou_briga or separado_sem_estado):
                yield 'flag_separacao', lema

        # 3. Desfecho
        if lema in LEMAS_CONTEXTO['desfecho_dp']:
            yield 'desfecho_dp', lema
        elif lema in LEMAS_CONTEXTO['desfecho_local']:
            yield 'desfecho_local', lema


def extrair_flags_adicionais(doc):
    """Filhos, separação e desfecho; no desfecho, a menção à delegacia tem prioridade sobre a resolução no local."""
    chaves = {chave for chave, _ in gatilhos_adicionais(doc)}
    if 'desfecho_dp' in chaves:
        desfecho = 'encaminhado_dp'
    elif 'desfecho_local' in chaves:
        desfecho = 'resolvido_local'
    else:
        desfecho = 'nao_identificado'
    return {
        'flag_separacao': 'flag_separacao' in chaves,
        'flag_filhos': 'flag_filhos' in chaves,
        'desfecho': desfecho,
    }


def mencoes_nao_negadas(pattern, texto):
    """Gera o texto de cada ocorrência de pattern fora do escopo de uma negação."""
    palavras = texto.split()
    for match in re.finditer(pattern, texto, re.IGNORECASE):
        if not termo_negado(palavras, len(texto[:match.start()].split())):
            yield match.group(0).lower()


def gatilhos_regex(texto):
    """Gera (flag, termo) para cada menção não negada nos padrões de REGEX_PATTERNS."""
    if not isinstance(texto, str) or texto == "":
        return
    for flag, pattern in REGEX_PATTERNS.items():
        for termo in mencoes_nao_negadas(pattern, texto):
            yield flag, termo


def extrair_flags_regex(texto):
    """
    Varre o texto em busca de termos fixos usando Regex.
    Retorna um dicionário com True/False para cada flag.
    Basta uma menção não negada para ativar a flag.
    """
    flags = {flag for flag, _ in gatilhos_regex(texto)}
    return {flag: flag in flags for flag in REGEX_PATTERNS}


def doc_improcedente(doc):
    """Indica se o histórico traz um termo de improcedência, que zera as formas de violência."""
    texto_bruto = unidecode(doc.text.lower())
    return any(termo in texto_bruto for termo in TERMOS_IMPROCEDENCIA)


def gatilhos_tipos(doc):
    """Gera (categoria, lema) para cada menção que sustenta uma forma, sem aplicar a improcedência."""
    palavras = _palavras(doc)
    lemas = [_lema(token) for token in doc]

    for token in doc:
        lema = lemas[token.i]
        for categoria, termos in LEMAS_VIOLENCIA.items():
            if lema in termos:

                # 1. Filtro de Negação Local
                if termo_negado(palavras, token.i):
                    continue

                # 2. Filtro de Gênero
                if lema == "sexo":
                    vizinhos_genero = [_lema(child) for child in token.children]
                    if any(g in vizinhos_genero for g in ["feminino", "masculino", "fem", "masc"]):
                        continue

                if categoria == "v_fisica" and lema == "bater":
                    if BATER_NAO_FISICO.intersection(palavras[token.i + 1:token.i + 4]):
                        continue

                # Refinamento de Violência Patrimonial
                if categoria == "v_patrimonial":
                    if lema == "quebrar":
                        vizinhos = [_lema(c) for c in token.children] + [_lema(token.head)]
                        termos_juridicos = ["medida", "decisao", "judicial", "protetiva", "regra", "ordem"]
                        if any(v in termos_juridicos for v in vizinhos):
                            continue

                    if lema == "tomar" and not _complemento_e_bem(palavras, lemas, token.i):
                        continue

                    if lema in OBJETOS_PATRIMONIO and not _verbo_de_dano_proximo(palavras, lemas, token.i):
                        continue

                # 3. Tratamento Inteligente de Importunação
                if lema in ["importunar", "importunacao"]:
                    eh_sexual = any(_lema(c) == "sexual" for c in token.children)
                    yield ("v_sexual" if eh_sexual else "v_psicologica"), lema
                    continue

                yield categoria, lema


def extrair_tipos_spacy(doc):
    """
    Versão com desambiguação e filtro de improcedência.
    """
    if doc_improcedente(doc):
        return {key: False for key in LEMAS_VIOLENCIA}
    categorias = {categoria for categoria, _ in gatilhos_tipos(doc)}
    return {key: key in categorias for key in LEMAS_VIOLENCIA}


def _complemento_e_bem(palavras, lemas, posicao):
    """Indica se o complemento de "tomar" (pulando artigos, possessivos e clíticos) é um bem."""
    j = posicao + 1
    while j < len(palavras) and palavras[j] in ANTES_DO_OBJETO:
        j += 1
    return j < len(palavras) and (palavras[j] in OBJETOS_TOMAR or lemas[j] in OBJETOS_TOMAR)


def _verbo_de_dano_proximo(palavras, lemas, posicao):
    """Indica se há verbo de dano não negado a até JANELA_OBJETO palavras do objeto."""
    inicio, fim = max(posicao - JANELA_OBJETO, 0), min(posicao + JANELA_OBJETO + 1, len(lemas))
    return any(lemas[k] in VERBOS_DANO_OBJETO and not termo_negado(palavras, k) for k in range(inicio, fim) if k != posicao)
