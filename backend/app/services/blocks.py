from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.client_user_block import ClientUserBlock


def find_block(db: Session, client_id, user) -> ClientUserBlock | None:
    return db.scalar(
        select(ClientUserBlock).where(
            ClientUserBlock.client_id == client_id,
            or_(
                ClientUserBlock.user_id == user.id,
                ClientUserBlock.email == user.email,
            ),
        )
    )


def list_blocks(db: Session, client_id) -> list[ClientUserBlock]:
    return list(
        db.scalars(
            select(ClientUserBlock)
            .where(ClientUserBlock.client_id == client_id)
            .order_by(ClientUserBlock.created_at.desc())
        ).all()
    )


def add_block(
    db: Session,
    client,
    *,
    email: str | None = None,
    user_id=None,
    reason: str = "",
) -> ClientUserBlock:
    if not email and user_id is None:
        raise ValueError("email 或 user_id 至少填一项")
    if email:
        email = email.lower()
        existing = db.scalar(
            select(ClientUserBlock).where(
                ClientUserBlock.client_id == client.id,
                ClientUserBlock.email == email,
            )
        )
    else:
        existing = db.scalar(
            select(ClientUserBlock).where(
                ClientUserBlock.client_id == client.id,
                ClientUserBlock.user_id == user_id,
            )
        )
    if existing is not None:
        raise ValueError("该账号已被此网站封禁")
    block = ClientUserBlock(
        client_id=client.id,
        user_id=user_id,
        email=email,
        reason=reason,
    )
    db.add(block)
    db.commit()
    db.refresh(block)
    return block


def remove_block(db: Session, block_id) -> None:
    block = db.get(ClientUserBlock, block_id)
    if block is None:
        raise ValueError("封禁记录不存在")
    db.delete(block)
    db.commit()
