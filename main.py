import time
import os
from src.clean_data import processar_base_completa
from src.analysis import realizar_analise

def run():
    print("="*50)
    print("PROJETO PMDF - ANÁLISE MARIA DA PENHA")
    print("="*50)
    
    # Início do cronômetro global
    inicio_total = time.time()

    try:
        # ETAPA 1: Limpeza e Processamento Inicial
        print("\n[1/2] Iniciando Limpeza e Engenharia de Dados...")
        processar_base_completa()
        
        print("-" * 30)

        # ETAPA 2: Análise com spaCy + Regex
        print("[2/2] Aplicando inteligência NLP e calculando Score...")
        realizar_analise()

        # Cálculo do tempo final
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