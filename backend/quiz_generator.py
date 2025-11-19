import os
import re
import pandas as pd
import json
import time 
import tempfile 
from typing import List, Dict, Optional, Tuple, Any

# RAG 및 LLM 관련 라이브러리 임포트
from openai import OpenAI
from openai.types.chat import ChatCompletion
from langchain_openai import OpenAIEmbeddings 
from langchain_community.vectorstores import Chroma 
from langchain_text_splitters import RecursiveCharacterTextSplitter 
from pypdf import PdfReader
import numpy as np 

# --- 1. Configuration Constants ---
class Config:
    SOURCE_ROOT_DIR = "data/rag_sources"
    OUTPUT_CSV_FILE = "dbquiz_eval.csv" 
    
    # Model Settings
    AI_MODEL_NAME = "gpt-4o" 
    EVAL_MODEL_NAME = "gpt-3.5-turbo" 
    
    # RAG Settings 
    CHUNK_SIZE = 500 
    CHUNK_OVERLAP = 200
    EMBEDDING_CHUNK_SIZE = 500 
    K_FINAL_CONTEXT = 3 
    
    # Control Flow
    API_RETRY_DELAY = 1 
    DUPLICATION_THRESHOLD = 0.92 
    MAX_GENERATION_ATTEMPTS = 5 
    MAX_DUPLICATE_ATTEMPTS = 3 

    # Quiz Structure
    QUIZ_DISTRIBUTION: Dict[str, int] = {
        '하': 1, 
        '중': 1, 
        '상': 1  
    }
    TOTAL_QUESTIONS_PER_SOURCE: int = sum(QUIZ_DISTRIBUTION.values())

    DIFFICULTY_MAPPING = {
        '상': "은행 및 금융 전문가 수준(경력 5년 이상). 심화 개념, 예외, 복합적, 실무적 이해가 필요한 문제.",
        '중': "경제학 전공 대학 졸업 수준(경력 0~1년). 핵심 개념 및 원리를 묻는 문제.",
        '하': "고등학생 수준. 가장 기본적인 용어 정의를 묻는 문제."
    }

# --- 2. Main Class: QuizGenerator ---

