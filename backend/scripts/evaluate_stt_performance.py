"""
STT 모델 성능 평가 스크립트

평가 메트릭:
- WER (Word Error Rate): 단어 오류율
- CER (Character Error Rate): 문자 오류율
- 정확도 (Accuracy): 완전 일치율
- 처리 시간 (Latency): 응답 속도

사용법:
    python backend/scripts/evaluate_stt_performance.py --test-data test_data.json
"""

import sys
import os
import json
import time
from pathlib import Path
from typing import List, Dict, Tuple
import argparse
from datetime import datetime
import tempfile

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from openai import OpenAI
from app.config import settings


def calculate_wer(reference: str, hypothesis: str) -> float:
    """
    WER (Word Error Rate) 계산
    
    WER = (S + D + I) / N
    S = 치환(substitutions), D = 삭제(deletions), I = 삽입(insertions), N = 총 단어 수
    """
    ref_words = reference.split()
    hyp_words = hypothesis.split()
    
    # 편집 거리 계산 (Levenshtein distance)
    d = [[0] * (len(hyp_words) + 1) for _ in range(len(ref_words) + 1)]
    
    for i in range(len(ref_words) + 1):
        d[i][0] = i
    for j in range(len(hyp_words) + 1):
        d[0][j] = j
    
    for i in range(1, len(ref_words) + 1):
        for j in range(1, len(hyp_words) + 1):
            if ref_words[i-1] == hyp_words[j-1]:
                d[i][j] = d[i-1][j-1]
            else:
                substitution = d[i-1][j-1] + 1
                insertion = d[i][j-1] + 1
                deletion = d[i-1][j] + 1
                d[i][j] = min(substitution, insertion, deletion)
    
    return d[len(ref_words)][len(hyp_words)] / len(ref_words) if len(ref_words) > 0 else 0.0


def calculate_cer(reference: str, hypothesis: str) -> float:
    """
    CER (Character Error Rate) 계산
    
    CER = (S + D + I) / N
    S = 치환(substitutions), D = 삭제(deletions), I = 삽입(insertions), N = 총 문자 수
    """
    ref_chars = list(reference.replace(" ", ""))
    hyp_chars = list(hypothesis.replace(" ", ""))
    
    # 편집 거리 계산
    d = [[0] * (len(hyp_chars) + 1) for _ in range(len(ref_chars) + 1)]
    
    for i in range(len(ref_chars) + 1):
        d[i][0] = i
    for j in range(len(hyp_chars) + 1):
        d[0][j] = j
    
    for i in range(1, len(ref_chars) + 1):
        for j in range(1, len(hyp_chars) + 1):
            if ref_chars[i-1] == hyp_chars[j-1]:
                d[i][j] = d[i-1][j-1]
            else:
                substitution = d[i-1][j-1] + 1
                insertion = d[i][j-1] + 1
                deletion = d[i-1][j] + 1
                d[i][j] = min(substitution, insertion, deletion)
    
    return d[len(ref_chars)][len(hyp_chars)] / len(ref_chars) if len(ref_chars) > 0 else 0.0


def transcribe_audio(
    audio_path: str,
    model: str = "whisper-1",
    openai_client: OpenAI = None
) -> Tuple[str, float]:
    """
    음성 파일을 텍스트로 변환
    
    Args:
        audio_path: 음성 파일 경로
        model: STT 모델 ("whisper-1" 또는 "gpt-4o-transcribe")
        openai_client: OpenAI 클라이언트
        
    Returns:
        (transcribed_text, latency_seconds)
    """
    if not openai_client:
        raise ValueError("OpenAI 클라이언트가 필요합니다.")
    
    start_time = time.time()
    
    try:
        with open(audio_path, "rb") as audio_file:
            transcript = openai_client.audio.transcriptions.create(
                model=model,
                file=audio_file,
                language="ko"
            )
        
        latency = time.time() - start_time
        return transcript.text, latency
    
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        return "", 0.0


def evaluate_stt_model(
    test_data: List[Dict],
    model: str = "whisper-1",
    openai_client: OpenAI = None
) -> Dict:
    """
    STT 모델 성능 평가
    
    Args:
        test_data: [{"audio_path": "...", "ground_truth": "..."}, ...]
        model: STT 모델 이름
        openai_client: OpenAI 클라이언트
        
    Returns:
        평가 결과 딕셔너리
    """
    results = []
    total_wer = 0.0
    total_cer = 0.0
    total_latency = 0.0
    exact_matches = 0
    
    print(f"\n{'='*60}")
    print(f"📊 {model} 모델 평가 시작")
    print(f"{'='*60}\n")
    
    for i, item in enumerate(test_data):
        audio_path = item["audio_path"]
        ground_truth = item["ground_truth"]
        
        print(f"[{i+1}/{len(test_data)}] 처리 중: {Path(audio_path).name}")
        
        # STT 실행
        hypothesis, latency = transcribe_audio(audio_path, model, openai_client)
        
        # 메트릭 계산
        wer = calculate_wer(ground_truth, hypothesis)
        cer = calculate_cer(ground_truth, hypothesis)
        is_exact_match = ground_truth.strip() == hypothesis.strip()
        
        total_wer += wer
        total_cer += cer
        total_latency += latency
        if is_exact_match:
            exact_matches += 1
        
        result = {
            "audio_path": audio_path,
            "ground_truth": ground_truth,
            "hypothesis": hypothesis,
            "wer": round(wer, 4),
            "cer": round(cer, 4),
            "exact_match": is_exact_match,
            "latency": round(latency, 3)
        }
        results.append(result)
        
        print(f"  정답: {ground_truth}")
        print(f"  인식: {hypothesis}")
        print(f"  WER: {wer:.2%}, CER: {cer:.2%}, 처리시간: {latency:.2f}초")
        print()
    
    # 평균 계산
    n = len(test_data)
    avg_wer = total_wer / n if n > 0 else 0.0
    avg_cer = total_cer / n if n > 0 else 0.0
    avg_latency = total_latency / n if n > 0 else 0.0
    accuracy = exact_matches / n if n > 0 else 0.0
    
    summary = {
        "model": model,
        "total_samples": n,
        "avg_wer": round(avg_wer, 4),
        "avg_cer": round(avg_cer, 4),
        "accuracy": round(accuracy, 4),
        "exact_matches": exact_matches,
        "avg_latency": round(avg_latency, 3),
        "results": results
    }
    
    return summary


