"""
동아리 라운지 게시판 API 라우터
멘토·멘티 취미 공유 커뮤니티
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List, Optional
from datetime import datetime, timedelta

from app.database import get_session
from app.models.user import User, UserRole
from app.models.post import (
    Post, PostCreate, PostRead, PostDetail,
    Comment, CommentCreate, CommentRead
)
from app.utils.auth import get_current_user

router = APIRouter(prefix="/posts", tags=["Anonymous Board"])

ROLE_LABELS = {
    UserRole.ADMIN.value: "관리자",
    UserRole.MENTOR.value: "멘토",
    UserRole.MENTEE.value: "멘티",
}


def get_user_identity(user: Optional[User]) -> tuple[str, str]:
    if not user:
        return ("알 수 없음", "역할 미정")
    role_value = user.role.value if isinstance(user.role, UserRole) else str(user.role)
    label = ROLE_LABELS.get(role_value, role_value)
    return (user.name, label)


def build_user_display(user: Optional[User]) -> str:
    name, label = get_user_identity(user)
    return f"{name} • {label}"


@router.post("/", response_model=PostRead)
async def create_post(
    post_data: PostCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    게시글 작성
    - 작성자는 "글쓴이"로 표시
    """
    subcategory = post_data.subcategory.strip() if post_data.subcategory else None
    if subcategory:
        if subcategory.startswith("#"):
            subcategory = subcategory[1:]
        subcategory = subcategory.strip() or None
    
    post = Post(
        title=post_data.title,
        content=post_data.content,
        category=post_data.category,
        subcategory=subcategory,
        author_id=current_user.id
    )
    
    session.add(post)
    session.commit()
    session.refresh(post)
    
    author_name, author_role_label = get_user_identity(current_user)
    
    return PostRead(
        id=post.id,
        title=post.title,
        content=post.content,
        category=post.category,
        subcategory=post.subcategory,
        view_count=post.view_count,
        comment_count=post.comment_count,
        created_at=post.created_at,
        updated_at=post.updated_at,
        author_alias=build_user_display(current_user),
        author_name=author_name,
        author_role_label=author_role_label
    )