class QuizGenerator:
    def __init__(self):
        self.api_key = os.environ.get("OPENAI_API_KEY") 
        self.client: Optional[OpenAI] = None
        self.embeddings: Optional[OpenAIEmbeddings] = None
        self.vectorstore: Optional[Chroma] = None
        self.all_final_quizzes: List[Dict] = []
        self.all_cumulative_vectors: List[np.ndarray] = []
        
        self._initialize_clients()

    # -----------------------------------------------------
    # Initialization & Client Setup
    # -----------------------------------------------------
    def _initialize_clients(self):
        if not self.api_key:
            print("🛑 환경 변수 'OPENAI_API_KEY'가 설정되지 않았습니다. 퀴즈를 생성할 수 없습니다.")
            return

        try:
            self.client = OpenAI(api_key=self.api_key)
            self.embeddings = OpenAIEmbeddings(
                openai_api_key=self.api_key,
                chunk_size=Config.EMBEDDING_CHUNK_SIZE 
            ) 
            
            temp_db_dir = os.path.join(tempfile.gettempdir(), "rag_quiz_chroma")
            self.vectorstore = Chroma(persist_directory=temp_db_dir, embedding_function=self.embeddings)
            
            print("✅ OpenAI 클라이언트 및 RAG 준비 완료.")
            
        except Exception as e:
            print(f"🛑 Error initializing OpenAI client or RAG components: {e}")
            self.client = None

    # -----------------------------------------------------
    # Utility Methods (Duplication Check)
    # -----------------------------------------------------
    @staticmethod
    def _get_text_for_embedding(quiz: Dict) -> str:
        """퀴즈 객체에서 임베딩을 위한 텍스트를 추출"""
        return f"Q: {quiz.get('question', '')} A: {quiz.get('answer', '')} Comment: {quiz.get('comment', '')}"

    def _get_text_embedding(self, text: str) -> Optional[np.ndarray]:
        """텍스트 임베딩을 생성"""
        if self.embeddings is None:
            return None
        try:
            vector = self.embeddings.embed_query(text)
            return np.array(vector)
        except Exception:
            return None

    @staticmethod
    def _get_cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
        """코사인 유사도 계산"""
        dot_product = np.dot(vec_a, vec_b)
        norm_a = np.linalg.norm(vec_a)
        norm_b = np.linalg.norm(vec_b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot_product / (norm_a * norm_b)

    # -----------------------------------------------------
    # RAG Indexing
    # -----------------------------------------------------
    def _clean_text(self, text: str) -> str:
        """URL, 이메일, 전화번호 등의 패턴을 텍스트에서 제거합니다."""
        
        # 1. URL 패턴 제거 (http/https, www. 포함, 또는 .com/.net/.org 등으로 끝나는 패턴)
        url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        text = re.sub(url_pattern, ' [URL_REMOVED] ', text) # 제거 대신 마스킹(Masking)도 고려

        # 2. 'www.'로 시작하거나 일반적인 도메인 형태 제거
        domain_pattern = r'\b(?:www\.|[a-zA-Z0-9-]+\.(?:com|net|org|co\.kr|or\.kr|kr|go\.kr|io))\b'
        text = re.sub(domain_pattern, ' [DOMAIN_REMOVED] ', text)

        # 3. 이메일 주소 제거
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        text = re.sub(email_pattern, ' [EMAIL_REMOVED] ', text)
        
        # 4. 전화번호 패턴 제거 (예: 000-0000-0000)
        phone_pattern = r'(\d{2,4}-\d{3,4}-\d{4}|\(\d{2,4}\)\s*\d{3,4}-\d{4})'
        text = re.sub(phone_pattern, ' [PHONE_REMOVED] ', text)

        # 제거 후 발생하는 과도한 공백을 하나로 합침
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def _extract_all_source_data(self) -> List[Dict[str, str]]:
        """PDF/JSONL 파일에서 텍스트와 메타데이터 추출"""
        all_source_data: List[Dict[str, str]] = []
        
        for root, _, files in os.walk(Config.SOURCE_ROOT_DIR):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext not in {".pdf", ".jsonl"}:
                    continue

                file_path = os.path.join(root, file)
                file_name = file 
                
                relative_path = os.path.relpath(root, Config.SOURCE_ROOT_DIR)
                category = relative_path.split(os.path.sep)[0]
                
                if not category or category == '.': 
                    continue
                
                text_content = ""

                if ext == ".pdf":
                    try:
                        reader = PdfReader(file_path)
                        text_content = "".join(page.extract_text() + "\n" for page in reader.pages if page.extract_text())
                    except Exception as e:
                        print(f"  -> ⚠️ PDF 읽기 오류 ({file_name}): {e}")
                        continue
                else:
                    text_chunks: List[str] = []
                    try:
                        with open(file_path, "r", encoding="utf-8") as jsonl_file:
                            for line_no, line in enumerate(jsonl_file, start=1):
                                trimmed = line.strip()
                                if not trimmed:
                                    continue
                                try:
                                    record = json.loads(trimmed)
                                except json.JSONDecodeError as e:
                                    print(f"  -> ⚠️ JSONL 파싱 오류 ({file_name}:{line_no}): {e}")
                                    continue
                                
                                if not isinstance(record, dict):
                                    continue
                                
                                text_candidate = ""
                                for key in ("text", "content", "body", "paragraph", "raw_text"):
                                    value = record.get(key)
                                    if isinstance(value, str) and value.strip():
                                        text_candidate = value.strip()
                                        break
                                if text_candidate:
                                    text_chunks.append(text_candidate)
                    except Exception as e:
                        print(f"  -> ⚠️ JSONL 읽기 오류 ({file_name}): {e}")
                        continue

                    text_content = "\n".join(text_chunks)

                if text_content.strip():
                    cleaned_text = self._clean_text(
                        text_content.encode('ascii', 'ignore').decode('ascii').strip()
                    )
                    
                    all_source_data.append({
                        "category": category,
                        "file_name": file_name,
                        "text": cleaned_text 
                    })
                        
        return all_source_data

    def create_rag_index(self, all_source_data: List[Dict[str, str]]) -> bool:
        """자료 텍스트를 청크로 분할하고 Chroma DB에 인덱싱"""
        if self.vectorstore is None:
            return False
            
        print("\n1. 📚 자료 텍스트 청크 분할 및 RAG 인덱스 생성 중...")
        
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=Config.CHUNK_SIZE,
            chunk_overlap=Config.CHUNK_OVERLAP,
            separators=["\n\n", "\n", " ", ""]
        )

        documents = []
        for source_info in all_source_data:
            category = source_info["category"]
            file_name = source_info["file_name"]
            combined_text = source_info["text"]
            
            if combined_text.strip():
                chunks = text_splitter.split_text(combined_text)
                
                for i, chunk in enumerate(chunks):
                    doc = {
                        "page_content": chunk,
                        "metadata": {"category": category, "file_name": file_name, "chunk_id": f"{category}_{file_name}_{i}"}
                    }
                    documents.append(doc)

        if not documents:
            return False

        texts = [doc["page_content"].encode('ascii', 'ignore').decode('ascii', 'ignore').strip() for doc in documents]
        metadatas = [doc["metadata"] for doc in documents]

        MAX_CHROMA_BATCH = 5000 
        try:
            total_documents = len(texts)
            print(f"2. 💾 총 {total_documents}개 청크를 {MAX_CHROMA_BATCH}개 단위로 배치 저장 중...")
            
            for i in range(0, total_documents, MAX_CHROMA_BATCH):
                self.vectorstore.add_texts(texts=texts[i:i + MAX_CHROMA_BATCH], metadatas=metadatas[i:i + MAX_CHROMA_BATCH])
            
            print(f"✅ 총 {total_documents}개 청크 벡터 DB 저장 완료.")
            return True
        
        except Exception as e:
            print(f"🛑 벡터 DB 저장 중 오류 발생: {e}")
            return False

    # -----------------------------------------------------
    # Quiz Generation Core
    # -----------------------------------------------------
    def _generate_quiz_with_retry(
        self, 
        quiz_system_prompt: str, 
        user_prompt: str, 
        category: str, 
        difficulty: str, 
        file_name: str, 
        dup_attempt: int
    ) -> Optional[Dict]:
        """퀴즈 생성 로직을 캡슐화하고 재시도 및 JSON 파싱 오류를 처리"""
        
        for attempt in range(Config.MAX_GENERATION_ATTEMPTS): 
            try:
                response: ChatCompletion = self.client.chat.completions.create(
                    model=Config.AI_MODEL_NAME,
                    response_format={"type": "json_object"}, 
                    messages=[
                        {"role": "system", "content": quiz_system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    # 중복 방지를 위해 temperature를 약간 높임
                    temperature=0.5 + (dup_attempt * 0.1) 
                )
                
                json_string = response.choices[0].message.content
                if not json_string:
                    raise ValueError("LLM returned empty content.")
                    
                raw_quiz = json.loads(json_string.strip()) 
                
                # LLM이 간혹 JSON 리스트로 반환하는 경우 대비
                if isinstance(raw_quiz, list) and raw_quiz:
                    raw_quiz = raw_quiz[0]
                
                # 필수 필드 확인
                if isinstance(raw_quiz, dict) and raw_quiz.get('question') and raw_quiz.get('answer'):
                    raw_quiz['category'] = category
                    raw_quiz['difficulty'] = difficulty
                    raw_quiz['source_files'] = file_name 
                    return raw_quiz
                else:
                    raise ValueError("Invalid JSON structure or missing key fields.")
                    
            except Exception as e:
                print(f"    -> ⚠️ 퀴즈 생성 실패/오류 (시도 {attempt+1}): {type(e).__name__}: {e}. 재시도...")
                time.sleep(Config.API_RETRY_DELAY)
        
        return None

    def _evaluate_quiz_with_retry(
        self, 
        raw_quiz: Dict, 
        eval_system_prompt: str, 
        source_full_text: str
    ) -> Optional[Dict]:
        """퀴즈 평가 로직을 캡슐화하고 재시도 및 JSON 파싱 오류를 처리"""
        
        eval_user_prompt = f"""
        [평가할 퀴즈]:
        ---
        {json.dumps(raw_quiz, ensure_ascii=False, indent=2)}
        ---
        
        [참고 자료 (LLM Judge가 전체 내용을 확인하도록 원문 전체 텍스트 제공)]:
        ---
        {source_full_text[:4000]}... (Truncated for brevity, full text is available to the model)
        ---
        
        위 퀴즈를 평가하고 평가 점수('evaluation_score', 1~10점)와 상세 평가('evaluation_comment')를 포함하여 단일 JSON 객체로 반환하세요.
        **반드시 시스템 프롬프트에 명시된 3단계 평가 기준을 명확히 적용하여 평가하세요.**
        """

        for attempt in range(3): 
            try:
                response: ChatCompletion = self.client.chat.completions.create(
                    model=Config.EVAL_MODEL_NAME, 
                    response_format={"type": "json_object"}, 
                    messages=[
                        {"role": "system", "content": eval_system_prompt},
                        {"role": "user", "content": eval_user_prompt}
                    ],
                    temperature=0.0 
                )
                
                eval_json_string = response.choices[0].message.content
                if not eval_json_string:
                    raise ValueError("LLM Judge returned empty content.")
                    
                temp_eval_data = json.loads(eval_json_string.strip())
                
                if isinstance(temp_eval_data, dict) and 'evaluation_score' in temp_eval_data:
                    final_quiz_data = raw_quiz.copy()
                    final_quiz_data.update(temp_eval_data)
                    return final_quiz_data
                else:
                    raise ValueError("Invalid JSON evaluation output.")
            
            except Exception as e:
                print(f"    -> ⚠️ 퀴즈 평가 실패/오류 (시도 {attempt+1}): {type(e).__name__}: {e}. 재시도...")
                time.sleep(Config.API_RETRY_DELAY)
        
        return None

    # -----------------------------------------------------
    # Main Processing Loop
    # -----------------------------------------------------
    def process_quizzes_per_source(self, source_info: Dict[str, str]):
        """자료(파일) 당 퀴즈 생성 및 평가를 통합 관리"""
        
        if self.client is None or self.vectorstore is None:
            return
            
        category = source_info['category']
        file_name = source_info['file_name']
        source_full_text = source_info['text'] 
        
        print(f"\n-> 파일 처리 시작: {file_name} (Category: {category})")

        # 1. RAG Retrieval (자료 당 1회)
        search_query = f"파일 '{file_name}'의 내용 중 '{category}' 카테고리의 핵심 정보, 정의, 원리, 그리고 심화 개념까지 포함하는 포괄적인 정보를 알려줘."
        
        retrieved_chunks = self.vectorstore.similarity_search(
            query=search_query,
            k=Config.K_FINAL_CONTEXT, 
            filter={"file_name": file_name} 
        )
        
        if not retrieved_chunks:
            print(f"  -> 경고: 파일 '{file_name}'에 대한 관련 청크를 찾을 수 없습니다. 건너뜁니다.")
            return
            
        context = "\n\n---\n\n".join(chunk.page_content for chunk in retrieved_chunks)
        print(f"  -> 최종 RAG Context: 검색을 통해 {len(retrieved_chunks)} Chunks 확보됨.")

        # 2. 퀴즈 생성 및 평가 (난이도 루프)
        for difficulty, num_questions in Config.QUIZ_DISTRIBUTION.items():
            if num_questions == 0:
                continue
                
            difficulty_desc = Config.DIFFICULTY_MAPPING[difficulty]
            
            # 시스템 프롬프트 포매팅
            quiz_system_prompt = Config.quiz_system_prompt_template.format(
                difficulty=difficulty, difficulty_desc=difficulty_desc
            )
            eval_system_prompt = Config.eval_system_prompt_template.format(
                difficulty=difficulty, difficulty_desc=difficulty_desc
            )
            
            for i in range(num_questions):
                
                raw_quiz: Optional[Dict] = None
                new_quiz_vector: Optional[np.ndarray] = None
                
                for dup_attempt in range(Config.MAX_DUPLICATE_ATTEMPTS):
                    # 퀴즈 생성
                    user_prompt = f"""
                    아래 '참고 자료' (**파일 '{file_name}'에서 검색된 핵심 청크**)만을 사용하여 퀴즈를 **단 1개** 생성해주세요.
                    - 주제(Category): '{category}'
                    - 난이도(Difficulty): '{difficulty}'
                    
                    [참고 자료 (RAG 청크)]:
                    ---
                    {context} 
                    ---
                    """
                    raw_quiz = self._generate_quiz_with_retry(
                        quiz_system_prompt, user_prompt, category, difficulty, file_name, dup_attempt
                    )
                    
                    if not raw_quiz: break 
                    
                    # 중복 확인
                    new_quiz_text = self._get_text_for_embedding(raw_quiz)
                    new_quiz_vector = self._get_text_embedding(new_quiz_text)

                    is_duplicate = False
                    if new_quiz_vector is not None:
                        for existing_vector in self.all_cumulative_vectors:
                            similarity = self._get_cosine_similarity(new_quiz_vector, existing_vector)
                            if similarity >= Config.DUPLICATION_THRESHOLD:
                                is_duplicate = True
                                print(f"    -> 🚨 중복 발견! 유사도: {similarity:.4f}. 다시 생성 시도...")
                                break
                    
                    if not is_duplicate: break 
                    
                    if is_duplicate and dup_attempt == Config.MAX_DUPLICATE_ATTEMPTS - 1:
                        print(f"    -> 🛑 중복 제거 최종 실패. 이 퀴즈는 건너뜁니다.")
                        raw_quiz = None 
                        break 
                
                if not raw_quiz: continue
                
                # 퀴즈 평가
                evaluated_quiz = self._evaluate_quiz_with_retry(raw_quiz, eval_system_prompt, source_full_text)
                
                if evaluated_quiz:
                    evaluated_quiz['id'] = len(self.all_final_quizzes) + 1
                    self.all_final_quizzes.append(evaluated_quiz)
                    self.all_cumulative_vectors.append(new_quiz_vector) 
                    print(f"    -> ✅ {i+1}번째 퀴즈 (난이도 {difficulty}) (점수: {evaluated_quiz.get('evaluation_score')}) 생성/평가 완료.")
                else:
                    # 평가 최종 실패 시 0점 처리 후 저장 (데이터 손실 방지)
                    raw_quiz['evaluation_score'] = 0
                    raw_quiz['evaluation_comment'] = "LLM Judge 평가 최종 실패로 0점 처리됨."
                    raw_quiz['id'] = len(self.all_final_quizzes) + 1
                    self.all_final_quizzes.append(raw_quiz)
                    self.all_cumulative_vectors.append(new_quiz_vector if new_quiz_vector is not None else np.array([0]))
                    print(f"    -> 🛑 {i+1}번째 퀴즈 (난이도 {difficulty}) 평가 최종 실패. 0점 처리 후 저장.")

    def run(self):
        """전체 파이프라인 실행"""
        print("--- 🧠 AI Quiz Generator (Document-Centric RAG Pipeline) Start ---")

        if self.client is None:
            return
            
        all_source_data = self._extract_all_source_data()
        if not all_source_data:
            print("❌ 퀴즈 생성을 위한 PDF/JSONL 파일이 없습니다. 종료합니다.")
            return
            
        if not self.create_rag_index(all_source_data):
            print("❌ RAG 색인 생성에 실패했습니다. 종료합니다.")
            return

        total_files = len(all_source_data)
        total_quizzes_expected = total_files * Config.TOTAL_QUESTIONS_PER_SOURCE
        print(f"\n3. 🧠 {total_files}개 자료별 퀴즈 생성 시작. 총 예상 퀴즈 수: {total_quizzes_expected}개.")
        
        for source_info in all_source_data:
            self.process_quizzes_per_source(source_info)

        self._save_to_csv()
        
        print("\n--- 🏁 AI Quiz Generator Finish ---")
    
    # -----------------------------------------------------
    # Output & Finalization
    # -----------------------------------------------------
    def _save_to_csv(self):
        """최종 퀴즈 목록을 CSV 파일로 저장"""
        if not self.all_final_quizzes:
            print("🛑 No quizzes generated. CSV file not created.")
            return

        columns = [
            'id', 'category', 'difficulty', 'question', 
            'choice1', 'choice2', 'choice3', 'choice4', 
            'answer', 'comment', 
            'evaluation_score', 'evaluation_comment',
            'source_files' 
        ]
        
        # DataFrame 생성을 위한 데이터 정규화
        normalized_list = [{col: quiz.get(col, '') for col in columns} for quiz in self.all_final_quizzes]
            
        df = pd.DataFrame(normalized_list, columns=columns)
        
        df.to_csv(Config.OUTPUT_CSV_FILE, index=False, encoding='utf-8-sig')
        print(f"\n✅ Successfully saved {len(self.all_final_quizzes)} quizzes to {Config.OUTPUT_CSV_FILE}")

# --- 3. Run Block ---

if __name__ == "__main__":
    # 시스템 프롬프트는 Config 클래스의 정적 변수로 통합하여 가독성을 높입니다.
    Config.quiz_system_prompt_template = (
        "당신은 제공된 '참고 자료'만을 사용하여 고품질의 객관식 문제를 생성하는 전문 퀴즈 출제자이며 은행 및 금융전문가입니다. "
        "요청된 난이도는 **'{difficulty}' ({difficulty_desc})** 입니다. 이 기준에 맞춰 참고 자료의 핵심을 파악하여 객관식 4지선다형 문제를 한국어로 생성하세요. "
        "웹사이트, URL, 연락처를 묻는 문제는 절대 출제하지 마세요. "
        "반드시 다음 JSON 객체 구조를 지키세요. JSON 객체 외의 다른 텍스트는 포함하지 마세요. "
        "{{\"question\": \"문제 본문\", \"choice1\": \"보기 1\", \"choice2\": \"보기 2\", \"choice3\": \"보기 3\", \"choice4\": \"보기 4\", \"answer\": \"정답 보기의 텍스트 (예: 보기 1)\", \"comment\": \"정답에 대한 해설\"}}"
    )
    
    Config.eval_system_prompt_template = (
        "당신은 객관식 문제의 품질을 평가하는 전문 평가자 LLM이자, 은행 및 금융 전문가입니다. "
        "**평가 기준**: 요청된 난이도 **'{difficulty}'는 '{difficulty_desc}'**를 의미합니다. 이 기준에 맞춰 난이도 적절성을 엄격하게 평가하세요. " 
        "**🚨 엄격한 평가 단계 (추론 과정 명시 필수)**: "
        "1. **사실 확인(Factuality Check, 5점)**: 퀴즈의 **정답**이 '참고 자료'에 제시된 내용과 **문자 그대로 100% 일치**하는지 확인. **오답 보기 3개**가 참고 자료에 **허위 정보**로 간주되지 않고, 그럴듯한 오답(Distractor)으로 구성되었는지 확인. **하나라도 사실 관계가 틀리면 0점 처리.** "
        "2. **난이도 적절성(Relevance & Difficulty, 3점)**: 질문의 내용과 깊이가 요청된 난이도 '{difficulty}'에 적합한지 평가. "
        "3. **형식 및 명확성(Format & Clarity, 2점)**: JSON 형식을 준수했는지, 질문과 해설이 명확한지 평가. "
        "평가 기준: 정확성(5점) + 난이도 적절성(3점) + 형식 준수(2점)로 총 10점 만점입니다. "
        "결과는 반드시 **평가 필드가 추가된 단일 JSON 객체**로만 반환해야 합니다. 다른 텍스트는 절대 포함하지 마세요."
    )
    
    generator = QuizGenerator()
    generator.run()
