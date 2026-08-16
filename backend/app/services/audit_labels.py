"""审计日志的中文展示标签（分类/动作/操作者类型）。

标签只服务于管理后台展示：审计存储层仍保留原始英文枚举值，
保证历史数据、统计聚合与外部解析不受展示改动影响。未知值原样回退，
新增动作未及时补标签时也不至于在界面上消失。
"""

CATEGORY_LABELS: dict[str, str] = {
    "auth": "认证",
    "user": "用户中心",
    "2fa": "二次验证",
    "consent": "授权确认",
    "oidc": "OIDC 单点登录",
    "admin_user": "用户管理",
    "admin_client": "应用管理",
    "admin_block": "黑名单",
    "admin_settings": "站点设置",
    "admin_notification": "通知管理",
    "security": "安全",
    "other": "其他",
}

ACTOR_TYPE_LABELS: dict[str, str] = {
    "user": "用户",
    "admin": "管理员",
    "client": "授权网站",
    "system": "系统",
}

ACTION_LABELS: dict[str, str] = {
    "2fa_email_auto_enabled": "自动启用邮箱二次验证",
    "2fa_email_disable": "关闭邮箱二次验证",
    "2fa_email_enable": "开启邮箱二次验证",
    "2fa_login": "二次验证登录",
    "2fa_login_failed": "二次验证失败",
    "2fa_totp_enable": "开启 TOTP 认证器",
    "2fa_trusted_skip": "可信设备免二次验证",
    "admin_batch_delete_user": "批量删除用户",
    "admin_batch_invite_user": "批量邀请注册",
    "admin_batch_revoke_session": "批量下线会话",
    "admin_batch_update_user": "批量更新用户",
    "admin_cancel_invite": "取消邀请",
    "admin_create_client": "创建授权网站",
    "admin_create_user": "代建账号",
    "admin_delete_client": "删除授权网站",
    "admin_delete_invite": "删除邀请",
    "admin_delete_user": "删除用户",
    "admin_invite_user": "邀请注册",
    "admin_recall_notification": "撤回通知",
    "admin_resend_invite": "重发邀请",
    "admin_reset_2fa": "重置二次验证",
    "admin_reset_client_secret": "重置客户端密钥",
    "admin_reset_password": "重置用户密码",
    "admin_revoke_all_sessions": "全部会话下线",
    "admin_revoke_session": "强制下线会话",
    "admin_send_notification": "发送通知",
    "admin_update_client": "更新授权网站",
    "admin_update_ip2region": "更新 IP 归属地库",
    "admin_update_site_setting": "更新站点设置",
    "admin_update_user": "更新用户",
    "admin_view_stats": "查看数据统计",
    "admin_view_system": "查看系统信息",
    "app_consent_revoke": "取消应用授权",
    "avatar_upload": "上传头像",
    "block_add": "添加封禁",
    "block_remove": "解除封禁",
    "consent_approve": "同意授权",
    "consent_deny": "拒绝授权",
    "email_change": "更换登录邮箱",
    "email_change_failed": "更换邮箱失败",
    "email_change_request": "请求更换邮箱",
    "email_verify": "验证邮箱",
    "email_verify_resend": "重发验证邮件",
    "login": "登录",
    "login_failed": "登录失败",
    "login_step1": "登录进入二次验证",
    "logout": "退出登录",
    "logout_local": "退出当前账号",
    "oauth_authorize": "OIDC 授权",
    "oidc_end_session": "OIDC 统一登出",
    "password_change": "修改密码",
    "password_reset": "重置密码",
    "password_reset_request": "请求重置密码",
    "phone_bind": "绑定手机",
    "phone_bind_send": "发送绑定验证码",
    "profile_update": "更新个人资料",
    "rate_limit_rejected": "限流拦截",
    "session_revoke": "撤销会话",
    "session_revoke_all": "退出所有设备",
    "stepup_2fa_failed": "二次验证复核失败",
    "stepup_2fa_send": "发送复核验证码",
    "stepup_failed": "密码复核失败",
    "stepup_required": "要求重新验证密码",
    "stepup_verify_success": "密码复核成功",
    "trusted_device_granted": "授予可信设备",
    "trusted_device_revoked": "撤销可信设备",
    "user_delete_self": "注销账号",
    "user_register": "注册账号",
    "user_register_by_invite": "受邀注册账号",
}


def category_label(category: str | None) -> str:
    if not category:
        return CATEGORY_LABELS["other"]
    return CATEGORY_LABELS.get(category, category)


def actor_type_label(actor_type: str) -> str:
    return ACTOR_TYPE_LABELS.get(actor_type, actor_type)


def action_label(action: str) -> str:
    return ACTION_LABELS.get(action, action)
