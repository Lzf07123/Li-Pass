"""管理后台数据统计：从现有用户/会话/审计表实时聚合，不做额外持久化。"""

import threading
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import Column, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.audit_log import AuditLog
from app.models.session import Session as SessionModel
from app.models.user import User, UserRole, UserStatus
from app.services import geoip

TZ = timezone(timedelta(hours=8))  # Asia/Shanghai，无夏令时
LOGIN_ACTIONS = ("login", "2fa_login")
AUTH_METHODS = ("password", "email_otp", "totp", "recovery")
REGION_TOP_N = 10
_CACHE_TTL_SECONDS = 60.0
_cache_lock = threading.Lock()
_CACHE: dict[int, tuple[float, dict]] = {}

# ip2region 省份名 → 地图 GeoJSON 的省级行政区全名（覆盖简称/别名变体）。
PROVINCE_ALIASES = {
    "内蒙古": "内蒙古自治区",
    "广西": "广西壮族自治区",
    "西藏": "西藏自治区",
    "宁夏": "宁夏回族自治区",
    "新疆": "新疆维吾尔自治区",
    "香港": "香港特别行政区",
    "澳门": "澳门特别行政区",
    "台湾": "台湾省",
}
GEO_PROVINCES = frozenset(
    {
        "北京市",
        "天津市",
        "河北省",
        "山西省",
        "内蒙古自治区",
        "辽宁省",
        "吉林省",
        "黑龙江省",
        "上海市",
        "江苏省",
        "浙江省",
        "安徽省",
        "福建省",
        "江西省",
        "山东省",
        "河南省",
        "湖北省",
        "湖南省",
        "广东省",
        "广西壮族自治区",
        "海南省",
        "重庆市",
        "四川省",
        "贵州省",
        "云南省",
        "西藏自治区",
        "陕西省",
        "甘肃省",
        "青海省",
        "宁夏回族自治区",
        "新疆维吾尔自治区",
        "台湾省",
        "香港特别行政区",
        "澳门特别行政区",
    }
)


def _day_expr(db: Session, column: Column) -> object:
    """按 Asia/Shanghai 自然日截断：SQLite 与 PostgreSQL 两种方言。"""
    if db.get_bind().dialect.name == "sqlite":
        return func.strftime("%Y-%m-%d", column, "+8 hours")
    return func.date(func.timezone("Asia/Shanghai", column))


def _count(db: Session, stmt) -> int:
    return db.scalar(stmt) or 0


def _overview(db: Session, now: datetime) -> dict:
    settings = get_settings()
    idle_cutoff = now - timedelta(minutes=settings.session_idle_minutes)
    total = _count(db, select(func.count()).select_from(User))
    active = _count(
        db,
        select(func.count())
        .select_from(User)
        .where(User.status == UserStatus.active),
    )
    admins = _count(
        db,
        select(func.count())
        .select_from(User)
        .where(User.role == UserRole.admin),
    )
    verified = _count(
        db,
        select(func.count())
        .select_from(User)
        .where(User.email_verified_at.is_not(None)),
    )
    online = _count(
        db,
        select(func.count())
        .select_from(SessionModel)
        .where(
            SessionModel.revoked_at.is_(None),
            SessionModel.expires_at >= now,
            SessionModel.last_used_at >= idle_cutoff,
        ),
    )
    total_logins = _count(
        db,
        select(func.count())
        .select_from(AuditLog)
        .where(AuditLog.action.in_(LOGIN_ACTIONS)),
    )
    return {
        "total_users": total,
        "active_users": active,
        "disabled_users": total - active,
        "admins": admins,
        "verified_users": verified,
        "online_sessions": online,
        "total_logins": total_logins,
    }


def _date_key(value) -> str:
    """SQLite 返回字符串日期，PostgreSQL 返回 date 对象，统一为 ISO 字符串。"""
    return value if isinstance(value, str) else value.isoformat()


def _daily_series(db: Session, days: int, now: datetime) -> list[dict]:
    start = now - timedelta(days=days)

    login_day = _day_expr(db, AuditLog.created_at)
    login_rows = db.execute(
        select(
            login_day.label("day"),
            func.count().label("logins"),
            func.count(func.distinct(AuditLog.actor_id)).label("login_users"),
        )
        .where(
            AuditLog.action.in_(LOGIN_ACTIONS),
            AuditLog.created_at >= start,
            AuditLog.created_at < now,
        )
        .group_by(login_day)
    ).all()

    register_day = _day_expr(db, User.created_at)
    register_rows = db.execute(
        select(register_day.label("day"), func.count().label("registrations"))
        .where(User.created_at >= start, User.created_at < now)
        .group_by(register_day)
    ).all()

    local_now = now.astimezone(TZ)
    points: dict[str, dict] = {}
    for offset in range(days - 1, -1, -1):
        key = (local_now - timedelta(days=offset)).date().isoformat()
        points[key] = {
            "date": key,
            "logins": 0,
            "login_users": 0,
            "registrations": 0,
        }

    for day, logins, login_users in login_rows:
        key = _date_key(day)
        if key in points:
            points[key]["logins"] = int(logins)
            points[key]["login_users"] = int(login_users)

    for day, registrations in register_rows:
        key = _date_key(day)
        if key in points:
            points[key]["registrations"] = int(registrations)

    return list(points.values())


