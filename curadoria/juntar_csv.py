import pandas as pd
import glob

arquivos = glob.glob("*.csv")

dfs = []

for arquivo in arquivos:
    try:
        df = pd.read_csv(arquivo)
        dfs.append(df)
        print(f"OK: {arquivo}")
    except Exception as e:
        print(f"ERRO em {arquivo}: {e}")

resultado = pd.concat(dfs, ignore_index=True)

resultado.to_csv("MASTER_SHOPEE.csv", index=False)

print("Arquivo final criado!")