import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from sqlmodel import Session

from app.database import engine
from app.services.rag_simulation_service import RAGSimulationService

scenario_order = [
    ("deposit", "수신"),
    ("loan", "여신"),
    ("card", "카드"),
]

summary = []


def serialize_knowledge_result(result):
    if not result:
        return None
    serialized = {}
    for key, value in result.items():
        if key == "verifications" and value:
            serialized["verifications"] = [
                asdict(v) if hasattr(v, "__dict__") else v for v in value
            ]
        else:
            serialized[key] = value
    return serialized

with Session(engine) as session:
    service = RAGSimulationService(session)
    user_id = 1
    for scenario_code, label in scenario_order:
        print("\n" + "="*80)
        print(f"▶️  {label} ({scenario_code}) 시나리오 실행")
        session_data = service.start_test_simulation(user_id=user_id, scenario_type=scenario_code)
        session_data["is_test_mode"] = True
        session_data.setdefault("conversation_history", [])
        session_data.setdefault("stt_evaluations", [])
        session_data.setdefault("rag_evaluations", [])
        turns = session_data.get("test_scenario", {}).get("turns", [])
        if not turns:
            print("⚠️  시나리오에 턴 정보가 없습니다.")
            continue
        next_text = turns[0].get("expected_text", "")
        responses = []
        step = 0
        while next_text:
            step += 1
            print(f"  - Step {step}: '{next_text[:60]}...'")
            resp = service.process_voice_interaction(session_data, b"", next_text)
            responses.append(resp)
            session_data["conversation_history"] = resp.get("conversation_history", session_data.get("conversation_history", []))
            session_data["stt_evaluations"] = resp.get("stt_evaluations", session_data.get("stt_evaluations", []))
            if resp.get("rag_evaluations") is not None:
                session_data["rag_evaluations"] = resp.get("rag_evaluations", [])
            if resp.get("rag_summary") is not None:
                session_data["rag_summary"] = resp.get("rag_summary")
            if resp.get("end_signal"):
                print("  ✔️  종료 신호 수신")
                break
            next_text = resp.get("next_turn_expected_text")
            if not next_text:
                print("  ⚠️  다음 턴 텍스트가 없어 루프 종료")
                break
        if not responses:
            print("⚠️  응답이 생성되지 않아 스킵합니다.")
            continue
        final_resp = responses[-1]
        conversation_history = final_resp.get("conversation_history", session_data.get("conversation_history", []))
        rag_evals = session_data.get("rag_evaluations")
        rag_summary = session_data.get("rag_summary")
        knowledge_result = None
        if scenario_code != "fx" and service.product_knowledge_service and conversation_history:
            try:
                knowledge_result = service.product_knowledge_service.batch_verify_conversation(
                    conversation_history,
                    use_llm=True,
                    use_llm_extraction=True
                )
            except Exception as e:
                print(f"  ⚠️  지식 검증 중 오류: {e}")
        summary.append({
            "scenario": scenario_code,
            "label": label,
            "steps": step,
            "history_turns": len(conversation_history),
            "rag_eval_count": len(rag_evals) if rag_evals else 0,
            "rag_evaluations": rag_evals,
            "rag_summary": rag_summary,
            "knowledge_result": serialize_knowledge_result(knowledge_result)
        })

print("\n" + "="*80)
print("시나리오 별 요약 데이터:")
for item in summary:
    print(f"\n[{item['label']}]")
    print(f" - Steps: {item['steps']}")
    print(f" - RAG 평가 수: {item['rag_eval_count']}")
    if item['knowledge_result']:
        kr = item['knowledge_result']
        print(f" - 지식 정확도: {kr.get('accuracy_rate'):.1%} ({kr.get('accurate_claims')}/{kr.get('total_claims')})")
    else:
        print(" - 지식 검증: 해당 없음")

output_payload = {
    "generated_at": datetime.utcnow().isoformat() + "Z",
    "scenarios": summary,
}

output_path = Path(__file__).parent / "test_mode_batch_results.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(output_payload, f, ensure_ascii=False, indent=2)

print(f"\nJSON 데이터 저장 완료: {output_path}")
