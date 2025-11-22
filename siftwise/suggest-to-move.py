import pandas as pd

csv = r"C:\Users\leopa\Desktop\ArchiveTest\Sorted\.sift\Mapping.csv"

df = pd.read_csv(csv)

df.loc[df["Action"] == "Suggest", "Action"] = "Move"

df.to_csv(csv, index=False)
print("Updated Suggest → Move in Mapping.csv")
