import pandas as pd
import geopandas as gpd
from shapely.geometry import Polygon
import numpy as np
import folium
import os

# Delimitação de palavra evita casamentos parciais ("BR" em BRASILIA/SOBRADINHO, "BAR" em BARRACO).
# A cidade fica fora da busca: o nome da RA não informa o tipo de local.
# "CONJUNTO" não entra em casa: no DF é unidade de endereçamento, não tipo de moradia.
PADROES_TIPO_LOCAL = {
    'APARTAMENTO': r'\b(?:APTO|APARTAMENTO|APT|BLOCO|EDIF\w*|ED|ANDAR|KITNET|RESIDENCIAL)\b',
    'CASA': r'\b(?:CASA|LOTE|CHACARA|FAZENDA)\b',
    'VIA PUBLICA': r'\b(?:RUA|AVENIDA|ESTACIONAMENTO|PARQUE|PRACA|VIA|BR|PASSARELA)\b|\bDF-',
    'COMERCIO / SERVICO': r'\b(?:BAR|LOJA|MERCADO|FARMACIA|SHOPPING|POSTO|DISTRIBUIDORA|RESTAURANTE|COMERCIO)\b',
}
TIPO_LOCAL_PADRAO = 'OUTROS / NÃO IDENTIFICADO'

# Os mapas são publicados: nenhum elemento pode remeter a uma vítima individual.
# Células com poucas ocorrências ficam fora do mapa, e os feminicídios aparecem só como contagem por RA.
K_MINIMO_CELULA = 5
K_MINIMO_RA = 3


def celulas_publicaveis(contagem, k=K_MINIMO_CELULA):
    """Mantém só as células com pelo menos k ocorrências."""
    return contagem[contagem['total_ocorrencias'] >= k]


def feminicidios_por_ra(ras):
    """Conta casos por RA; o mapa não exibe atributos de casos individuais."""
    return ras.dropna().str.strip().str.upper().value_counts()


def rotulo_contagem(n, k=K_MINIMO_RA):
    return f"{n} casos" if n >= k else f"menos de {k} casos"


def classificar_tipo_local(quadra, complemento):
    """Classifica o tipo de local pelo endereço; a ordem de PADROES_TIPO_LOCAL é a precedência."""
    endereco = quadra.fillna('').str.upper() + " " + complemento.fillna('').str.upper()
    tipo = pd.Series(TIPO_LOCAL_PADRAO, index=endereco.index)
    for categoria, padrao in reversed(list(PADROES_TIPO_LOCAL.items())):
        tipo = tipo.mask(endereco.str.contains(padrao, regex=True), categoria)
    return tipo


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

    df['TIPO_MORADIA'] = classificar_tipo_local(df['quadra'], df['complemento'])

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
        contagem_grid = celulas_publicaveis(intersecao_unica.groupby('id_celula').size().reset_index(name='total_ocorrencias'))
        grid_mapa = grid_export.merge(contagem_grid, on='id_celula')

        # Cria o mapa base
        mapa_risco = folium.Map(location=[-15.793889, -47.882778], zoom_start=11, tiles='CartoDB dark_matter')
        
        # Camada 1: Calor (Grade)
        folium.Choropleth(
            geo_data=grid_mapa, data=grid_mapa, columns=['id_celula', 'total_ocorrencias'],
            key_on='feature.properties.id_celula', fill_color='YlOrRd', fill_opacity=0.8, line_opacity=0.3,
            legend_name=f'Ocorrências da Lei Maria da Penha em 2024 (células de 500 m com {K_MINIMO_CELULA} ou mais)'
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
            anos = pd.to_datetime(df_fem['Data do Crime'], dayfirst=True, errors='coerce').dt.year
            periodo = f"{int(anos.min())}–{int(anos.max())}"

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
            
            # Um círculo por RA, com área proporcional ao número de casos (piso em K_MINIMO_RA,
            # para que o tamanho não revele contagens suprimidas).
            for ra_nome, n in feminicidios_por_ra(df_fem['RA']).items():
                if ra_nome not in coords_ra:
                    print(f"⚠️ RA sem centroide no mapa de feminicídios: {ra_nome} ({n} casos)")
                    continue
                folium.CircleMarker(
                    location=coords_ra[ra_nome],
                    radius=4 + 2 * np.sqrt(max(n, K_MINIMO_RA)),
                    color='red', fill=True, fill_color='darkred', fill_opacity=0.7,
                    tooltip=f"{ra_nome}: {rotulo_contagem(n)} de feminicídio ({periodo})",
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