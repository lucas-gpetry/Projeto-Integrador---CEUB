import time
import os
import sys
from src.clean_data import processar_base_completa
from src.geo_analysis import processar_geoespacial
from src.analysis import realizar_analise
from scripts.agrupamentos_nlp import gerar_agrupamentos_nlp
from src.sinan_pipeline import processar_sinan_e_integrar_pmdf


# Mantém logs legíveis no terminal Windows e evita que caracteres dos módulos interrompam a esteira.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

def run():
    print("="*50)
    print("PROJETO PMDF - ANÁLISE MARIA DA PENHA")
    print("="*50)

    # As etapas 1 a 4 resolvem caminhos a partir do diretório atual; a 5, a partir da raiz.
    # Fixar a raiz evita que uma etapa leia a saída antiga de outra.
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    inicio_total = time.time()

    try:
        # ETAPA 1: Limpeza e Processamento Inicial 
        print("\n[1/5] Iniciando Limpeza e Extração de Datas...")
        processar_base_completa()
        
        print("-" * 30)

        # ETAPA 2: Análise Geoespacial e Atributos 
        print("[2/5] Aplicando Engenharia Geoespacial (Turnos, Moradia e Grade)...")
        processar_geoespacial()

        print("-" * 30)

        # ETAPA 3: Análise com spaCy + Regex 
        print("[3/5] Aplicando NLP...")
        realizar_analise()

        print("-" * 30)

        # ETAPA 4: Agrupamentos das categorias extraídas pelo NLP
        print("[4/5] Gerando agrupamentos e planilhas de validação NLP...")
        caminho_agrupamentos = gerar_agrupamentos_nlp(
            input_path=os.path.join("data", "base_analisada.csv"),
            output_dir=os.path.join("outputs", "agrupamentos_nlp"),
        )

        print("-" * 30)
        print("[5/5] Tratando SINAN e integrando indicadores agregados com PMDF...")
        caminho_sinan = processar_sinan_e_integrar_pmdf()

        fim_total = time.time()
        tempo_total = (fim_total - inicio_total) / 60
        
        print("\n" + "="*50)
        print("✨ PIPELINE FINALIZADO COM SUCESSO!")
        print(f"Tempo total de execução: {tempo_total:.2f} minutos")
        print(f"Arquivo gerado: data/base_analisada.csv")
        print(f"Agrupamentos gerados em: {caminho_agrupamentos}")
        print(f"Integração SINAN × PMDF gerada em: {caminho_sinan}")
        print("="*50)

    except Exception as e:
        print(f"\nERRO NO PIPELINE: {e}")
        import traceback; print(traceback.format_exc())
        # Código de saída diferente de zero: uma etapa que falha deixa as saídas da execução
        # anterior no lugar, e o relatório as renderizaria sem aviso.
        sys.exit(1)

if __name__ == "__main__":
    run()
