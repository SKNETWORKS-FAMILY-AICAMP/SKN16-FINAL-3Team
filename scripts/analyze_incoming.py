import pandas as pd
import sys

try:
    # 팀원들이 작성한 원본 파일 읽기
    df = pd.read_excel("docs/incoming/요구사항 정의서.xlsx", engine='openpyxl')
    print("=== 팀원 작성 문서 컬럼 ===")
    print(df.columns.tolist())
    print("\n=== 팀원 작성 데이터 (상위 10행) ===")
    print(df.head(10).to_string())
except Exception as e:
    print(f"Error reading excel: {e}")



