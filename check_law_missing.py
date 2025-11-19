import json
import pathlib
from collections import Counter

law_dir = pathlib.Path('backend/data/rag_sources/bank_laws')
path = next(iter(sorted(law_dir.glob('*.jsonl'))))
missing = Counter()
count = 0
with path.open(encoding='utf-8') as f:
    for line in f:
        line=line.strip()
        if not line:
            continue
        count += 1
        record = json.loads(line)
        for field in ('id','document_id','text','source'):
            if not record.get(field):
                missing[field] += 1

print('sample_file', path.name)
print('records', count)
print('missing', missing)
