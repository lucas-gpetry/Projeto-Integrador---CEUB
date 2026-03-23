import pandas as pd
import os
from src.utils.read_file import read_file
from src.utils.extracao_datetime import extracao_datetime
from unidecode import unidecode

# Função para ler, limpar e padronizar os dados 
def limpar_historico(texto):
    """Função para normalizar o texto do histórico policial."""
    if pd.isna(texto) or not isinstance(texto, str):
        return ""
    
    # Remove acentos e deixa em minúsculo
    texto = unidecode(texto).lower()
    # Remove caracteres especiais (mantendo apenas letras e espaços)
    import re
    texto = re.sub(r'[^a-z\s]', ' ', texto)
    # Remove espaços extras
    texto = " ".join(texto.split())
    
    return texto

def processar_base_completa():
    nome_arquivo = "base_original_pmdf.xlsx" 
    base_dir = os.getcwd()
    caminho_bruto = os.path.join(base_dir, "data", nome_arquivo)
    caminho_saida = os.path.join(base_dir, "data", "base_limpa.csv")

    print(f"Tentando ler: {caminho_bruto}")

    # 2. Carregar os dados
    df = read_file(caminho_bruto)

    # 3. Tratar Datas
    print("\nExtraindo componentes de data/hora...")
    df = extracao_datetime(df, "data hora")

    #4. Normalizar texto
    print("Limpando campo de histórico...")
    coluna_texto = "historico"
    df["historico_limpo"] = df[coluna_texto].apply(limpar_historico)

    # 5. Salvar resultado
    df.to_csv(caminho_saida, index=False, encoding='utf-8')
    print(f"\n--- Finalizado! Base salva em: {caminho_saida} ---")

if __name__ == "__main__":
    processar_base_completa()