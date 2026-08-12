from app.models.audit_log import AuditLog


def log_audit(
    db,
    actor_type: str,
    actor_id: str | None,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    detail: dict | None = None,
) -> None:
    # 数据库列为 VARCHAR(300)/VARCHAR(64)，超长请求头会直接报错，统一截断。
    user_agent = (user_agent or "")[:300] or None
    ip = (ip or "")[:64] or None
    actor_id = (actor_id or "")[:64] or None
    target_id = (target_id or "")[:64] or None
    action = (action or "")[:80]
    db.add(
        AuditLog(
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            ip=ip,
            user_agent=user_agent,
            detail=detail,
        )
    )
    db.commit()
