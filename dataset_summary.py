import json
import pathlib
from collections import Counter

base = pathlib.Path('backend/data/rag_sources')
summary = {}

law_dir = base / 'bank_laws'
law_files = sorted([p for p in law_dir.glob('*.jsonl')])
prod_dir = base / 'products' / 'hakyung'
prod_files = sorted([p for p in prod_dir.glob('*.jsonl')])

law_records = 0
law_missing_files = 0
law_sections_total = 0
law_sections_counts = []

for path in law_files:
    count = 0
    has_missing = False
    sections = set()
    with path.open(encoding='utf-8') as f:
        for line in f:
            line=line.strip()
            if not line:
                continue
            record = json.loads(line)
            count += 1
            sections.add(record.get('section_title') or record.get('breadcrumb'))
            if not all(record.get(field) for field in ('id','document_id','text','source')):
                has_missing = True
    law_records += count
    law_sections_counts.append(len(sections))
    if has_missing:
        law_missing_files += 1

prod_records = 0
prod_missing_files = 0
prod_sections_counts = []

for path in prod_files:
    count = 0
    has_missing = False
    sections = set()
    with path.open(encoding='utf-8') as f:
        for line in f:
            line=line.strip()
            if not line:
                continue
            record = json.loads(line)
            count += 1
            sections.add(record.get('part_title') or record.get('breadcrumb'))
            if not all(record.get(field) for field in ('id','document_id','text','source')):
                has_missing = True
    prod_records += count
    prod_sections_counts.append(len(sections))
    if has_missing:
        prod_missing_files += 1

summary['bank_laws'] = {
    'files': len(law_files),
    'records': law_records,
    'files_with_missing_core': law_missing_files,
    'avg_sections_per_file': round(sum(law_sections_counts)/len(law_sections_counts),2),
    'min_sections': min(law_sections_counts),
    'max_sections': max(law_sections_counts),
}
summary['products'] = {
    'files': len(prod_files),
    'records': prod_records,
    'files_with_missing_core': prod_missing_files,
    'avg_sections_per_file': round(sum(prod_sections_counts)/len(prod_sections_counts),2),
    'min_sections': min(prod_sections_counts),
    'max_sections': max(prod_sections_counts),
}

print(summary)

if law_files:
    sample = law_files[0]
    count = 0
    sections=set()
    has_missing=False
    with sample.open(encoding='utf-8') as f:
        for line in f:
            line=line.strip()
            if not line:
                continue
            record=json.loads(line)
            count+=1
            sections.add(record.get('section_title') or record.get('breadcrumb'))
            if not all(record.get(field) for field in ('id','document_id','text','source')):
                has_missing=True
    print({'sample_file': sample.name, 'records': count, 'sections': len(sections), 'missing_core_field': has_missing})

if prod_files:
    sample = prod_files[0]
    count = 0
    sections=set()
    has_missing=False
    with sample.open(encoding='utf-8') as f:
        for line in f:
            line=line.strip()
            if not line:
                continue
            record=json.loads(line)
            count+=1
            sections.add(record.get('part_title') or record.get('breadcrumb'))
            if not all(record.get(field) for field in ('id','document_id','text','source')):
                has_missing=True
    print({'sample_file': sample.name, 'records': count, 'sections': len(sections), 'missing_core_field': has_missing})
