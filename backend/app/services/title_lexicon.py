"""
제목 사전 및 별칭 자동 생성 시스템
타이틀 게이팅을 위한 핵심 모듈
"""

import re
from collections import defaultdict
from typing import Dict, List, Set, Tuple

# 실제 문서 제목들 (하드코딩)
TITLES = [
    "위임장", "신용보증서", "이의신청서", "대위변제증서", "대출만기안내", "민원접수양식", "제증명의뢰서",
    "거치식예금약관", "고객권리안내문", "수신거래상황표", "신용보증약정서", "여신거래상황표",
    "이의제기신청서", "이자계산내역서", "자료열람요구서", "잔존채무확인서", "적립식예금약관",
    "피해구제신청서", "대출만기경과안내", "예금거래기본약관", "전세지킴보증약관",
    "채권자계좌신고서", "가계대출상품설명서", "기업대출상품설명서", "보증채무이행청구서",
    "비과세종합저축특약", "신용보증부실통지서", "전자금융거래기본약관",
    "은행여신거래기본약관(함께대출용)", "은행여신거래기본약관(가계용)", "은행여신거래기본약관(기업용)",
    "전자금융거래기본약관(기업용)", "입출금이자유로운예금_약관", "가계대출상품설명서(함께대출용)",
    "증권계좌개설서비스+설명서", "계좌통합관리서비스+이용약관", "증권계좌개설서비스_이용약관",
    "전월세보증금대출+상품설명서",
    "위임장(개인여신)", "위임장(금결원+대출이동시스템)", "위임장+(전월세대출+심사용)",
    "위임장+(상속)",
    "CD(양도성예금증서)상품설명서", "MMF(머니마켓펀드)상품설명서", "RP(환매약정)상품설명서",
    "주택담보대출상품설명서", "전세보증금대출상품설명서", "신용대출상품설명서",
    "개인신용평가기준", "기업신용평가기준", "대출심사기준", "여신정책기준",
    "금융소비자보호법", "전자금융거래법", "은행법", "신용정보법",
    "개인정보보호법", "금융실명거래법", "자금세탁방지법", "외국환거래법"
]

# 문서 타입별 키워드
K_KEYWORDS = {
    "terms": ["약관", "기본약관", "특약"],
    "form": ["양식", "서식", "신청서", "확인서", "동의서", "위임장", "증서", "약정서", "청구서"],
    "product_brochure": ["상품설명서", "상품안내"],
    "regulation": ["법", "시행령", "타법개정", "일부개정"],
    "manual": ["안내", "서비스 설명서", "이용약관", "공지", "안내문"],
}

def norm(s: str) -> str:
    """제목 정규화"""
    s = s.lower()
    s = s.replace("_", " ").replace("+", " ").replace("·", " ")
    s = re.sub(r"[()\[\]]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def guess_doc_type(title: str) -> str:
    """제목으로부터 문서 타입 추정"""
    for t, keys in K_KEYWORDS.items():
        if any(k in title for k in keys):
            return t
    return "mixed"

def build_title_lexicon(titles: List[str]) -> Dict:
    """제목 사전 구축"""
    by_norm = {}
    aliases = defaultdict(set)
    by_token = defaultdict(set)

    for t in titles:
        n = norm(t)
        by_norm[n] = t
        
        # 기본 별칭 생성 규칙
        base_tokens = [tok for tok in re.split(r"\s", n) if tok and tok not in {"의", "및", "에", "용", "용)"}]
        
        # 대표 키워드 단일형 별칭 생성
        for kw in sum(K_KEYWORDS.values(), []):
            if kw in n:
                aliases[kw].add(t)
        
        # 괄호 앞부분/키워드 조합
        head = n.split()[0] if base_tokens else n
        for tok in base_tokens:
            by_token[tok].add(t)
        
        # 문서유형 태깅
        dt = guess_doc_type(n)
        by_token[dt].add(t)

        # 특수: "위임장(개인여신)" → "위임장", "위임장 개인여신"
        bare = re.split(r"\s", re.sub(r"\(.*?\)", "", n))[0]
        if bare:
            aliases[bare].add(t)

    return {
        "by_norm": by_norm, 
        "aliases": dict(aliases), 
        "by_token": dict(by_token)
    }

def title_candidates(query: str, lex: Dict) -> List[str]:
    """쿼리로부터 제목 후보 추출"""
    qn = norm(query)
    titles = list(lex["by_norm"].values())
    cands = set()

    # 1) exact/aliases/키워드 매칭
    if qn in lex["by_norm"]:
        cands.add(lex["by_norm"][qn])
    if qn in lex["aliases"]:
        cands |= lex["aliases"][qn]
    for tok in qn.split():
        if tok in lex["aliases"]:
            cands |= lex["aliases"][tok]
        if tok in lex["by_token"]:
            cands |= lex["by_token"][tok]

    # 2) fuzzy(부분 일치 허용) - 간단한 구현
    for title in titles:
        if qn in title or any(tok in title for tok in qn.split()):
            cands.add(title)

    # 너무 많으면 상한
    return list(cands)[:20]

# 전역 사전 인스턴스
LEXICON = build_title_lexicon(TITLES)

# 의도별 doc_type 우선순위
DOC_TYPE_PRIORITIES = {
    "form": ["form", "manual", "faq"],
    "terms": ["terms", "regulation"],
    "product": ["product_brochure", "faq"],
    "regulation": ["regulation", "terms"],
    "manual": ["manual", "faq", "form"],
    "general": []
}