def _auth_methods(db: Session, now: datetime) -> list[dict]:
    settings = get_settings()
    idle_cutoff = now - timedelta(minutes=settings.session_idle_minutes)
    rows = db.execute(
        select(SessionModel.auth_method, func.count())
        .where(
            SessionModel.revoked_at.is_(None),
            SessionModel.expires_at >= now,
            SessionModel.last_used_at >= idle_cutoff,
        )
        .group_by(SessionModel.auth_method)
    ).all()

    counts = {method: 0 for method in AUTH_METHODS}
    extra: dict[str, int] = {}
    for method, count in rows:
        if method in counts:
            counts[method] = int(count)
        else:
            extra[method] = int(count)

    result = [
        {"method": method, "count": counts[method]} for method in AUTH_METHODS
    ]
    result.extend(
        {"method": method, "count": count} for method, count in extra.items()
    )
    return result


def _regions(db: Session, days: int, now: datetime) -> list[dict]:
    """窗口内成功登录 IP 的归属地 Top 10；IP 库未安装时返回空。"""
    if not geoip.resolver_ready():
        return []
    start = now - timedelta(days=days)
    rows = db.execute(
        select(AuditLog.ip, func.count())
        .where(
            AuditLog.action.in_(LOGIN_ACTIONS),
            AuditLog.created_at >= start,
            AuditLog.created_at < now,
            AuditLog.ip.is_not(None),
        )
        .group_by(AuditLog.ip)
    ).all()
    counts: dict[str, int] = {}
    for ip, count in rows:
        if not ip:
            continue
        key = geoip.describe_ip(ip) or "未知"
        counts[key] = counts.get(key, 0) + int(count)
    ordered = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    result = [
        {"region": name, "count": count}
        for name, count in ordered[:REGION_TOP_N]
    ]
    rest = sum(count for _, count in ordered[REGION_TOP_N:])
    if rest:
        result.append({"region": "其它", "count": rest})
    return result


def _regions_map(db: Session, days: int, now: datetime) -> dict:
    """窗口内登录 IP 按省级行政区聚合（供中国地图着色）；海外/内网/未知单独汇总。"""
    if not geoip.resolver_ready():
        return {
            "map": [],
            "overseas": 0,
            "internal": 0,
            "unknown": 0,
        }
    start = now - timedelta(days=days)
    rows = db.execute(
        select(AuditLog.ip, func.count())
        .where(
            AuditLog.action.in_(LOGIN_ACTIONS),
            AuditLog.created_at >= start,
            AuditLog.created_at < now,
            AuditLog.ip.is_not(None),
        )
        .group_by(AuditLog.ip)
    ).all()
    counts: dict[str, int] = {}
    overseas = 0
    internal = 0
    unknown = 0
    for ip, count in rows:
        if not ip:
            continue
        result, label = geoip.locate_ip(ip)
        if label == "内网地址" or label == "保留地址":
            internal += int(count)
            continue
        if label == "未知" or result is None:
            unknown += int(count)
            continue
        # 库内未识别记录（country 为空，如 "0|0|0|0|0"）应归「未知」，
        # 只有明确解析为其他国家时才计入「海外」。
        if result.country == "中国":
            raw_province = (result.province or "").strip()
            province = PROVINCE_ALIASES.get(raw_province, raw_province)
            if province in GEO_PROVINCES:
                counts[province] = counts.get(province, 0) + int(count)
            else:
                unknown += int(count)
        elif result.country is None:
            unknown += int(count)
        else:
            overseas += int(count)
    ordered = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    return {
        "map": [{"name": name, "value": value} for name, value in ordered],
        "overseas": overseas,
        "internal": internal,
        "unknown": unknown,
    }


def _collect_stats(db: Session, days: int) -> dict:
    """聚合一次统计快照；days 的 7–90 边界由路由层校验。"""
    now = datetime.now(timezone.utc)
    regions_map = _regions_map(db, days, now)
    return {
        "generated_at": now.isoformat(),
        "timezone": "Asia/Shanghai",
        "days": days,
        "overview": _overview(db, now),
        "daily": _daily_series(db, days, now),
        "auth_methods": _auth_methods(db, now),
        "regions": _regions(db, days, now),
        "regions_map": regions_map["map"],
        "regions_other": {
            "overseas": regions_map["overseas"],
            "internal": regions_map["internal"],
            "unknown": regions_map["unknown"],
        },
    }


def collect_admin_stats(db: Session, days: int) -> dict:
    """短 TTL 进程内缓存：降低管理端高频刷新时的聚合查询压力。"""
    monotonic = time.monotonic()
    with _cache_lock:
        cached = _CACHE.get(days)
        if cached is not None and monotonic - cached[0] < _CACHE_TTL_SECONDS:
            return cached[1]
    snapshot = _collect_stats(db, days)
    with _cache_lock:
        _CACHE[days] = (time.monotonic(), snapshot)
    return snapshot


def invalidate_admin_stats_cache() -> None:
    """用户数据变更（注册/删除/禁用/角色调整）后调用，清空统计快照缓存。

    60 秒 TTL 缓存只用于降低高频刷新压力；对"禁用后立即查看统计"
    这类强一致性诉求，必须在写路径上主动失效，否则会命中旧快照。
    """
    with _cache_lock:
        _CACHE.clear()
