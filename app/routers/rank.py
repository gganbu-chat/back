from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.sql import func
from sqlalchemy.orm import Session
import os

from app.database.session import get_db
from app.models.models import Character, ChatRoom, ChatLog, Image, ImageMapping, Tag, Field as DBField

router = APIRouter()

@router.get("/api/characters/top3/{user_idx}")
def get_top3_characters(user_idx: int, db: Session = Depends(get_db), request: Request = None):
    try:
        # 기본 쿼리 설정
        query = (
            db.query(
                Character.char_idx,
                Character.char_name,
                func.count(ChatLog.session_id).label("log_count"),
                Image.file_path
            )
            .join(ChatRoom, ChatRoom.char_prompt_id == Character.char_idx)
            .join(ChatLog, ChatLog.chat_id == ChatRoom.chat_id)
            .outerjoin(ImageMapping, ImageMapping.char_idx == Character.char_idx)
            .outerjoin(Image, Image.img_idx == ImageMapping.img_idx)
            .filter(Character.character_owner == user_idx)
            .group_by(Character.char_idx, Character.char_name, Image.file_path)
            .order_by(func.count(ChatLog.session_id).desc())
            .limit(3)
        )

        # 쿼리 결과 가져오기
        results = query.all()

        if not results:
            return {"message": "사용 기록이 있는 캐릭터가 없습니다."}

        # 요청 URL에서 base URL 생성
        base_url = f"{request.base_url.scheme}://{request.base_url.netloc}" if request else ""

        # 결과 처리
        top_characters = []
        for char_idx, char_name, log_count, image_path in results:
            # 이미지 경로 처리
            image_url = f"{base_url}/static/{os.path.basename(image_path)}" if image_path else None
            top_characters.append({
                "char_idx": char_idx,
                "char_name": char_name,
                "log_count": log_count,
                "character_image": image_url,
            })

        return top_characters

    except Exception as e:
        print(f"Error fetching top characters: {e}")
        raise HTTPException(status_code=500, detail="캐릭터 데이터를 가져오는 중 오류가 발생했습니다.")

@router.get("/api/fields/top3/{user_idx}")
def get_top3_fields(user_idx: int, db: Session = Depends(get_db)):
    """
    특정 사용자가 생성한 캐릭터들이 속한 필드 TOP 3를 반환하는 API.
    """
    try:
        # 필드별 캐릭터 수 집계 쿼리
        query = (
            db.query(
                DBField.field_idx,
                DBField.field_category,
                func.count(Character.char_idx).label("char_count")
            )
            .join(Character, Character.field_idx == DBField.field_idx)
            .filter(Character.character_owner == user_idx)
            .group_by(DBField.field_idx, DBField.field_category)
            .order_by(func.count(Character.char_idx).desc())
            .limit(3)
        )

        # 쿼리 실행
        results = query.all()

        # 결과가 없을 때 메시지 처리
        if not results:
            return {"message": "사용자가 생성한 캐릭터가 속한 필드가 없습니다."}

        # 결과 리스트 생성
        top_fields = [
            {"field_idx": field_idx, "field_category": field_category, "char_count": char_count}
            for field_idx, field_category, char_count in results
        ]

        return {"top_fields": top_fields}

    except Exception as e:
        print(f"Error fetching top fields: {e}")
        raise HTTPException(status_code=500, detail="필드 데이터를 가져오는 중 오류가 발생했습니다.")

@router.get("/api/tags/top3/{user_idx}", response_model=dict)
def get_top3_tags(user_idx: int, db: Session = Depends(get_db)):
    """
    특정 사용자가 생성한 캐릭터들의 태그 TOP 3를 반환하는 API.
    """
    try:
        # 태그별 사용 횟수 집계 쿼리
        query = (
            db.query(
                Tag.tag_name,
                func.count(Tag.tag_idx).label("tag_count")
            )
            .join(Character, Character.char_idx == Tag.char_idx)
            .filter(Character.character_owner == user_idx, Tag.is_deleted == False)
            .group_by(Tag.tag_name)
            .order_by(func.count(Tag.tag_idx).desc())
            .limit(3)
        )

        # 쿼리 실행
        results = query.all()

        # 결과가 없을 때 메시지 처리
        if not results:
            return {"message": "사용자가 생성한 캐릭터에 연결된 태그가 없습니다."}

        # 결과 리스트 생성
        top_tags = [{"tag_name": tag_name, "tag_count": tag_count} for tag_name, tag_count in results]

        return {"top_tags": top_tags}

    except Exception as e:
        print(f"Error fetching top tags: {e}")
        raise HTTPException(status_code=500, detail="태그 데이터를 가져오는 중 오류가 발생했습니다.")