def print_summary(summary: Dict):
    """평가 결과 요약 출력"""
    print(f"\n{'='*60}")
    print(f"📈 평가 결과 요약 - {summary['model']}")
    print(f"{'='*60}")
    print(f"총 샘플 수:       {summary['total_samples']}개")
    print(f"평균 WER:         {summary['avg_wer']:.2%}")
    print(f"평균 CER:         {summary['avg_cer']:.2%}")
    print(f"완전 일치율:      {summary['accuracy']:.2%} ({summary['exact_matches']}/{summary['total_samples']})")
    print(f"평균 처리 시간:   {summary['avg_latency']:.2f}초")
    print(f"{'='*60}\n")


def compare_models(summaries: List[Dict]):
    """모델별 성능 비교"""
    print(f"\n{'='*60}")
    print(f"🔍 모델 성능 비교")
    print(f"{'='*60}\n")
    
    headers = ["모델", "WER", "CER", "정확도", "처리시간"]
    print(f"{headers[0]:<25} {headers[1]:<10} {headers[2]:<10} {headers[3]:<10} {headers[4]:<10}")
    print("-" * 70)
    
    for summary in summaries:
        model = summary['model']
        wer = f"{summary['avg_wer']:.2%}"
        cer = f"{summary['avg_cer']:.2%}"
        accuracy = f"{summary['accuracy']:.2%}"
        latency = f"{summary['avg_latency']:.2f}초"
        
        print(f"{model:<25} {wer:<10} {cer:<10} {accuracy:<10} {latency:<10}")
    
    print()


def save_results(summaries: List[Dict], output_path: str):
    """평가 결과를 JSON 파일로 저장"""
    output_data = {
        "evaluation_date": datetime.now().isoformat(),
        "summaries": summaries
    }
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 평가 결과 저장 완료: {output_path}")


def create_sample_test_data(output_path: str = "stt_test_data.json"):
    """
    샘플 테스트 데이터 생성 (템플릿)
    
    사용자는 이 파일을 수정하여 실제 음성 파일과 정답 텍스트를 입력해야 합니다.
    """
    sample_data = [
        {
            "audio_path": "path/to/sample1.webm",
            "ground_truth": "예금 상품에 대해 문의드립니다"
        },
        {
            "audio_path": "path/to/sample2.webm",
            "ground_truth": "대출 금리가 어떻게 되나요"
        },
        {
            "audio_path": "path/to/sample3.webm",
            "ground_truth": "카드 발급 절차를 알려주세요"
        }
    ]
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(sample_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 샘플 테스트 데이터 생성 완료: {output_path}")
    print(f"   파일을 수정하여 실제 음성 파일 경로와 정답 텍스트를 입력하세요.")


def main():
    parser = argparse.ArgumentParser(description="STT 모델 성능 평가")
    parser.add_argument(
        "--test-data",
        type=str,
        help="테스트 데이터 JSON 파일 경로"
    )
    parser.add_argument(
        "--create-sample",
        action="store_true",
        help="샘플 테스트 데이터 생성"
    )
    parser.add_argument(
        "--models",
        type=str,
        nargs="+",
        default=["whisper-1"],
        help="평가할 모델 목록 (whisper-1, gpt-4o-transcribe)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="stt_evaluation_results.json",
        help="결과 저장 파일명"
    )
    
    args = parser.parse_args()
    
    # 샘플 데이터 생성 모드
    if args.create_sample:
        create_sample_test_data()
        return
    
    # 테스트 데이터 로드
    if not args.test_data:
        print("❌ --test-data 옵션으로 테스트 데이터 파일을 지정하거나")
        print("   --create-sample 옵션으로 샘플 파일을 생성하세요.")
        print("\n사용 예시:")
        print("  python backend/scripts/evaluate_stt_performance.py --create-sample")
        print("  python backend/scripts/evaluate_stt_performance.py --test-data stt_test_data.json")
        return
    
    if not Path(args.test_data).exists():
        print(f"❌ 테스트 데이터 파일을 찾을 수 없습니다: {args.test_data}")
        return
    
    with open(args.test_data, "r", encoding="utf-8") as f:
        test_data = json.load(f)
    
    # OpenAI 클라이언트 초기화
    if not settings.OPENAI_API_KEY:
        print("❌ OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")
        return
    
    openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
    
    # 각 모델별로 평가 실행
    summaries = []
    for model in args.models:
        summary = evaluate_stt_model(test_data, model, openai_client)
        print_summary(summary)
        summaries.append(summary)
    
    # 모델 비교
    if len(summaries) > 1:
        compare_models(summaries)
    
    # 결과 저장
    save_results(summaries, args.output)


if __name__ == "__main__":
    main()

