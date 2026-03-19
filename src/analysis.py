import pandas as pd
import spacy
import os
from tqdm import tqdm
from src.utils.nlp_engines import extrair_flags_regex, extrair_tipos_spacy, extrair_flags_adicionais

def realizar_analise():
    caminho_in = os.path.join("data", "base_limpa.csv")
    caminho_out = os.path.join("data", "base_analisada.csv")

    if not os.path.exists(caminho_in):
        raise FileNotFoundError(f"Arquivo {caminho_in} não encontrado.")

    df = pd.read_csv(caminho_in)
    df['historico_limpo'] = df['historico_limpo'].fillna('')

    # Carrega spaCy otimizado (sem NER para ganhar velocidade)
    nlp = spacy.load("pt_core_news_sm", disable=["ner", "textcat"])

    print(f"--- Processando {len(df)} ocorrências com Pipeline Híbrida ---")
    
    resultados_finais = []
    textos = df['historico_limpo'].tolist()

    # Processamento em Lote (nlp.pipe)
    for i, doc in enumerate(tqdm(nlp.pipe(textos, batch_size=500), total=len(df))):
        texto_original = textos[i]
        
        # 1. Extração via Regex (Baseada no texto bruto)
        res_regex = extrair_flags_regex(texto_original)
        
        # 2. Extração via spaCy (Tipos de Violência)
        res_tipos = extrair_tipos_spacy(doc)
        
        # 3. Extração via spaCy (Contexto Adicional)
        res_contexto = extrair_flags_adicionais(doc)
        
        # Une todos os dicionários em um só
        row_result = {**res_regex, **res_tipos, **res_contexto}
        resultados_finais.append(row_result)

    # Transformando a lista de dicionários em colunas do DataFrame
    df_analisado = pd.DataFrame(resultados_finais)
    df = pd.concat([df, df_analisado], axis=1)

    # --- CÁLCULO DO SCORE DE RISCO (Exemplo)
    #df['score_risco'] = (
        #df['flag_arma_fogo'].astype(int) * 3 +
        #df['flag_medida_protetiva'].astype(int) * 3 +
        #df['flag_separacao'].astype(int) * 2 +
        #df['v_fisica'].astype(int) * 2 +
        #df['flag_alcool'].astype(int) * 1
    #)

    df.to_csv(caminho_out, index=False)
    print(f"Análise concluída. Base salva com {df.shape[1]} colunas.")

if __name__ == "__main__":
    realizar_analise()