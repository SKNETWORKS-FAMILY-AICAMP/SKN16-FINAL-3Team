"""동아리 게시물 개수 확인"""
from sqlmodel import Session, select
from app.database import engine
from app.models.post import Post

with Session(engine) as session:
    # 전체 게시물 개수
    total = session.exec(select(Post).where(Post.is_deleted == False)).all()
    print(f"📊 전체 게시물: {len(total)}개")
    
    # 카테고리별 개수
    categories = {}
    for post in total:
        cat = post.category
        categories[cat] = categories.get(cat, 0) + 1
    
    print(f"\n📁 카테고리별 분류:")
    for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {cat}: {count}개")
    
    # 동아리 관련 게시물 (제목이나 내용에 "동아리" 포함)
    club_posts = []
    for post in total:
        if "동아리" in post.title or "동아리" in post.content:
            club_posts.append(post)
    
    print(f"\n🎯 동아리 관련 게시물: {len(club_posts)}개")
    if club_posts:
        print(f"\n📋 동아리 게시물 목록:")
        for idx, post in enumerate(club_posts, 1):
            print(f"  {idx}. [{post.category}] {post.title}")
    
    print(f"\n📋 전체 게시물 목록:")
    for idx, post in enumerate(total, 1):
        print(f"  {idx}. [{post.category}] {post.title}")
        if post.subcategory:
            print(f"      세부카테고리: {post.subcategory}")

