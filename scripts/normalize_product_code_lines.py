import json
import re
from pathlib import Path

base_dir = Path('data/rag/hakyung')
pattern = re.compile(r'(\uc0c1\ud488\ucf54\ub4dc:\s*)([^\n]+)')

for json_path in base_dir.glob('*.jsonl'):
    records = []
    changed = False
    for line in json_path.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        data = json.loads(line)
        doc_id = data.get('document_id', '')

        def replace_value(value):
            if isinstance(value, str) and '\uc0c1\ud488\ucf54\ub4dc:' in value:
                new_value = pattern.sub(r'\1' + doc_id, value)
                return new_value
            return value

        new_data = {}
        for key, value in data.items():
            if isinstance(value, str):
                new_value = replace_value(value)
            elif isinstance(value, list):
                new_value = [replace_value(item) if isinstance(item, str) else item for item in value]
            else:
                new_value = value
            if new_value != value:
                changed = True
            new_data[key] = new_value
        records.append(new_data)
    if changed:
        with json_path.open('w', encoding='utf-8') as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False))
                f.write('\n')
        print(f'Normalized ?곹뭹肄붾뱶 in {json_path.name}')
