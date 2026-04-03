import time
import os
from src.clean_data import processar_base_completa
from src.geo_analysis import processar_geoespacial # <-- Sua importação aqui
from src.analysis import realizar_analise

def contar_enderecos_repetidos():
    caminho = os.path.join(os.path.dirname(__file__), "data", "base_espacial.csv")
    df = pd.read_csv(caminho)

    colunas = ["bairro", "quadra", "complemento"]
    total = len(df)

    duplicados = df.duplicated(subset=colunas, keep=False)
    qtd_repetidas = duplicados.sum()
    percentual = (qtd_repetidas / total) * 100

    print(f"\nTotal de linhas: {total}")
    print(f"Linhas com endereço repetido (bairro+quadra+complemento): {qtd_repetidas}")
    print(f"Percentual do total: {percentual:.2f}%")

    contagem = df.groupby(colunas).size().reset_index(name="ocorrencias")
    repetidos = contagem[contagem["ocorrencias"] > 1].sort_values("ocorrencias", ascending=False)

    total_enderecos_unicos = len(contagem)
    percentual_repetidos = (len(repetidos) / total_enderecos_unicos) * 100
    print(f"\nEndereços únicos que se repetem: {len(repetidos)} de {total_enderecos_unicos} ({percentual_repetidos:.2f}%)")
    print("\nTop 10 endereços mais repetidos:")
    print(repetidos.head(10).to_string(index=False))

def run():
    print("="*50)
    print("PROJETO PMDF - ANÁLISE MARIA DA PENHA")
    print("="*50)
    
    inicio_total = time.time()

    try:
        # ETAPA 1: Limpeza e Processamento Inicial 
        print("\n[1/3] Iniciando Limpeza e Extração de Datas...")
        processar_base_completa()
        
        print("-" * 30)

        # ETAPA 2: Análise Geoespacial e Atributos 
        print("[2/3] Aplicando Engenharia Geoespacial (Turnos, Moradia e Grade)...")
        processar_geoespacial()

        print("-" * 30)

        # ETAPA 3: Análise com spaCy + Regex 
        print("[3/3] Aplicando NLP...")
        realizar_analise()

        fim_total = time.time()
        tempo_total = (fim_total - inicio_total) / 60
        
        print("\n" + "="*50)
        print("✨ PIPELINE FINALIZADO COM SUCESSO!")
        print(f"Tempo total de execução: {tempo_total:.2f} minutos")
        print(f"Arquivo gerado: data/base_analisada.csv")
        print("="*50)

    except Exception as e:
        print(f"\nERRO NO PIPELINE: {e}")
        import traceback; print(traceback.format_exc())

if __name__ == "__main__":
    run()