@router.get("/", response_model=List[PostRead])
async def get_posts(
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    게시글 목록 조회
    - 삭제되지 않은 게시글만
    - 최신순 정렬
    - 목록에서는 작성자 정보 숨김
    - 취미 카테고리 표시 포함
    """
    statement = (
        select(Post)
        .where(Post.is_deleted == False)
        .order_by(Post.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    
    posts = session.exec(statement).all()

    author_cache: dict[int, Optional[User]] = {}
    
    result = []
    for post in posts:
        if post.author_id not in author_cache:
            author_cache[post.author_id] = session.get(User, post.author_id)
        author = author_cache[post.author_id]
        
        author_name, author_role_label = get_user_identity(author)
        
        result.append(PostRead(
            id=post.id,
            title=post.title,
            content=post.content,
            category=post.category,
            subcategory=post.subcategory,
            view_count=post.view_count,
            comment_count=post.comment_count,
            created_at=post.created_at,
            updated_at=post.updated_at,
            author_alias=build_user_display(author),
            author_name=author_name,
            author_role_label=author_role_label
        ))
    
    return result


@router.get("/mine", response_model=List[PostRead])
async def get_my_recent_posts(
    limit: int = 1,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    내가 작성한 최신 게시글
    """
    statement = (
        select(Post)
        .where(Post.is_deleted == False, Post.author_id == current_user.id)
        .order_by(Post.created_at.desc())
        .limit(limit)
    )
    my_posts = session.exec(statement).all()
    
    author_name, author_role_label = get_user_identity(current_user)
    result = []
    for post in my_posts:
        result.append(PostRead(
            id=post.id,
            title=post.title,
            content=post.content,
            category=post.category,
            subcategory=post.subcategory,
            view_count=post.view_count,
            comment_count=post.comment_count,
            created_at=post.created_at,
            updated_at=post.updated_at,
            author_alias=build_user_display(current_user),
            author_name=author_name,
            author_role_label=author_role_label
        ))
    return result


@router.get("/popular", response_model=List[PostRead])
async def get_popular_posts(
    limit: int = 3,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    최근 일주일 조회수 높은 게시물 조회 (홈페이지용)
    - 최근 7일간의 게시물만 대상
    - 조회수 높은 순으로 정렬
    """
    # 일주일 전 날짜 계산
    week_ago = datetime.utcnow() - timedelta(days=7)
    
    statement = (
        select(Post)
        .where(
            Post.is_deleted == False,
            Post.created_at >= week_ago
        )
        .order_by(Post.view_count.desc())
        .limit(limit)
    )
    
    posts = session.exec(statement).all()
    
    result = []
    for post in posts:
        author = session.get(User, post.author_id)
        author_name, author_role_label = get_user_identity(author)
        result.append(PostRead(
            id=post.id,
            title=post.title,
            content=post.content,
            category=post.category,
            subcategory=post.subcategory,
            view_count=post.view_count,
            comment_count=post.comment_count,
            created_at=post.created_at,
            updated_at=post.updated_at,
            author_alias=build_user_display(author),
            author_name=author_name,
            author_role_label=author_role_label
        ))
    
    return result


@router.get("/{post_id}", response_model=PostDetail)
async def get_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    게시글 상세 조회
    - 조회수 증가
    - 댓글 목록 포함
    - 게시글 작성자는 모든 사용자에게 "글쓴이"로 표시
    - 댓글 작성자는 게시글 작성자인 경우 "글쓴이", 다른 사람은 "익명1", "익명2" 순으로 표시
    """
    statement = select(Post).where(Post.id == post_id, Post.is_deleted == False)
    post = session.exec(statement).first()
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # 조회수 증가
    post.view_count += 1
    session.add(post)
    session.commit()
    
    # 댓글 조회
    comment_statement = (
        select(Comment)
        .where(Comment.post_id == post_id, Comment.is_deleted == False)
        .order_by(Comment.created_at.asc())
    )
    comments = session.exec(comment_statement).all()
    
    # 게시글 작성자 표시 (모든 사용자에게 "글쓴이"로 표시)
    post_author = session.get(User, post.author_id)
    post_author_alias = build_user_display(post_author)
    post_author_name, post_author_role_label = get_user_identity(post_author)
    
    # 댓글에 익명 번호 부여
    comment_reads = []

    comment_author_cache: dict[int, Optional[User]] = {}
    
    for comment in comments:
        if comment.author_id not in comment_author_cache:
            comment_author_cache[comment.author_id] = session.get(User, comment.author_id)
        comment_author = comment_author_cache[comment.author_id]
        author_alias = build_user_display(comment_author)
        author_name, author_role_label = get_user_identity(comment_author)
        
        comment_reads.append(CommentRead(
            id=comment.id,
            post_id=comment.post_id,
            content=comment.content,
            join_status=comment.join_status,
            join_approved_at=comment.join_approved_at,
            created_at=comment.created_at,
            author_alias=author_alias,
            is_author=comment.author_id == current_user.id,
            is_admin=current_user.role.value == "admin",
            author_name=author_name,
            author_role_label=author_role_label
        ))
    
    return PostDetail(
        post=PostRead(
            id=post.id,
            title=post.title,
            content=post.content,
            category=post.category,
            subcategory=post.subcategory,
            view_count=post.view_count,
            comment_count=post.comment_count,
            created_at=post.created_at,
            updated_at=post.updated_at,
            author_alias=post_author_alias,
            author_name=post_author_name,
            author_role_label=post_author_role_label
        ),
        comments=comment_reads,
        is_author=post.author_id == current_user.id,
        is_admin=current_user.role.value == "admin"
    )


@router.post("/comments", response_model=CommentRead)
async def create_comment(
    comment_data: CommentCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    댓글 작성
    - 작성자는 "글쓴이"로 표시
    - 게시글 댓글 수 증가
    """
    # 게시글 존재 확인
    post_statement = select(Post).where(Post.id == comment_data.post_id)
    post = session.exec(post_statement).first()
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # 댓글 순서 계산
    comment_count_statement = select(Comment).where(
        Comment.post_id == comment_data.post_id,
        Comment.is_deleted == False
    )
    existing_comments = session.exec(comment_count_statement).all()
    comment_order = len(existing_comments) + 1  # 순서는 1부터 시작
    
    # 댓글 생성
    join_status = "none"
    if current_user.id != post.author_id:
        join_status = "pending"
    
    comment = Comment(
        post_id=comment_data.post_id,
        content=comment_data.content,
        author_id=current_user.id,
        comment_order=comment_order,
        join_status=join_status
    )
    
    session.add(comment)
    
    # 게시글 댓글 수 증가
    post.comment_count += 1
    session.add(post)
    
    session.commit()
    session.refresh(comment)
    
    comment_author = current_user  # 현재 사용자
    author_alias = build_user_display(comment_author)
    author_name, author_role_label = get_user_identity(comment_author)
    
    return CommentRead(
        id=comment.id,
        post_id=comment.post_id,
        content=comment.content,
        join_status=comment.join_status,
        join_approved_at=comment.join_approved_at,
        created_at=comment.created_at,
        author_alias=author_alias,
        is_author=True,  # 댓글 작성자는 본인이므로 항상 True
        is_admin=current_user.role.value == "admin",
        author_name=author_name,
        author_role_label=author_role_label
    )


@router.put("/{post_id}", response_model=PostRead)
async def update_post(
    post_id: int,
    post_data: PostCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    게시글 수정
    - 작성자 본인 또는 관리자만 수정 가능
    """
    statement = select(Post).where(Post.id == post_id, Post.is_deleted == False)
    post = session.exec(statement).first()
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # 작성자 또는 관리자 확인
    if post.author_id != current_user.id and current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to update this post")
    
    # 게시글 수정
    post.title = post_data.title
    post.content = post_data.content
    post.category = post_data.category
    subcategory = post_data.subcategory.strip() if post_data.subcategory else None
    if subcategory:
        if subcategory.startswith("#"):
            subcategory = subcategory[1:]
        subcategory = subcategory.strip() or None
    post.subcategory = subcategory
    session.add(post)
    session.commit()
    session.refresh(post)
    
    return PostRead(
        id=post.id,
        title=post.title,
        content=post.content,
        category=post.category,
        subcategory=post.subcategory,
        view_count=post.view_count,
        comment_count=post.comment_count,
        created_at=post.created_at,
        updated_at=post.updated_at,
        author_alias="글쓴이"
    )


@router.delete("/{post_id}")
async def delete_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    게시글 삭제
    - 작성자 본인 또는 관리자만 삭제 가능
    - 소프트 삭제 (is_deleted = True)
    """
    statement = select(Post).where(Post.id == post_id)
    post = session.exec(statement).first()
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # 작성자 또는 관리자 확인
    if post.author_id != current_user.id and current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to delete this post")
    
    post.is_deleted = True
    session.add(post)
    session.commit()
    
    return {"message": "Post deleted successfully"}


@router.put("/comments/{comment_id}", response_model=CommentRead)
async def update_comment(
    comment_id: int,
    comment_data: CommentCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    댓글 수정
    - 작성자 본인 또는 관리자만 수정 가능
    """
    statement = select(Comment).where(Comment.id == comment_id, Comment.is_deleted == False)
    comment = session.exec(statement).first()
    
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    # 작성자 또는 관리자 확인
    if comment.author_id != current_user.id and current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to update this comment")
    
    # 댓글 수정
    comment.content = comment_data.content
    session.add(comment)
    session.commit()
    session.refresh(comment)
    
    # 게시글 정보 가져오기
    post_statement = select(Post).where(Post.id == comment.post_id)
    post = session.exec(post_statement).first()
    
    comment_author = session.get(User, comment.author_id)
    author_alias = build_user_display(comment_author)
    author_name, author_role_label = get_user_identity(comment_author)
    
    return CommentRead(
        id=comment.id,
        post_id=comment.post_id,
        content=comment.content,
        join_status=comment.join_status,
        join_approved_at=comment.join_approved_at,
        created_at=comment.created_at,
        author_alias=author_alias,
        is_author=comment.author_id == current_user.id,
        is_admin=current_user.role.value == "admin",
        author_name=author_name,
        author_role_label=author_role_label
    )


@router.delete("/comments/{comment_id}")
async def delete_comment(
    comment_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    댓글 삭제
    - 작성자 본인 또는 관리자만 삭제 가능
    """
    statement = select(Comment).where(Comment.id == comment_id)
    comment = session.exec(statement).first()
    
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    # 작성자 또는 관리자 확인
    if comment.author_id != current_user.id and current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to delete this comment")
    
    comment.is_deleted = True
    session.add(comment)
    
    # 게시글 댓글 수 감소
    post_statement = select(Post).where(Post.id == comment.post_id)
    post = session.exec(post_statement).first()
    if post:
        post.comment_count = max(0, post.comment_count - 1)
        session.add(post)
    
    session.commit()
    
    return {"message": "Comment deleted successfully"}


@router.post("/comments/{comment_id}/join", response_model=CommentRead)
async def approve_comment_join(
    comment_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    댓글 같이하기 승인
    - 게시글 작성자 또는 관리자만 승인 가능
    - 승인 시 추후 일정 연동을 위한 정보가 저장됨
    """
    comment = session.exec(
        select(Comment).where(Comment.id == comment_id, Comment.is_deleted == False)
    ).first()
    
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    post = session.exec(
        select(Post).where(Post.id == comment.post_id, Post.is_deleted == False)
    ).first()
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    if post.author_id != current_user.id and current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to approve this request")
    
    if comment.author_id == post.author_id:
        raise HTTPException(status_code=400, detail="Cannot approve your own comment")
    
    if comment.join_status == "approved":
        # 이미 승인된 경우 그대로 반환
        pass
    elif comment.join_status != "pending":
        raise HTTPException(status_code=400, detail="This comment is not awaiting approval")
    else:
        comment.join_status = "approved"
        comment.join_approved_at = datetime.utcnow()
        session.add(comment)
        session.commit()
        session.refresh(comment)
    
    comment_author = session.get(User, comment.author_id)
    author_alias = build_user_display(comment_author)
    author_name, author_role_label = get_user_identity(comment_author)
    
    return CommentRead(
        id=comment.id,
        post_id=comment.post_id,
        content=comment.content,
        join_status=comment.join_status,
        join_approved_at=comment.join_approved_at,
        created_at=comment.created_at,
        author_alias=author_alias,
        is_author=comment.author_id == current_user.id,
        is_admin=current_user.role.value == "admin",
        author_name=author_name,
        author_role_label=author_role_label
    )


@router.get("/comments/mine")
async def get_my_recent_comment_posts(
    limit: int = 1,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    내가 댓글을 단 게시글 중 최신 작성
    """
    statement = (
        select(Comment, Post)
        .join(Post, Comment.post_id == Post.id)
        .where(
            Comment.is_deleted == False,
            Post.is_deleted == False,
            Comment.author_id == current_user.id
        )
        .order_by(Comment.created_at.desc())
        .limit(limit)
    )
    
    results = session.exec(statement).all()
    response = []
    
    for comment, post in results:
        post_author = session.get(User, post.author_id)
        post_author_name, post_author_role_label = get_user_identity(post_author)
        response.append({
            "id": post.id,
            "title": post.title,
            "content": post.content,
            "category": post.category,
            "subcategory": post.subcategory,
            "view_count": post.view_count,
            "comment_count": post.comment_count,
            "created_at": post.created_at,
            "updated_at": post.updated_at,
            "author_alias": build_user_display(post_author),
             "author_name": post_author_name,
             "author_role_label": post_author_role_label,
            "highlight_comment": {
                "content": comment.content,
                "created_at": comment.created_at
            }
        })
    
    return response
