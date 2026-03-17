import pandas as pd

def extracao_datetime(df, coluna):
    
    df[coluna] = pd.to_datetime(df[coluna], errors="coerce")
    
    df["ano"] = df[coluna].dt.year
    df["mes"] = df[coluna].dt.month
    df["dia"] = df[coluna].dt.day
    df["hora"] = df[coluna].dt.hour
    df["minuto"] = df[coluna].dt.minute
    df["segundo"] = df[coluna].dt.second
    
    return df

