from src.clean_data import processar_base_completa

def run():
    print("="*30)
    print("PROJETO PMDF - MARIA DA PENHA")
    print("="*30)
    
    try:
        # Chama a função principal de limpeza
        processar_base_completa()
        print("\n[OK] Fase de limpeza e processamento concluída!")
        
    except Exception as e:
        print(f"\n[ERRO] Ocorreu um problema: {e}")

if __name__ == "__main__":
    run()