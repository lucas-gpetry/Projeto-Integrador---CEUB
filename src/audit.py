import pandas as pd
import os

def auditar_pipeline():
    base_dir = os.getcwd()
    caminho_final = os.path.join(base_dir, "data", "base_analisada.csv")

    if not os.path.exists(caminho_final):
        print(f"❌ ERRO: O arquivo {caminho_final} não existe. Rode o main.py primeiro!")
        return

    print("\n🔍 INICIANDO AUDITORIA DA BASE FINAL...\n")
    df = pd.read_csv(caminho_final)

    # 1. Checagem de Volumetria e Saúde
    print(f"📊 Total de Registros: {len(df)}")
    print(f"📍 Registros com Célula Espacial (Grid): {df['id_celula'].notna().sum()}")
    print("-" * 50)

    # 2. Validação da Frente Geoespacial (Pessoa 4)
    print("🏠 Top 3 Locais de Ocorrência:")
    if 'TIPO_MORADIA' in df.columns:
        print(df['TIPO_MORADIA'].value_counts().head(3))
    
    print("\n⏰ Distribuição por Turno:")
    if 'TURNO' in df.columns:
        print(df['TURNO'].value_counts())
    print("-" * 50)

    # 3. Validação da Frente NLP (Pessoa 3)
    print("🧠 Detecções da Inteligência Artificial (NLP):")
    colunas_nlp = ['v_fisica', 'v_psicologica', 'flag_arma_fogo', 'flag_alcool', 'flag_separacao']
    
    for col in colunas_nlp:
        if col in df.columns:
            total_detectado = df[col].sum() # Como é True/False, a soma dá o total de True
            print(f"  - {col}: {total_detectado} casos encontrados.")
    print("-" * 50)

    # 4. A Prova Real do Texto (Ground Truthing)
    print("\n🕵️ LENDO 3 CASOS CLASSIFICADOS COMO VIOLÊNCIA FÍSICA PARA VALIDAR O NLP:")
    if 'v_fisica' in df.columns and df['v_fisica'].sum() > 0:
        amostra = df[df['v_fisica'] == True][['historico_limpo']].dropna().sample(min(3, df['v_fisica'].sum()))
        for i, texto in enumerate(amostra['historico_limpo']):
            # Mostra só os primeiros 200 caracteres para não poluir a tela
            print(f"\nCaso {i+1}: {str(texto)[:200]}...")
    else:
        print("Nenhum caso de violência física detectado para auditar.")
    
    print("\n✅ Auditoria Concluída!")

if __name__ == "__main__":
    auditar_pipeline()