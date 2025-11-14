import json
import re
from pathlib import Path

source_path = Path(r"C:\Users\JuYoung\Downloads\?˜ê²½?€??ì²´í¬ì¹´ë“œ_?„ì „??txt")
text = source_path.read_text(encoding='utf-8')

product = "?˜ê²½ My ì²´í¬ì¹´ë“œ"
product_code = "HK-CHE-2025-001"
source_name = source_path.name
created_at = "2025-11-10T01:26:15.525747Z"
chunking_meta = {"strategy": "structure", "max_len": 820, "overlap": 120}

part_pattern = re.compile(r"^??PART\s+(\d+)\.\s*(.+?) ??, re.MULTILINE)
subsection_pattern = re.compile(r"^??s*(.+)")

parts = []
last_index = 0
for match in part_pattern.finditer(text):
    part_no = int(match.group(1))
    part_title = match.group(2).strip()
    if parts:
        parts[-1]['content'] = text[last_index:match.start()].strip("\n")
    parts.append({"part_no": part_no, "part_title": part_title, "start": match.end(), "content": None})
    last_index = match.end()
if parts:
    parts[-1]['content'] = text[last_index:].strip("\n")

records = []

for part in parts:
    part_no = part['part_no']
    part_title = part['part_title']
    content = part['content']
    lines = content.splitlines()

    subsections = []
    current_title = None
    current_buffer = []

    def flush():
        nonlocal current_title, current_buffer
        if current_title:
            body = "\n".join(line.rstrip() for line in current_buffer).strip()
            if body:
                subsections.append((current_title, body))
        current_title = None
        current_buffer = []

    for line in lines:
        m = subsection_pattern.match(line)
        if m:
            flush()
            current_title = m.group(1).strip()
            remainder = line[m.end():].strip()
            if remainder:
                current_buffer.append(remainder)
        else:
            if current_title is None:
                current_title = part_title if part_no != 7 else "ì²´í¬ì¹´ë“œ ?½ê?"
            current_buffer.append(line)
    flush()

    if part_no == 7:
        # Combine all text and split by article range
        combined_text = "\n".join(body for _, body in subsections) if subsections else content.strip()
        articles = [a.strip() for a in re.split(r"(?=??d+ì¡?", combined_text) if a.strip()]
        subsections = []
        temp_chunk = []
        char_count = 0
        for article in articles:
            temp_chunk.append(article)
            char_count += len(article)
            if char_count >= 1200:
                chunk_text = "\n".join(temp_chunk)
                nums = re.findall(r"??\d+)ì¡?, chunk_text)
                title = f"?½ê? (??nums[0]}ì¡???nums[-1]}ì¡?" if nums else "?½ê?"
                subsections.append((title, chunk_text))
                temp_chunk = []
                char_count = 0
        if temp_chunk:
            chunk_text = "\n".join(temp_chunk)
            nums = re.findall(r"??\d+)ì¡?, chunk_text)
            title = f"?½ê? (??nums[0]}ì¡???nums[-1]}ì¡?" if nums else "?½ê?"
            subsections.append((title, chunk_text))

    section_counter = 0
    for sub_title, body in subsections:
        section_counter += 1
        chunk_id = f"{product_code}-P{part_no:02d}-S{section_counter:02d}-C001"
        record = {
            "id": chunk_id,
            "product": product,
            "product_code": product_code,
            "part_no": part_no,
            "part_title": part_title,
            "subsection_title": sub_title,
            "breadcrumb": f"PART {part_no}. {part_title} > {sub_title}",
            "chunk_index": 1,
            "text": body.strip(),
            "source": source_name,
            "created_at": created_at,
            "chunking": chunking_meta,
        }
        records.append(record)

# Ensure ?‘ì„±???•ë³´ ì¡´ì¬
if not any("?‘ì„±?? in rec['subsection_title'] for rec in records):
    tail_match = re.search(r"?‘ì„±??[\s\S]+", text)
    if tail_match:
        part_no = 8
        part_title = "ë°œê¸‰ ?ˆì°¨ ë°??œë¹„??
        existing = [rec for rec in records if rec['part_no'] == part_no]
        section_counter = len(existing) + 1
        chunk_id = f"{product_code}-P{part_no:02d}-S{section_counter:02d}-C001"
        records.append({
            "id": chunk_id,
            "product": product,
            "product_code": product_code,
            "part_no": part_no,
            "part_title": part_title,
            "subsection_title": "?‘ì„±??,
            "breadcrumb": f"PART {part_no}. {part_title} > ?‘ì„±??,
            "chunk_index": 1,
            "text": tail_match.group(0).strip(),
            "source": source_name,
            "created_at": created_at,
            "chunking": chunking_meta,
        })

output_path = Path(r"C:\cant\?˜ê²½?€??ì²´í¬ì¹´ë“œ_?„ì „??chunks.full.jsonl")
with output_path.open("w", encoding="utf-8") as f:
    for rec in records:
        json.dump(rec, f, ensure_ascii=False)
        f.write("\n")

print(f"Wrote {len(records)} records to {output_path}")
