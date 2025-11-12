import json
from pathlib import Path

input_path = Path('C:/Users/JuYoung/Downloads/\ud558\uacbd\uc740\ud589_\uc885\ud569\uc0c1\ud488\uac00\uc774\ub4dc_15\uac1c_\uc644\uc804\ud310.txt')
output_path = Path('data/rag/hakyung/DOC-GDE.jsonl')
lines = input_path.read_text(encoding='utf-8').splitlines()
product = '\ud558\uacbd\uc740\ud589 \uc885\ud569 \uc0c1\ud488 \uac00\uc774\ub4dc (15\uac1c \uc0c1\ud488)'
product_code = 'DOC-GDE'
document_id = 'DOC-GDE'
parts = []
current_title = None
current_lines = []
part_no = 0

for line in lines:
    stripped = line.strip()
    if '\u3010' in stripped and '\u3011' in stripped:
        heading = stripped[stripped.find('\u3010') + 1:stripped.find('\u3011')].strip()
        if current_title is not None:
            parts.append((part_no, current_title, current_lines))
        part_no += 1
        current_title = heading if heading else '\uc139\uc158'
        current_lines = [line]
    else:
        if current_title is None:
            if not parts and not current_lines:
                current_title = '\ud504\ub864\ub85c\uadf8'
                part_no = 1
                current_lines = [line]
            else:
                current_lines.append(line)
        else:
            current_lines.append(line)

if current_title is not None:
    parts.append((part_no, current_title, current_lines))

normalized_parts = []
for idx, (no, title, chunk_lines) in enumerate(parts, start=1):
    normalized_parts.append((idx, title, chunk_lines))

output_path.parent.mkdir(parents=True, exist_ok=True)
with output_path.open('w', encoding='utf-8') as f:
    for part_no, title, chunk_lines in normalized_parts:
        text_block = '\n'.join(chunk_lines).strip()
        if not text_block:
            continue
        record = {
            'id': f'{document_id}-P{part_no:02d}-S01-C001',
            'document_id': document_id,
            'product': product,
            'product_code': product_code,
            'part_no': part_no,
            'part_title': title,
            'subsection_title': title,
            'breadcrumb': title,
            'chunk_index': 1,
            'text': text_block,
            'source': input_path.name,
            'created_at': '2025-11-10T02:35:00Z',
            'chunking': {
                'strategy': 'section',
                'max_len': len(text_block),
                'overlap': 0,
            },
        }
        f.write(json.dumps(record, ensure_ascii=False))
        f.write('\n')
