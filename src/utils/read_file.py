import pandas as pd 

def read_file(caminho):

    df = pd.read_excel(
        caminho,
        sheet_name="LEI 11.340 - MARIA DA PENHA",
        header=3,
        usecols="B:K", 
        skipfooter= 3
    )

    df.columns = df.columns.str.lower()

    print(df.shape)
    print(df.columns)
    print(df.head())

    return df