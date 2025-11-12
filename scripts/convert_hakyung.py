import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

MAX_LEN = 800
OVERLAP = 120

PART_RE = re.compile(r'^\u3010\s*PART\s+(\d+)\.\s*(.+?)\s*\u3011(?:[\u2500-\u257f\s]*)$')
SECTION_RE = re.compile(r'^\u3010\s*(.+?)\s*\u3011(?:[\u2500-\u257f\s]*)$')
SUB_RE = re.compile(r'^\u25a3\s*(.+?)\s*$')
ARTICLE_RE = re.compile(r'^(\u81f3?\uc81c\d+\uc870)\s*(?:\((.+?)\)|[:\uff1a]\s*(.+))?')
PRODUCT_PATTERN = re.compile(r'\u25a3\s*\uc0c1\ud488\uba85:\s*(.+)')
ARTICLE_PART_KEYWORD = '\uc57d\uad00'
LINE_DECOR_CHARS = set('\u2500\u2501\u2502\u2503\u2504\u2505\u2506\u2507\u2508\u2509\u250a\u250b\u250c\u250d\u250e\u250f\u2510\u2511\u2512\u2513\u2514\u2515\u2516\u2517\u2518\u2519\u251a\u251b\u251c\u251d\u251e\u251f\u2520\u2521\u2522\u2523\u2524\u2525\u2526\u2527\u2528\u2529\u252a\u252b\u252c\u252d\u252e\u252f\u2530\u2531\u2532\u2533\u2534\u2535\u2536\u2537\u2538\u2539\u253a\u253b\u253c\u253d\u253e\u253f\u2540\u2541\u2542\u2543\u2544\u2545\u2546\u2547\u2548\u2549\u254a\u254b\u254c\u254d\u254e\u254f\u2550\u2551\u2552\u2553\u2554\u2555\u2556\u2557\u2558\u2559\u255a\u255b\u255c\u255d\u255e\u255f\u2560\u2561\u2562\u2563\u2564\u2565\u2566\u2567\u2568\u2569\u256a\u256b\u256c\u256d\u256e\u256f\u2570\u2571\u2572\u2573\u2574\u2575\u2576\u2577\u2578\u2579\u257a\u257b\u257c\u257d\u257e\u257f ')

FILENAME_TO_CODE = {
    '\ud558\uacbd\uc740\ud589_\uccb4\ud06c\uce74\ub4dc_\uc644\uc804\ud310': 'CRD-DEB',
    '\ud558\uacbd\uc740\ud589_\uccad\ub144\uce74\ub4dc_\uc644\uc804\ud310': 'CRD-YTH',
    '\ud558\uacbd\uc740\ud589_\uc2e0\uc6a9\uce74\ub4dc_\uc644\uc804\ud310': 'CRD-CRE',
    '\ud558\uacbd\uc740\ud589_\uc804\uc138\uc790\uae08\ub300\ucd9c_\uc644\uc804\ud310': 'LON-JNS',
    '\ud558\uacbd\uc740\ud589_\uc2e0\uc6a9\ub300\ucd9c_\uc644\uc804\ud310': 'LON-UNS',
    '\ud558\uacbd\uc740\ud589_\uc608\uab0d\ub2f4\ubcf4\ub300\ucd9c_\uc644\uc804\ud310': 'LON-DCL',
    '\ud558\uacbd\uc740\ud589_\ub9c8\uc774\ub108\uc2a4\ud1b5\uc7a5_\uc644\uc804\ud310': 'LON-ODL',
    '\ud558\uacbd\uc740\ud589_\uccad\ub144\ud76c\ub9dd\ub300\ucd9c_\uc644\uc804\ud310': 'LON-YHP',
    '\ud558\uacbd\uc740\ud589_\uc8fc\ud0dd\ub2f4\ubcf4\ub300\ucd9c_\uc644\uc804\ud310': 'LON-MTG',
    '\ud558\uacbd\uc740\ud589_\ud559\uc790\uae08\ub300\ucd9c_\uc644\uc804\ud310': 'LON-STU',
    '\ud558\uacbd\uc740\ud589_\uc790\uc720\uc801\uae08_\uc644\uc804\ud310': 'SAV-FRE',
    '\ud558\uacbd\uc740\ud589_\uc815\uae30\uc801\uae08_\uc644\uc804\ud310': 'SAV-FIX',
    '\ud558\uacbd\uc740\ud589_\uc815\uae30\uc608\uae08_\uc644\uc804\ud310': 'DEP-TIM',
    '\ud558\uacbd\uc740\ud589_\uc790\uc720\uc785\ucd9c\uae08\ud1b5\uc7a5_\uc644\uc804\ud310': 'DEP-FLX',
    '\ud558\uacbd\uc740\ud589_MMDA_\uc644\uc804\ud310': 'DEP-MMD',
}


def is_decorative(line: str) -> bool:
    return bool(line) and all(ch in LINE_DECOR_CHARS for ch in line)


def chunk_text(text: str, max_len: int = MAX_LEN, overlap_chars: int = OVERLAP) -> List[str]:
    lines = text.split('\n')
    chunks: List[str] = []
    current: List[str] = []
    length = 0
    for line in lines:
        add_len = len(line)
        projected = length + (1 if current else 0) + add_len
        if current and projected > max_len:
            chunk = '\n'.join(current).strip()
            if chunk:
                chunks.append(chunk)
            overlap: List[str] = []
            if overlap_chars > 0 and current:
                total = 0
                for prev in reversed(current):
                    total += len(prev) + 1
                    overlap.append(prev)
                    if total >= overlap_chars:
                        break
                overlap = list(reversed(overlap))
            current = overlap + [line]
            length = sum(len(item) for item in current) + max(0, len(current) - 1)
        else:
            if current:
                length += 1 + add_len
            else:
                length += add_len
            current.append(line)
    if current:
        chunk = '\n'.join(current).strip()
        if chunk:
            chunks.append(chunk)
    return chunks


