"""CRD-CRE 상품 데이터 분석 - 벡터 검색 어려운 요인 찾기"""
import json
from pathlib import Path

file_path = Path("data/rag_sources/products/hakyung/CRD-CRE.jsonl")

with open(file_path, 'r', encoding='utf-8') as f:
    chunks = [json.loads(line) for line in f]

print("=" * 80)
print("CRD-CRE 상품 데이터 분석 - 벡터 검색 어려운 요인 찾기")
print("=" * 80)

# 1. 청크 길이 분석
text_lengths = [len(chunk.get('text', '')) for chunk in chunks]
print(f"\n[1] 청크 길이 분석")
print(f"  - 총 청크 수: {len(chunks)}")
print(f"  - 최소 길이: {min(text_lengths)}자")
print(f"  - 최대 길이: {max(text_lengths)}자")
print(f"  - 평균 길이: {sum(text_lengths)/len(text_lengths):.1f}자")
print(f"  - 중간값: {sorted(text_lengths)[len(text_lengths)//2]}자")

short_chunks = [chunk for chunk in chunks if len(chunk.get('text', '')) < 100]
print(f"\n  ⚠️ 매우 짧은 청크 (100자 미만): {len(short_chunks)}개")
for chunk in short_chunks[:5]:
    text = chunk.get('text', '')[:60]
    print(f"    - {chunk.get('subsection_title', '')}: {text}...")

# 2. 표 형식 데이터
table_chunks = [chunk for chunk in chunks if '│' in chunk.get('text', '')]
print(f"\n[2] 표 형식 데이터 포함 청크: {len(table_chunks)}개")
for chunk in table_chunks:
    print(f"  - {chunk.get('subsection_title', '')}")

# 3. 비교 문구
comparison_chunks = [chunk for chunk in chunks if 'vs' in chunk.get('text', '').lower() or '비교' in chunk.get('subsection_title', '')]
print(f"\n[3] 비교 문구 포함 청크: {len(comparison_chunks)}개")
for chunk in comparison_chunks:
    print(f"  - {chunk.get('subsection_title', '')}")

# 4. 중복/반복 구조
print(f"\n[4] 반복되는 구조 패턴")
repeat_patterns = {}
for chunk in chunks:
    text = chunk.get('text', '')
    # PART X. 패턴 추출
    if 'PART' in text and '>' in text:
        parts = text.split('>')
        if len(parts) >= 1:
            part_prefix = parts[0].strip()
            if part_prefix not in repeat_patterns:
                repeat_patterns[part_prefix] = []
            repeat_patterns[part_prefix].append(chunk.get('subsection_title', ''))

high_repeat = {k: v for k, v in repeat_patterns.items() if len(v) > 3}
if high_repeat:
    print(f"  ⚠️ 반복 패턴이 많은 섹션:")
    for part, subsections in list(high_repeat.items())[:3]:
        print(f"    - {part}: {len(subsections)}개 청크")

# 5. 복합 정보가 섞인 긴 청크
long_complex_chunks = [chunk for chunk in chunks if len(chunk.get('text', '')) > 300 and (',' in chunk.get('text', '') or '\n' in chunk.get('text', ''))]
print(f"\n[5] 복합 정보가 섞인 긴 청크 (300자 이상, 여러 정보 포함): {len(long_complex_chunks)}개")
for chunk in long_complex_chunks:
    text_preview = chunk.get('text', '')[:80]
    print(f"  - {chunk.get('subsection_title', '')}: {text_preview}...")

# 6. 숫자/금액 정보 밀도
print(f"\n[6] 숫자/금액 정보 분석")
number_dense_chunks = []
for chunk in chunks:
    text = chunk.get('text', '')
    # 숫자 패턴 (금액, 퍼센트 등)
    import re
    numbers = re.findall(r'\d+[,\d]*(?:원|%|만원|억원|퍼센트|개월|일|회)', text)
    if len(numbers) >= 3:  # 3개 이상 숫자 패턴
        number_dense_chunks.append((chunk, len(numbers)))

if number_dense_chunks:
    print(f"  ⚠️ 숫자/금액 정보가 많은 청크:")
    for chunk, num_count in sorted(number_dense_chunks, key=lambda x: x[1], reverse=True)[:5]:
        print(f"    - {chunk.get('subsection_title', '')}: {num_count}개 숫자 패턴")

# 7. 단순 반복 청크 (의미가 거의 없는 청크)
print(f"\n[7] 단순 반복 청크 (제목만 반복)")
meaningless_chunks = []
for chunk in chunks:
    text = chunk.get('text', '')
    lines = text.split('\n')
    # 제목이 본문과 거의 동일한 경우
    if len(lines) >= 2:
        title_part = lines[0].split('>')[-1].strip() if '>' in lines[0] else ''
        content_part = lines[1].strip() if len(lines) > 1 else ''
        # ▣ 뒤의 내용과 제목이 거의 동일
        if '▣' in content_part:
            content_clean = content_part.split('▣')[-1].strip()
            if title_part and content_clean and title_part[:20] == content_clean[:20]:
                meaningless_chunks.append(chunk)

if meaningless_chunks:
    print(f"  ⚠️ 의미 없는 반복 청크: {len(meaningless_chunks)}개")
    for chunk in meaningless_chunks[:5]:
        print(f"    - {chunk.get('subsection_title', '')}")

print("\n" + "=" * 80)
print("분석 완료")
print("=" * 80)

