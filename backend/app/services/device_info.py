"""设备信息解析：Client Hints 优先，User-Agent 降级。

详细型号只有 Chromium 系浏览器通过 Client Hints（Sec-CH-UA-Model）提供；
iOS Safari / Firefox 出于隐私不提供型号，只能降级到“iPhone/Android/Windows”粒度。
"""

import re
from dataclasses import dataclass
from typing import Mapping

# Chromium Client Hints 的 GREASE 品牌 token：以 Not 开头、Brand 结尾，
# 中间各带一个非字母数字字符（如 Not A;Brand / Not)A;Brand / Not=A?Brand），
# 具体字符随 Chrome 版本轮换，因此按结构匹配而不是枚举黑名单。
_GREASE_BRAND = r"Not[^A-Za-z0-9]A[^A-Za-z0-9]Brand"
_GREASE_BRAND_FULL = re.compile(f"^{_GREASE_BRAND}$")
_GREASE_BRAND_ANY = re.compile(_GREASE_BRAND)


@dataclass(frozen=True)
class DeviceFingerprint:
    model: str | None = None
    platform: str | None = None
    platform_version: str | None = None
    browser: str | None = None
    mobile: bool | None = None


def _strip(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().strip('"').strip()
    return cleaned or None


def parse_ch_headers(headers: Mapping[str, str]) -> DeviceFingerprint:
    model = _strip(headers.get("sec-ch-ua-model"))
    platform = _strip(headers.get("sec-ch-ua-platform"))
    platform_version = _strip(headers.get("sec-ch-ua-platform-version"))
    mobile = None
    mobile_raw = headers.get("sec-ch-ua-mobile")
    if mobile_raw == "?1":
        mobile = True
    elif mobile_raw == "?0":
        mobile = False
    browser = None
    brand_map = {
        "Google Chrome": "Chrome",
        "Microsoft Edge": "Edge",
        "Opera": "Opera",
    }
    candidates = [
        name.strip()
        for name in re.findall(r'"([^"]*)";\s*v=', headers.get("sec-ch-ua") or "")
        if name.strip() and not _GREASE_BRAND_FULL.match(name.strip())
    ]
    if candidates:
        # 优先取真实浏览器品牌；仅剩 Chromium 时（Chromium 本体）也保留它
        browser_name = next(
            (name for name in candidates if name != "Chromium"),
            candidates[0],
        )
        browser = brand_map.get(browser_name, browser_name)
    return DeviceFingerprint(model, platform, platform_version, browser, mobile)


def parse_user_agent(ua: str) -> DeviceFingerprint:
    ua = ua or ""
    model = None
    platform = None
    platform_version = None
    browser = None
    mobile = False

    if re.search(r"iPhone|iPod", ua):
        model, platform, mobile = "iPhone", "iOS", True
    elif "iPad" in ua or ("Macintosh" in ua and "Mobile/" in ua):
        model, platform, mobile = "iPad", "iOS", True
    elif "Android" in ua:
        platform, mobile = "Android", True
    elif re.search(r"Macintosh|Mac OS X", ua):
        platform = "macOS"
    elif "Windows" in ua:
        platform = "Windows"
    elif "Linux" in ua or "X11" in ua:
        platform = "Linux"

    ios_match = re.search(r"(?:iPhone OS|CPU OS|iPad OS) (\d+)[_](\d+)", ua)
    if ios_match and platform == "iOS":
        platform_version = f"{ios_match.group(1)}.{ios_match.group(2)}"
    android_match = re.search(r"Android (\d+(?:\.\d+)*)", ua)
    if android_match and platform == "Android":
        platform_version = android_match.group(1)

    if re.search(r"EdgA?/|EdgiOS/", ua):
        browser = "Edge"
    elif re.search(r"OPR/|OPiOS/", ua):
        browser = "Opera"
    elif re.search(r"SamsungBrowser/", ua):
        browser = "Samsung Internet"
    elif re.search(r"FxiOS/|Firefox/", ua):
        browser = "Firefox"
    elif re.search(r"CriOS/|Chrome/", ua):
        browser = "Chrome"
    elif "Safari/" in ua:
        browser = "Safari"

    return DeviceFingerprint(model, platform, platform_version, browser, mobile)


def build_device_label(fp: DeviceFingerprint) -> str:
    parts: list[str] = []
    if fp.model:
        parts.append(fp.model)
    if fp.platform:
        os_part = fp.platform
        if fp.platform_version:
            os_part = f"{os_part} {fp.platform_version}"
        parts.append(os_part)
    if fp.browser:
        parts.append(fp.browser)
    return " · ".join(parts) or "未知设备"


def describe_session_device(device_name: str, user_agent: str) -> str:
    """读取侧设备名：历史会话的 device_name 可能是原始 UA，解析为友好名。

    同时修复历史脏数据：早期版本把 Client Hints 的 GREASE token（如
    Not=A?Brand）当成浏览器名写入了 device_name。此时优先按原始 UA 重建，
    无 UA 可用时剔除名称中的 GREASE 片段。
    """
    name = (device_name or "").strip()
    if name and "Mozilla/" not in name:
        if _GREASE_BRAND_ANY.search(name):
            repaired = build_device_label(parse_user_agent(user_agent or ""))
            if repaired != "未知设备":
                return repaired[:120]
            segments = [
                segment.strip()
                for segment in name.split("·")
                if segment.strip() and not _GREASE_BRAND_FULL.match(segment.strip())
            ]
            name = " · ".join(segments)
            if not name:
                return "未知设备"
        return name[:120]
    label = build_device_label(parse_user_agent(user_agent or name))
    if label != "未知设备":
        return label[:120]
    return name[:120] if name else "未知设备"