def extract_product_name(path: Path) -> str:
    text = path.read_text(encoding='utf-8')
    match = PRODUCT_PATTERN.search(text)
    return match.group(1).strip() if match else path.stem


def process_file(input_path: Path, output_path: Path, doc_id: str, product_name: str) -> dict:
    raw_lines = input_path.read_text(encoding='utf-8').splitlines()

    part_no: Optional[int] = None
    part_title: Optional[str] = None
    subsection_index = 0
    subsection_title: Optional[str] = None
    current_lines: List[str] = []
    results: List[dict] = []
    created_at = datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')
    auto_part_counter = 0

    def flush() -> None:
        nonlocal current_lines, results, subsection_title, part_no, subsection_index
        if not current_lines or part_no is None or subsection_title is None:
            current_lines = []
            return
        text_block = '\n'.join(current_lines).strip()
        if not text_block:
            current_lines = []
            return
        chunks = chunk_text(text_block)
        for idx, chunk in enumerate(chunks, start=1):
            chunk_identifier = f"{doc_id}-P{part_no:02d}-S{subsection_index:02d}-C{idx:03d}"
            payload = {
                'id': chunk_identifier,
                'document_id': doc_id,
                'product': product_name,
                'product_code': doc_id,
                'part_no': part_no,
                'part_title': part_title,
                'subsection_title': subsection_title,
                'breadcrumb': f"PART {part_no}. {part_title} > {subsection_title}",
                'chunk_index': idx,
                'text': chunk,
                'source': input_path.name,
                'created_at': created_at,
                'chunking': {
                    'strategy': 'structure+size',
                    'max_len': MAX_LEN,
                    'overlap': OVERLAP,
                },
            }
            results.append(payload)
        current_lines = []

    for raw in raw_lines:
        line_clean = raw.rstrip()
        stripped = line_clean.strip()
        if not stripped:
            if current_lines is not None:
                current_lines.append('')
            continue
        if is_decorative(stripped):
            continue

        part_match = PART_RE.match(stripped)
        if part_match:
            flush()
            part_no = int(part_match.group(1))
            part_title = part_match.group(2).strip()
            auto_part_counter = max(auto_part_counter, part_no)
            subsection_index = 0
            subsection_title = None
            current_lines = []
            continue

        section_match = SECTION_RE.match(stripped)
        if section_match:
            candidate_title = section_match.group(1).strip()
            if candidate_title.startswith('\uc81c'):
                pass
            else:
                flush()
                auto_part_counter += 1
                part_no = auto_part_counter
                part_title = candidate_title
                subsection_index = 0
                subsection_title = None
                current_lines = []
                continue

        sub_match = SUB_RE.match(stripped)
        if sub_match and part_no is not None:
            flush()
            subsection_index += 1
            subsection_title = sub_match.group(1).strip()
            header = f"PART {part_no}. {part_title} > {subsection_title}"
            current_lines = [header, stripped]
            continue

        article_match = ARTICLE_RE.match(stripped)
        if article_match and part_no is not None and ARTICLE_PART_KEYWORD in (part_title or ''):
            flush()
            subsection_index += 1
            descriptor = article_match.group(2) or article_match.group(3) or ''
            descriptor = descriptor.strip()
            title = article_match.group(1).replace('\u81f3', '\uc81c')
            subsection_title = f"{title} {descriptor}".strip()
            header = f"PART {part_no}. {part_title} > {subsection_title}"
            current_lines = [header, stripped]
            continue

        if part_no is not None:
            if subsection_title is None:
                subsection_index += 1
                subsection_title = part_title or f'PART {part_no}'
                header = f"PART {part_no}. {part_title} > {subsection_title}"
                current_lines = [header]
            current_lines.append(line_clean)

    flush()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open('w', encoding='utf-8') as f:
        for record in results:
            f.write(json.dumps(record, ensure_ascii=False))
            f.write('\n')

    parts_set = {(r['part_no'], r['part_title']) for r in results}
    subsections_set = {(r['part_no'], r['subsection_title']) for r in results}

    return {
        'input': str(input_path),
        'output': str(output_path),
        'product': product_name,
        'product_code': doc_id,
        'document_id': doc_id,
        'parts': len(parts_set),
        'subsections': len(subsections_set),
        'chunks': len(results),
    }


def main() -> None:
    base_output = Path('backend/data/rag_sources/products/hakyung')
    downloads = Path('C:/Users/JuYoung/Downloads')
    filenames = list(FILENAME_TO_CODE.keys())

    summaries = []
    for stem in filenames:
        path = downloads / f'{stem}.txt'
        if not path.exists():
            raise FileNotFoundError(f'Missing input file: {path}')
        code = FILENAME_TO_CODE[stem]
        product_name = extract_product_name(path)
        output_path = base_output / f'{code}.jsonl'
        summary = process_file(
            input_path=path,
            output_path=output_path,
            doc_id=code,
            product_name=product_name,
        )
        summaries.append(summary)
    print(json.dumps(summaries, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
