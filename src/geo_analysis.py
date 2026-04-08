import pandas as pd
import geopandas as gpd
from shapely.geometry import Polygon
import numpy as np
import folium 
import os

def processar_geoespacial():
    base_dir = os.getcwd()
    caminho_in = os.path.join(base_dir, "data", "base_limpa.csv")
    caminho_bat = os.path.join(base_dir, "data", "batalhoes_pmdf.csv") 
    caminho_fem = os.path.join(base_dir, "data", "feminicidios_pcdf.csv") 
    caminho_out = os.path.join(base_dir, "data", "base_espacial.csv")
    caminho_grade = os.path.join(base_dir, "data", "grade_espacial_df_LIMPA.geojson") 
    docs_dir = os.path.join(base_dir, "docs")

    os.makedirs(docs_dir, exist_ok=True)

    print("🚀 Lendo dados e corrigindo coordenadas...")
    df = pd.read_csv(caminho_in)
    df['latitude'] = df['latitude'].astype(str).str.replace(',', '.').astype(float)
    df['longitude'] = df['longitude'].astype(str).str.replace(',', '.').astype(float)

    # --- 1. ENGENHARIA DE FEATURES ---
    print("Criando variáveis de Turno e Tipo de Moradia...")
    df['COMPLEMENTO_CLEAN'] = df['complemento'].fillna('').str.upper()
    df['QUADRA_CLEAN'] = df['quadra'].fillna('').str.upper()
    df['ENDERECO_BUSCA'] = df['cidade'].fillna('').str.upper() + " " + df['QUADRA_CLEAN'] + " " + df['COMPLEMENTO_CLEAN']

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

    # --- 2. ANÁLISE DE REINCIDÊNCIA ---
    print("Analisando reincidência por endereço...")
    contagem_enderecos = df['ENDERECO_BUSCA'].value_counts()
    df['reincidencia_endereco'] = df['ENDERECO_BUSCA'].map(contagem_enderecos)
    df.drop(columns=['COMPLEMENTO_CLEAN', 'QUADRA_CLEAN', 'ENDERECO_BUSCA'], inplace=True)

    # --- 3. GRADE ESPACIAL E SJOIN ---
    print("Realizando clusterização espacial (Grade 500m)...")
    df_espacial = df.dropna(subset=['latitude', 'longitude']).copy()
    df_espacial = df_espacial[(df_espacial['latitude'] != 0) & (df_espacial['longitude'] != 0)]

    if not df_espacial.empty:
        coord_viciada = df_espacial.groupby(['latitude', 'longitude']).size().idxmax()
        df_limpo_gps = df_espacial[~((df_espacial['latitude'] == coord_viciada[0]) & (df_espacial['longitude'] == coord_viciada[1]))].copy()

        gdf = gpd.GeoDataFrame(df_limpo_gps, geometry=gpd.points_from_xy(df_limpo_gps['longitude'], df_limpo_gps['latitude']), crs="EPSG:4326")
        gdf_utm = gdf.to_crs("EPSG:31983")
        
        xmin, ymin, xmax, ymax = gdf_utm.total_bounds
        tamanho_celula = 500 

        cols = list(np.arange(xmin, xmax, tamanho_celula))
        rows = list(np.arange(ymin, ymax, tamanho_celula))
        poligonos = [Polygon([(x, y), (x + tamanho_celula, y), (x + tamanho_celula, y + tamanho_celula), (x, y + tamanho_celula)]) for x in cols[:-1] for y in rows[:-1]]

        grid = gpd.GeoDataFrame({'id_celula': range(len(poligonos))}, geometry=poligonos, crs="EPSG:31983")
        intersecao = gpd.sjoin(gdf_utm, grid, how='inner', predicate='intersects')
        intersecao_unica = intersecao[~intersecao.index.duplicated(keep='first')]
        df_final = df.merge(intersecao_unica[['id_celula']], left_index=True, right_index=True, how='left')
        
        grid_export = grid[grid['id_celula'].isin(df_final['id_celula'].dropna().unique())].to_crs("EPSG:4326")
        grid_export.to_file(caminho_grade, driver='GeoJSON')
        
        # --- 4. MAPA DE CAMADAS ---
        print("Gerando Mapas Interativos...")
        contagem_grid = intersecao_unica.groupby('id_celula').size().reset_index(name='total_ocorrencias')
        grid_mapa = grid_export.merge(contagem_grid, on='id_celula')

        # Cria o mapa base
        mapa_risco = folium.Map(location=[-15.793889, -47.882778], zoom_start=11, tiles='CartoDB dark_matter')
        
        # Camada 1: Calor (Grade)
        folium.Choropleth(
            geo_data=grid_mapa, data=grid_mapa, columns=['id_celula', 'total_ocorrencias'],
            key_on='feature.properties.id_celula', fill_color='YlOrRd', fill_opacity=0.8, line_opacity=0.3,
            legend_name='Risco Real (Nº de Chamados 190)'
        ).add_to(mapa_risco)
        
        # Camada 2: Batalhões
        if os.path.exists(caminho_bat):
            df_bat = pd.read_csv(caminho_bat)
            for _, bat in df_bat.iterrows():
                folium.Marker(
                    location=[bat['Latitude'], bat['Longitude']],
                    tooltip=bat['Nome do Batalhão'],
                    icon=folium.Icon(color='blue', icon='shield', prefix='fa')
                ).add_to(mapa_risco)

        # SALVA O PRIMEIRO MAPA (Apenas PMDF)
        caminho_mapa_1 = os.path.join(docs_dir, "mapa_1_batalhoes.html")
        mapa_risco.save(caminho_mapa_1)
        print(f"🗺️ Mapa 1 (Batalhões) salvo em: {caminho_mapa_1}")

        # Camada 3: Feminicídios (Inteligência Geográfica por RA)
        if os.path.exists(caminho_fem):
            df_fem = pd.read_csv(caminho_fem, encoding='latin1', sep=';')
            
            if 'Idade - Vítima' in df_fem.columns:
                df_fem['Idade - Vítima'] = pd.to_numeric(df_fem['Idade - Vítima'], errors='coerce')
            if 'Idade - Autor' in df_fem.columns:
                df_fem['Idade - Autor'] = pd.to_numeric(df_fem['Idade - Autor'], errors='coerce')

            coords_ra = {
                'ÁGUAS CLARAS': [-15.8390, -48.0240], 'ARNIQUEIRAS': [-15.8480, -48.0050],
                'BRAZLÂNDIA': [-15.6669, -48.2001], 'CANDANGOLÂNDIA': [-15.8500, -47.9450],
                'CEILÂNDIA': [-15.8194, -48.1030], 'CRUZEIRO': [-15.7870, -47.9350],
                'FERCAL': [-15.5800, -47.8700], 'GAMA': [-16.0150, -48.0650],
                'GUARÁ': [-15.8300, -47.9790], 'ITAPOÃ': [-15.7360, -47.7560],
                'JARDIM BOTANICO': [-15.8640, -47.7810], 'LAGO SUL': [-15.8390, -47.8640],
                'NÚCLEO BANDEIRANTE': [-15.8690, -47.9650], 'PARANOÁ': [-15.7725, -47.7770],
                'PARK WAY': [-15.8850, -47.9540], 'PLANALTINA': [-15.6174, -47.6534],
                'PLANO PILOTO': [-15.7938, -47.8827], 'POR DO SOL/SOL NASCENTE': [-15.8270, -48.1300],
                'RECANTO DAS EMAS': [-15.9070, -48.0770], 'RIACHO FUNDO': [-15.8821, -48.0152],
                'RIACHO FUNDO II': [-15.8940, -48.0380], 'SAMAMBAIA': [-15.8741, -48.0838],
                'SANTA MARIA': [-16.0180, -48.0120], 'SÃO SEBASTIÃO': [-15.9080, -47.7710],
                'SCIA E ESTRUTURAL': [-15.7836, -47.9834], 'SIA (SETOR DE INDUSTRIA E ABASTECIMENTO)': [-15.8050, -47.9500],
                'SOBRADINHO': [-15.6515, -47.7912], 'SOBRADINHO II': [-15.6320, -47.8220],
                'SUDOESTE': [-15.7980, -47.9250], 'TAGUATINGA': [-15.8335, -48.0560],
                'VICENTE PIRES': [-15.8080, -48.0280]
            }
            
            for _, fem in df_fem.iterrows():
                ra_nome = str(fem.get('RA', '')).strip().upper()
                centroide = coords_ra.get(ra_nome, [-15.7938, -47.8827]) 
                
                lat_jitter = centroide[0] + np.random.normal(0, 0.015) 
                lon_jitter = centroide[1] + np.random.normal(0, 0.015)
                
                meio = fem.get('Meio Utilizado', 'Não Informado')
                local = fem.get('Local', 'Não Informado')
                motivo = fem.get('Motivação', 'Não Informada')
                data_crime = fem.get('Data do Crime', 'Data Desconhecida')
                
                id_vit = fem.get('Idade - Vítima', np.nan)
                id_aut = fem.get('Idade - Autor', np.nan)
                str_id_vit = f"{int(id_vit)} anos" if pd.notna(id_vit) else "Não Informada"
                str_id_aut = f"{int(id_aut)} anos" if pd.notna(id_aut) else "Não Informada"

                texto_popup = (f"<div style='width: 200px; font-family: Arial;'>"
                               f"<h4 style='color: darkred; margin-bottom: 5px;'>🛑 FEMINICÍDIO</h4>"
                               f"<b>Data:</b> {data_crime}<br>"
                               f"<b>RA:</b> {ra_nome}<br>"
                               f"<b>Local:</b> {local}<br>"
                               f"<b>Motivação:</b> {motivo}<br>"
                               f"<b>Arma/Meio:</b> {meio}<br>"
                               f"<hr style='margin: 5px 0;'>"
                               f"<b>Idade Vítima:</b> {str_id_vit}<br>"
                               f"<b>Idade Autor:</b> {str_id_aut}</div>")

                folium.CircleMarker(
                    location=[lat_jitter, lon_jitter],
                    radius=5, 
                    color='red', fill=True, fill_color='darkred', fill_opacity=0.9,
                    tooltip=f"Feminicídio: {meio}",
                    popup=folium.Popup(texto_popup, max_width=300)
                ).add_to(mapa_risco)

        # SALVA O SEGUNDO MAPA (PMDF + PCDF)
        caminho_mapa_2 = os.path.join(docs_dir, "mapa_2_feminicidios.html")
        mapa_risco.save(caminho_mapa_2)
        print(f"🗺️ Mapa 2 (Completo com Feminicídios) salvo em: {caminho_mapa_2}")

    else:
        df_final = df

    df_final.to_csv(caminho_out, index=False, encoding='utf-8-sig')

if __name__ == "__main__":
    processar_geoespacial()