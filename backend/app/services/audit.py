from app.models.audit_log import AuditLog

AUDIT_CATEGORIES = frozenset(
    {
        "auth",
        "user",
        "2fa",
        "consent",
        "oidc",
        "admin_user",
        "admin_client",
        "admin_block",
        "admin_settings",
        "security",
        "other",
    }
)


def log_audit(
    db,
    actor_type: str,
    actor_id: str | None,
    action: str,
    category: str = "other",
    target_type: str | None = None,
    target_id: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    detail: dict | None = None,
) -> None:
    # 数据库列为 VARCHAR(300)/VARCHAR(64)，超长请求头会直接报错，统一截断。
    if category not in AUDIT_CATEGORIES:
        category = "other"
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
            category=category,
            target_type=target_type,
            target_id=target_id,
            ip=ip,
            user_agent=user_agent,
            detail=detail,
        )
    )
    db.commit()


def log_rate_limit_rejected_once(
    db,
    action: str,
    count: int,
    limit: int,
    increment: int = 1,
    actor_type: str = "system",
    actor_id: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    detail: dict | None = None,
) -> None:
    """每个限流窗口只记录第一次拒绝，避免被持续 429 请求刷爆审计表。"""
    if count > limit and count - increment <= limit:
        log_audit(
            db,
            actor_type,
            actor_id,
            "rate_limit_rejected",
            category="security",
            ip=ip,
            user_agent=user_agent,
            detail=detail or {"action": action, "reason": "rate_limit"},
        )


def mask_phone(phone: str) -> str:
    """手机号落审计日志前掩码：保留前 3 位与后 4 位。"""
    if len(phone) < 7:
        return "****"
    return f"{phone[:3]}****{phone[-4:]}"
