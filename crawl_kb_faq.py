#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KB국민은행 FAQ 크롤링 및 하경은행 브랜드 치환 스크립트

이 스크립트는 KB국민은행 고객센터 FAQ를 크롤링하여
"하경은행" 브랜드로 치환한 후 JSONL 포맷으로 저장하고 ZIP으로 압축합니다.

필수 라이브러리 설치:
    pip install requests beautifulsoup4

실행 방법:
    python crawl_kb_faq.py
"""

import json
import logging
import random
import re
import time
import zipfile
from typing import Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('crawl_kb_faq.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 브랜드 치환 맵
# 주의: 긴 패턴부터 먼저 치환되도록 순서가 중요함
BRAND_MAP = {
    # 은행명 패턴 (긴 것부터)
    "KB국민은행": "하경은행",
    "KB 국민은행": "하경은행",
    "KB국민": "하경",
    "KB 국민": "하경",
    "국민은행": "하경은행",  # "KB" 없이 "국민은행"만 있는 경우
    
    # 제품/서비스명 (자연스러운 한글 브랜드 사용)
    "KB스타클럽": "하경스타클럽",
    "KB 스타클럽": "하경 스타클럽",
    "KB스타뱅킹": "하경 스타뱅킹",
    "KB 스타뱅킹": "하경 스타뱅킹",
    "KB국민카드": "하경카드",
    "KB 국민카드": "하경카드",
    "KB가맹점우대통장": "하경가맹점우대통장",
    "KB 가맹점우대통장": "하경 가맹점우대통장",
    "KB금융그룹": "하경금융그룹",
    "KB 금융그룹": "하경금융그룹",
    
    # 단독 "KB"는 마지막에 처리 (코드/기술 용어가 아닌 일반 문맥에서는 "하경"으로)
    # 코드나 번호 등 기술 용어는 "HK"로 치환되지 않도록 주의
    "KB": "하경",  # 일반 문맥에서 "KB" → "하경" (예: "KB에서 안내" → "하경에서 안내")
}

# FAQ 카테고리 정의
FAQ_CATEGORIES = [
    # 은행업무
    ("은행업무", "예금 상담", "https://obank.kbstar.com/quics?page=C019772"),
    ("은행업무", "신탁/펀드 상담", "https://obank.kbstar.com/quics?page=C019773"),
    ("은행업무", "대출 상담", "https://obank.kbstar.com/quics?page=C019774"),
    ("은행업무", "외환 상담", "https://obank.kbstar.com/quics?page=C019777"),
    ("은행업무", "myQ카드(금융IC카드)상담", "https://obank.kbstar.com/quics?page=C019780"),
    ("은행업무", "퇴직연금", "https://obank.kbstar.com/quics?page=C025066"),
    
    # 전자금융업무
    ("전자금융업무", "홈페이지", "https://obank.kbstar.com/quics?page=C019791"),
    ("전자금융업무", "인터넷뱅킹 서비스", "https://obank.kbstar.com/quics?page=C019782"),
    ("전자금융업무", "공동인증서", "https://obank.kbstar.com/quics?page=C019783"),
    ("전자금융업무", "KB 스타뱅킹 서비스", "https://obank.kbstar.com/quics?page=C019784"),
    ("전자금융업무", "폰뱅킹 서비스", "https://obank.kbstar.com/quics?page=C019785"),
    ("전자금융업무", "B2B전자결제", "https://obank.kbstar.com/quics?page=C019786"),
    ("전자금융업무", "로그인관련", "https://obank.kbstar.com/quics?page=C019787"),
    ("전자금융업무", "KB 에스크로 이체 서비스", "https://obank.kbstar.com/quics?page=C019788"),
    ("전자금융업무", "자동화기기/제휴업무", "https://obank.kbstar.com/quics?page=C019790"),
]

# User-Agent 설정 (서버 차단 방지)
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
}


def get_soup(url: str) -> Optional[BeautifulSoup]:
    """
    URL에서 HTML을 가져와 BeautifulSoup 객체로 반환합니다.
    
    Args:
        url: 크롤링할 URL
        
    Returns:
        BeautifulSoup 객체 또는 None (실패 시)
    """
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        
        # 인코딩 설정
        if response.encoding is None or response.encoding.lower() == 'iso-8859-1':
            response.encoding = response.apparent_encoding or 'utf-8'
        
        soup = BeautifulSoup(response.text, 'html.parser')
        return soup
        
    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP 요청 실패: {url} - {e}")
        return None
    except Exception as e:
        logger.error(f"파싱 실패: {url} - {e}")
        return None


def extract_list_links(list_url: str) -> list[Tuple[str, str]]:
    """
    FAQ 리스트 페이지에서 상세 페이지 링크들을 추출합니다.
    모든 페이지를 순회하여 전체 FAQ 링크를 수집합니다.
    
    Args:
        list_url: FAQ 리스트 페이지 URL
        
    Returns:
        (제목, 상세 페이지 URL) 튜플 리스트
    """
    all_links = []
    seen_urls = set()
    
    # 첫 번째 페이지부터 시작
    current_page = 1
    base_url = list_url.split('&viewPage=')[0].split('?viewPage=')[0]  # 기존 viewPage 제거
    
    while True:
        # 현재 페이지 URL 생성
        if '?' in base_url:
            page_url = f"{base_url}&viewPage={current_page}"
        else:
            page_url = f"{base_url}?viewPage={current_page}"
        
        logger.debug(f"페이지 {current_page} 크롤링: {page_url}")
        
        soup = get_soup(page_url)
        if not soup:
            logger.warning(f"페이지 {current_page} 로드 실패")
            break
        
        page_links = []
        
        # 여러 가지 패턴으로 링크 추출 시도
        # 패턴 1: bbsMode=view를 포함하는 링크
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            if 'bbsMode=view' in href:
                # 절대 URL로 변환
                absolute_url = urljoin(page_url, href)
                title = link.get_text(strip=True)
                
                # 제목이 비어있지 않고, 링크가 유효한 경우만 추가
                if title and absolute_url.startswith('http') and absolute_url not in seen_urls:
                    seen_urls.add(absolute_url)
                    page_links.append((title, absolute_url))
        
        # 패턴 2: 특정 클래스나 ID를 가진 영역 내의 링크
        list_containers = soup.find_all(['div', 'ul', 'table'], class_=re.compile(r'list|faq|board|content', re.I))
        for container in list_containers:
            for link in container.find_all('a', href=True):
                href = link.get('href', '')
                if 'bbsMode=view' in href and 'quics' in href:
                    absolute_url = urljoin(page_url, href)
                    title = link.get_text(strip=True)
                    
                    if title and absolute_url.startswith('http') and absolute_url not in seen_urls:
                        seen_urls.add(absolute_url)
                        page_links.append((title, absolute_url))
        
        # 현재 페이지에서 발견한 링크가 없으면 종료
        if not page_links:
            logger.info(f"페이지 {current_page}에서 FAQ 링크를 찾을 수 없음. 종료.")
            break
        
        all_links.extend(page_links)
        logger.info(f"페이지 {current_page}: {len(page_links)}개의 FAQ 링크 발견 (누적: {len(all_links)}개)")
        
        # 연속으로 중복된 페이지가 2번 나오면 종료 (같은 내용 반복 방지)
        # 이전 페이지 URL 집합과 현재 페이지 URL 집합 비교
        if current_page > 1:
            prev_page_urls = {url for _, url in all_links[:-len(page_links)]}
            current_page_urls = {url for _, url in page_links}
            
            # 현재 페이지의 모든 링크가 이전 페이지에 이미 있었다면 종료
            if current_page_urls.issubset(prev_page_urls):
                logger.info(f"페이지 {current_page}의 내용이 이전 페이지와 중복됨. 종료.")
                break
        
        current_page += 1
        
        # 안전장치: 최대 100페이지까지만
        if current_page > 100:
            logger.info(f"최대 페이지 수(100)에 도달. 종료.")
            break
    
    logger.info(f"리스트 페이지에서 총 {len(all_links)}개의 FAQ 링크 발견: {list_url}")
    return all_links


def extract_qna(detail_url: str) -> Tuple[Optional[str], Optional[str]]:
    """
    FAQ 상세 페이지에서 질문과 답변을 추출합니다.
    
    Args:
        detail_url: FAQ 상세 페이지 URL
        
    Returns:
        (질문, 답변) 튜플. 추출 실패 시 (None, None)
    """
    soup = get_soup(detail_url)
    if not soup:
        return None, None
    
    question = None
    answer = None
    
    # 텍스트 마커 기반 추출 (KB국민은행 FAQ는 Q(질문), A(답변) 마커 사용)
    full_text = soup.get_text()
    
    # Q(질문)과 A(답변) 마커 찾기
    q_marker_pattern = r'Q\s*\(질문\)'
    a_marker_pattern = r'A\s*\(답변\)'
    
    # Q(질문) 마커 찾기
    q_match = re.search(q_marker_pattern, full_text, re.IGNORECASE)
    if q_match:
        q_marker_end = q_match.end()
        
        # A(답변) 마커 찾기 (Q 마커 이후)
        a_match = re.search(a_marker_pattern, full_text[q_marker_end:], re.IGNORECASE)
        if a_match:
            a_marker_start = q_marker_end + a_match.start()
            a_marker_end = q_marker_end + a_match.end()
            
            # 질문 추출: Q(질문) 마커 바로 뒤부터 A(답변) 마커 전까지
            question_text = full_text[q_marker_end:a_marker_start].strip()
            question = question_text
            
            # 답변 추출: A(답변) 마커 바로 뒤부터 답변 끝 마커 전까지
            answer_text = full_text[a_marker_end:]
            
            # 답변 종료 마커 찾기 ("이전글", "다음글", "목록" 등)
            # 우선순위: 더 구체적인 패턴부터 시도
            end_patterns = [
                r'이전글주택청약예금',  # "이전글" + 다음 FAQ 제목
                r'이전글\S+',  # "이전글" + 제목 (공백 전까지)
                r'다음글\S+',  # "다음글" + 제목 (공백 전까지)
                r'이전글',  # "이전글" 단독
                r'다음글',  # "다음글" 단독
                r'목록\s*$',  # "목록"으로 끝나는 경우
            ]
            
            answer_end_pos = len(answer_text)
            for pattern in end_patterns:
                match = re.search(pattern, answer_text, re.MULTILINE)
                if match:
                    answer_end_pos = match.start()
                    break
            
            # 답변 추출
            answer = answer_text[:answer_end_pos].strip()
            
            # 답변 앞부분에 불필요한 단어가 있는 경우 제거
            # 예: "확인" 같은 단어
            confirm_pattern = r'^확인\s*'
            answer = re.sub(confirm_pattern, '', answer, flags=re.MULTILINE).strip()
    
    # 질문/답변 정리
    if question:
        # 줄바꿈은 유지하면서 연속된 공백만 하나로 통합
        question = re.sub(r'[ \t]+', ' ', question).strip()
    
    if answer:
        # 줄바꿈은 유지하면서 연속된 공백만 하나로 통합
        # 불릿 포인트나 목록 형식은 보존
        lines = answer.split('\n')
        cleaned_lines = []
        for line in lines:
            cleaned_line = re.sub(r'[ \t]+', ' ', line.strip())
            if cleaned_line:
                cleaned_lines.append(cleaned_line)
        
        # 답변을 다시 합치되, 과도한 줄바꿈 제거
        answer = '\n'.join(cleaned_lines)
        answer = re.sub(r'\n{3,}', '\n\n', answer)  # 3개 이상의 연속 줄바꿈을 2개로
        answer = answer.strip()
    
    # 너무 짧거나 의미 없는 내용 제거
    if question and len(question) < 5:
        question = None
    if answer and len(answer) < 10:
        answer = None
    
    if question and answer:
        logger.debug(f"Q/A 추출 성공: {detail_url[:50]}...")
    else:
        logger.warning(f"Q/A 추출 실패 또는 불완전: {detail_url}")
    
    return question, answer


def replace_brand(text: str) -> str:
    """
    텍스트에서 KB/국민은행 브랜드를 HK/하경은행 브랜드로 치환합니다.
    
    Args:
        text: 원본 텍스트
        
    Returns:
        브랜드 치환된 텍스트
    """
    if not text:
        return text
    
    # 긴 패턴부터 치환 (먼저 처리하여 "KB국민은행"을 "HK하경은행"으로 치환)
    # 그 다음 단순 "KB"를 "HK"로 치환
    for old, new in BRAND_MAP.items():
        text = text.replace(old, new)
    
    return text


def sanitize_category_name(category: str) -> str:
    """
    카테고리 이름을 ID 생성에 사용할 수 있도록 정리합니다.
    
    Args:
        category: 원본 카테고리 이름
        
    Returns:
        정리된 카테고리 이름 (공백/슬래시 제거 또는 언더스코어로 치환)
    """
    # 공백을 언더스코어로
    category = category.replace(' ', '_')
    # 슬래시를 언더스코어로
    category = category.replace('/', '_')
    # 기타 특수문자 제거
    category = re.sub(r'[^\w_가-힣]', '', category)
    return category


def crawl_all() -> Tuple[list, list]:
    """
    모든 FAQ 카테고리를 크롤링합니다.
    
    Returns:
        (은행업무 FAQ 리스트, 전자금융업무 FAQ 리스트) 튜플
    """
    bank_faqs = []
    efin_faqs = []
    
    # 서브카테고리별 카운터 (ID 생성용)
    sub_category_counters = {}
    
    total_categories = len(FAQ_CATEGORIES)
    
    for idx, (big_category, sub_category, list_url) in enumerate(FAQ_CATEGORIES, 1):
        logger.info(f"[{idx}/{total_categories}] 크롤링 시작: {big_category} > {sub_category}")
        
        # 리스트 페이지에서 상세 링크 추출
        links = extract_list_links(list_url)
        
        if not links:
            logger.warning(f"링크를 찾을 수 없습니다: {list_url}")
            continue
        
        # ID 생성용 키
        sanitized_big = sanitize_category_name(big_category)
        sanitized_sub = sanitize_category_name(sub_category)
        category_key = f"{sanitized_big}_{sanitized_sub}"
        
        # 해당 서브카테고리의 카운터 초기화 (없는 경우)
        if category_key not in sub_category_counters:
            sub_category_counters[category_key] = 0
        
        # 각 상세 페이지 크롤링
        for link_idx, (title, detail_url) in enumerate(links, 1):
            logger.info(f"  [{link_idx}/{len(links)}] 처리 중: {title[:50]}...")
            
            # Q/A 추출
            question, answer = extract_qna(detail_url)
            
            # 질문이 없으면 리스트 제목 사용
            if not question:
                question = title
            
            # 질문 또는 답변이 비어있으면 스킵
            if not question or not answer:
                logger.warning(f"    Q/A 불완전 - 스킵: {detail_url}")
                continue
            
            # 브랜드 치환
            question = replace_brand(question)
            answer = replace_brand(answer)
            
            # ID 생성 (서브카테고리별로 순차 번호 부여)
            sub_category_counters[category_key] += 1
            item_num = sub_category_counters[category_key]
            faq_id = f"{sanitized_big}_{sanitized_sub}_{item_num:03d}"
            
            # FAQ 항목 생성
            faq_item = {
                "id": faq_id,
                "big_category": big_category,
                "sub_category": sub_category,
                "question": question,
                "answer": answer,
                "source_url": detail_url,
            }
            
            # big_category에 따라 적절한 리스트에 추가
            if big_category == "은행업무":
                bank_faqs.append(faq_item)
            else:
                efin_faqs.append(faq_item)
            
            # 서버 부하 방지를 위한 지연
            sleep_time = random.uniform(0.3, 0.7)
            time.sleep(sleep_time)
        
        logger.info(f"  완료: {big_category} > {sub_category} - {len(links)}개 항목 처리")
    
    logger.info(f"크롤링 완료 - 은행업무: {len(bank_faqs)}개, 전자금융업무: {len(efin_faqs)}개")
    return bank_faqs, efin_faqs


def save_jsonl(filename: str, data: list) -> None:
    """
    데이터를 JSONL 파일로 저장합니다.
    
    Args:
        filename: 저장할 파일명
        data: 저장할 데이터 리스트
    """
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            for item in data:
                json_line = json.dumps(item, ensure_ascii=False)
                f.write(json_line + '\n')
        
        logger.info(f"JSONL 파일 저장 완료: {filename} ({len(data)}개 항목)")
    except Exception as e:
        logger.error(f"JSONL 파일 저장 실패: {filename} - {e}")
        raise


def create_zip(jsonl_files: list, zip_filename: str) -> None:
    """
    JSONL 파일들을 ZIP으로 압축합니다.
    
    Args:
        jsonl_files: 압축할 JSONL 파일 리스트
        zip_filename: 생성할 ZIP 파일명
    """
    try:
        with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for jsonl_file in jsonl_files:
                zipf.write(jsonl_file)
        
        logger.info(f"ZIP 파일 생성 완료: {zip_filename}")
    except Exception as e:
        logger.error(f"ZIP 파일 생성 실패: {zip_filename} - {e}")
        raise


def main():
    """메인 실행 함수"""
    logger.info("=" * 60)
    logger.info("KB국민은행 FAQ 크롤링 시작")
    logger.info("=" * 60)
    
    try:
        # 크롤링 실행
        bank_faqs, efin_faqs = crawl_all()
        
        if not bank_faqs and not efin_faqs:
            logger.error("크롤링된 FAQ가 없습니다. 종료합니다.")
            return
        
        # JSONL 파일 저장
        bank_jsonl = "hagyung_faq_bank.jsonl"
        efin_jsonl = "hagyung_faq_efin.jsonl"
        
        if bank_faqs:
            save_jsonl(bank_jsonl, bank_faqs)
        else:
            logger.warning("은행업무 FAQ가 없어 JSONL 파일을 생성하지 않습니다.")
        
        if efin_faqs:
            save_jsonl(efin_jsonl, efin_faqs)
        else:
            logger.warning("전자금융업무 FAQ가 없어 JSONL 파일을 생성하지 않습니다.")
        
        # ZIP 압축
        jsonl_files = [f for f in [bank_jsonl, efin_jsonl] if f]
        if jsonl_files:
            create_zip(jsonl_files, "hagyung_faq_jsonl.zip")
        
        logger.info("=" * 60)
        logger.info("모든 작업이 완료되었습니다!")
        logger.info(f"- 은행업무 FAQ: {len(bank_faqs)}개")
        logger.info(f"- 전자금융업무 FAQ: {len(efin_faqs)}개")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"실행 중 오류 발생: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()

