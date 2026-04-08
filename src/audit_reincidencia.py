import pandas as pd
import os
import random

base_dir = os.getcwd()
# Certifique-se de que está apontando para o arquivo que tem as colunas 'cidade', 'quadra', 'complemento', etc.
caminho_in = os.path.join(base_dir, "data", "base_analisada.csv")

print("🔍 Iniciando Auditoria Completa (Campeão Extremo + Amostra de 2 Chamados)...")
df = pd.read_csv(caminho_in)

# 1. Recriando a chave de busca (Cidade + Endereço)
df['COMPLEMENTO_CLEAN'] = df['complemento'].fillna('').str.upper()
df['QUADRA_CLEAN'] = df['quadra'].fillna('').str.upper()
df['ENDERECO_BUSCA'] = df['cidade'].fillna('').str.upper() + " " + df['QUADRA_CLEAN'] + " " + df['COMPLEMENTO_CLEAN']

# 2. Filtrando Casas e Apartamentos
cond_apt = df['ENDERECO_BUSCA'].str.contains(r'APTO|APARTAMENTO|APT|BLOCO|EDIF|ED\.|ANDAR|KITNET|RESIDENCIAL', regex=True)
cond_casa = df['ENDERECO_BUSCA'].str.contains(r'CASA|LOTE|CHACARA|FAZENDA|CONJUNTO', regex=True)
df_casas = df[cond_casa | cond_apt].copy()

# 3. Contando as repetições
contagem = df_casas['ENDERECO_BUSCA'].value_counts()

# ======================================================================
# PARTE 1: AUDITORIA DO "CAMPEÃO" (O CASO MAIS EXTREMO)
# ======================================================================
print("\n🚨 TOP 5 ENDEREÇOS COM MAIS CHAMADOS:")
print(contagem.head(5))

endereco_campeao = contagem.index[0]
total_chamados = contagem.iloc[0]

print(f"\n=======================================================")
print(f"🏆 LENDO OS {total_chamados} CASOS DO ENDEREÇO CAMPEÃO: {endereco_campeao}")
print(f"=======================================================\n")

# Filtra e ordena pela data para lermos a história na ordem cronológica
casos_campeao = df_casas[df_casas['ENDERECO_BUSCA'] == endereco_campeao].sort_values('data hora')

for index, row in casos_campeao.iterrows():
    data = row.get('data hora', 'Data não informada')
    hist = str(row.get('historico_limpo', row.get('historico', ''))).strip()
    
    print(f"🗓️ Data: {data}")
    print(f"📝 Relato: {hist[:200]}...") 
    print("-" * 50)

# ======================================================================
# PARTE 2: AUDITORIA DA BASE (AMOSTRA ALEATÓRIA DE 2 CHAMADOS)
# ======================================================================
print("\n\n🎲 INICIANDO AMOSTRAGEM ALEATÓRIA (CASOS COM EXATAMENTE 2 CHAMADOS)...")
enderecos_com_2 = contagem[contagem == 2].index.tolist()

if not enderecos_com_2:
    print("Nenhum endereço com 2 chamados encontrado.")
else:
    print(f"✅ Total de endereços com 2 chamados: {len(enderecos_com_2)}")
    
    # Sorteia 3 endereços aleatórios da lista de casas com 2 chamadas
    amostra = random.sample(enderecos_com_2, min(3, len(enderecos_com_2)))
    
    for endereco in amostra:
        print(f"\n=======================================================")
        print(f"🏠 AUDITANDO ENDEREÇO (2 CHAMADOS): {endereco}")
        print(f"=======================================================\n")
        
        casos = df_casas[df_casas['ENDERECO_BUSCA'] == endereco].sort_values('data hora')
        
        for _, row in casos.iterrows():
            data = row.get('data hora', 'N/A')
            hist = str(row.get('historico_limpo', row.get('historico', ''))).strip()
            print(f"🗓️ Data: {data}")
            print(f"📝 Relato: {hist[:200]}...")
            print("-" * 50)