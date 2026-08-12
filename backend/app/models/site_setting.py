from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SiteSetting(Base):
    """站点级运行时设置（key-value）。

    用于承载管理后台可改的开关，例如公开注册；未写入的 key 由代码回退到
    环境变量默认值，保证全新部署/未配置时行为与旧版本一致。
    """

    __tablename__ = "site_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(String(500))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
