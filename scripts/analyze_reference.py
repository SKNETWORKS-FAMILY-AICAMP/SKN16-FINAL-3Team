import pandas as pd

try:
    # 레퍼런스 파일 읽기
    df = pd.read_excel("docs/incoming/요구사항정의서_레퍼런스.xlsx", engine='openpyxl')
    print("=== 레퍼런스 문서 컬럼 ===")
    print(df.columns.tolist())
    print("\n=== 레퍼런스 데이터 (상위 5행) ===")
    print(df.head(5).to_string())
except Exception as e:
    print(f"Error reading excel: {e}")



