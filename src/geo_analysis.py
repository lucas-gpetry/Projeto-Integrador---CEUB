import pandas as pd
import geopandas as gpd
from shapely.geometry import Polygon
import numpy as np
import folium 
import os

def processar_geoespacial():
    """
    Lê a base limpa, gera features de Turno e Moradia via Regex de endereços, 
    calcula reincidência, corrige coordenadas e aplica o Spatial Join com a grade UTM de 500m.
    Salva a base final e exporta o mapa interativo com os Batalhões da PMDF.
    """
    base_dir = os.getcwd()
    caminho_in = os.path.join(base_dir, "data", "base_limpa.csv")
    caminho_bat = os.path.join(base_dir, "data", "batalhoes_pmdf.csv") # Onde ficarão os batalhões
    caminho_out = os.path.join(base_dir, "data", "base_espacial.csv")
    caminho_grade = os.path.join(base_dir, "data", "grade_espacial_df_LIMPA.geojson") 
    docs_dir = os.path.join(base_dir, "docs")

    os.makedirs(docs_dir, exist_ok=True)

    print("🚀 Lendo dados e corrigindo coordenadas...")
    df = pd.read_csv(caminho_in)
    df['latitude'] = df['latitude'].astype(str).str.replace(',', '.').astype(float)
    df['longitude'] = df['longitude'].astype(str).str.replace(',', '.').astype(float)

    # --- 1. ENGENHARIA DE FEATURES (Moradia e Turno) ---
    print("Criando variáveis de Turno e Tipo de Moradia...")
    df['COMPLEMENTO_CLEAN'] = df['complemento'].fillna('').str.upper()
    df['QUADRA_CLEAN'] = df['quadra'].fillna('').str.upper()
    df['ENDERECO_BUSCA'] = df['QUADRA_CLEAN'] + " " + df['COMPLEMENTO_CLEAN']

    cond_apt = df['ENDERECO_BUSCA'].str.contains(r'APTO|APARTAMENTO|APT|BLOCO|EDIF|ED\.|ANDAR|KITNET|RESIDENCIAL', regex=True)
    cond_casa = df['ENDERECO_BUSCA'].str.contains(r'CASA|LOTE|CHACARA|FAZENDA|CONJUNTO', regex=True)
    cond_via = df['ENDERECO_BUSCA'].str.contains(r'RUA|AVENIDA|ESTACIONAMENTO|PARQUE|PRACA|VIA|BR|DF-|PASSARELA', regex=True)
    cond_comercio = df['ENDERECO_BUSCA'].str.contains(r'BAR|LOJA|MERCADO|FARMACIA|SHOPPING|POSTO|DISTRIBUIDORA|RESTAURANTE|COMERCIO', regex=True)

    df['TIPO_MORADIA'] = 'OUTROS / NÃO IDENTIFICADO'
    df.loc[cond_casa, 'TIPO_MORADIA'] = 'CASA'
    df.loc[cond_apt, 'TIPO_MORADIA'] = 'APARTAMENTO'
    df.loc[cond_via & (df['TIPO_MORADIA'] == 'OUTROS / NÃO IDENTIFICADO'), 'TIPO_MORADIA'] = 'VIA PUBLICA'
    df.loc[cond_comercio & (df['TIPO_MORADIA'] == 'OUTROS / NÃO IDENTIFICADO'), 'TIPO_MORADIA'] = 'COMERCIO / SERVICO'

    bins = [-1, 5, 11, 17, 23]
    labels = ['Madrugada', 'Manhã', 'Tarde', 'Noite']
    df['TURNO'] = pd.cut(df['hora'], bins=bins, labels=labels)

    # --- 2. ANÁLISE DE REINCIDÊNCIA (Eixo 3) ---
    print("Analisando reincidência por endereço...")
    contagem_enderecos = df['ENDERECO_BUSCA'].value_counts()
    df['reincidencia_endereco'] = df['ENDERECO_BUSCA'].map(contagem_enderecos)

    # Limpando colunas temporárias
    df.drop(columns=['COMPLEMENTO_CLEAN', 'QUADRA_CLEAN', 'ENDERECO_BUSCA'], inplace=True)

    # --- 3. CIRURGIA DE GPS E GRADE ESPACIAL ---
    print("Realizando clusterização espacial (Grade 500m)...")
    
    # Criamos uma CÓPIA apenas para fazer a matemática espacial, sem destruir o df original de 12 mil linhas
    df_espacial = df.dropna(subset=['latitude', 'longitude']).copy()
    df_espacial = df_espacial[(df_espacial['latitude'] != 0) & (df_espacial['longitude'] != 0)]

    if not df_espacial.empty:
        # Achando e isolando o "Buraco Negro"
        coord_viciada = df_espacial.groupby(['latitude', 'longitude']).size().idxmax()
        df_limpo_gps = df_espacial[~((df_espacial['latitude'] == coord_viciada[0]) & (df_espacial['longitude'] == coord_viciada[1]))].copy()

        # Matemática do Grid...
        gdf = gpd.GeoDataFrame(df_limpo_gps, geometry=gpd.points_from_xy(df_limpo_gps['longitude'], df_limpo_gps['latitude']), crs="EPSG:4326")
        gdf_utm = gdf.to_crs("EPSG:31983")
        
        xmin, ymin, xmax, ymax = gdf_utm.total_bounds
        tamanho_celula = 500 

        cols = list(np.arange(xmin, xmax, tamanho_celula))
        rows = list(np.arange(ymin, ymax, tamanho_celula))
        poligonos = [Polygon([(x, y), (x + tamanho_celula, y), (x + tamanho_celula, y + tamanho_celula), (x, y + tamanho_celula)]) for x in cols[:-1] for y in rows[:-1]]

        grid = gpd.GeoDataFrame({'id_celula': range(len(poligonos))}, geometry=poligonos, crs="EPSG:31983")

        # Cruzamento (Sjoin)
        intersecao = gpd.sjoin(gdf_utm, grid, how='inner', predicate='intersects')
        
        # Garante que não haja índices duplicados antes do merge
        intersecao_unica = intersecao[~intersecao.index.duplicated(keep='first')]

        # Onde não houver GPS válido, o id_celula vai ficar como NaN (vazio).
        df_final = df.merge(intersecao_unica[['id_celula']], left_index=True, right_index=True, how='left')
        
        # --- Exportando a Grade (Mapas) ---
        grid_export = grid[grid['id_celula'].isin(df_final['id_celula'].dropna().unique())].to_crs("EPSG:4326")
        grid_export.to_file(caminho_grade, driver='GeoJSON')
        
        print("Gerando mapa interativo (Ocorrências vs Batalhões)...")
        contagem_grid = intersecao_unica.groupby('id_celula').size().reset_index(name='total_ocorrencias')
        grid_mapa = grid_export.merge(contagem_grid, on='id_celula')

        mapa_risco = folium.Map(location=[-15.793889, -47.882778], zoom_start=11, tiles='CartoDB dark_matter')
        
        # Camada 1: Mapa de Calor (Grade)
        folium.Choropleth(
            geo_data=grid_mapa, data=grid_mapa, columns=['id_celula', 'total_ocorrencias'],
            key_on='feature.properties.id_celula', fill_color='YlOrRd', fill_opacity=0.8, line_opacity=0.3,
            legend_name='Risco Real (Nº de Ocorrências)'
        ).add_to(mapa_risco)
        
        # Camada 2: Batalhões da PMDF
        if os.path.exists(caminho_bat):
            df_bat = pd.read_csv(caminho_bat)
            for _, bat in df_bat.iterrows():
                # O parâmetro icon='shield' usa um ícone de escudo. A cor 'blue' contrasta com a grade vermelha.
                folium.Marker(
                    location=[bat['Latitude'], bat['Longitude']],
                    popup=f"<b>{bat['Nome do Batalhão']}</b><br>{bat['Endereço']}",
                    tooltip=bat['Nome do Batalhão'],
                    icon=folium.Icon(color='blue', icon='shield', prefix='fa')
                ).add_to(mapa_risco)
        else:
            print("⚠️ Arquivo de batalhões não encontrado. O mapa foi gerado sem eles.")
        
        caminho_mapa = os.path.join(docs_dir, "mapa_crime_vs_batalhoes.html")
        mapa_risco.save(caminho_mapa)
        print(f"🗺️ Mapa salvo em: {caminho_mapa}")

    else:
        df_final = df

    # --- 4. SALVAR ---
    # Salva a base preservando todas as 12 mil linhas e a nova coluna 'reincidencia_endereco'
    df_final.to_csv(caminho_out, index=False, encoding='utf-8-sig')
    print(f"Base espacial salva em: {caminho_out} com {len(df_final)} linhas!")

if __name__ == "__main__":
    processar_geoespacial()