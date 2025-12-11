from sqlmodel import Session, select, func
from app.database import engine
from app.models.document import ProductChunk
from pgvector.sqlalchemy import Vector

def check_db():
    with Session(engine) as session:
        # LON-MTG 상품의 청크 확인
        product_code_to_check = 'LON-MTG'
        chunks = session.exec(select(ProductChunk).where(ProductChunk.product_code == product_code_to_check)).all()
        
        print(f"ProductChunk count for {product_code_to_check}: {len(chunks)}")
        
        valid_embeddings = 0
        for chunk in chunks:
            if chunk.embedding is not None:
                valid_embeddings += 1
                
        print(f"Valid embeddings: {valid_embeddings} / {len(chunks)}")
        
        if valid_embeddings > 0:
            sample = chunks[0]
            print(f"Sample embedding dimension: {len(sample.embedding)}")
            print(f"Sample embedding type: {type(sample.embedding)}")
            print(f"Sample content: {sample.content[:50]}...")

if __name__ == "__main__":
    check_db()

