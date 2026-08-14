from sqlalchemy import select

from app.models.session import Session as SessionModel
from app.services.device_info import (
    build_device_label,
    describe_session_device,
    parse_ch_headers,
    parse_user_agent,
)

IPHONE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 "
    "Mobile/15E148 Safari/604.1"
)
ANDROID_CHROME_UA = (
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
)
WINDOWS_CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
MAC_SAFARI_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15"
)
FIREFOX_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) "
    "Gecko/20100101 Firefox/129.0"
)


def test_parse_client_hints_model():
    fp = parse_ch_headers(
        {
            "sec-ch-ua-model": '"Pixel 8"',
            "sec-ch-ua-platform": '"Android"',
            "sec-ch-ua-platform-version": '"14"',
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua": (
                '"Not)A;Brand";v="99", "Chromium";v="124", '
                '"Google Chrome";v="124"'
            ),
        }
    )
    assert fp.model == "Pixel 8"
    assert fp.platform == "Android"
    assert fp.platform_version == "14"
    assert fp.mobile is True
    assert fp.browser == "Chrome"


def test_parse_ua_iphone_safari():
    fp = parse_user_agent(IPHONE_UA)
    assert fp.model == "iPhone"
    assert fp.platform == "iOS"
    assert fp.platform_version == "17.5"
    assert fp.mobile is True
    assert fp.browser == "Safari"


def test_parse_ua_android_chrome():
    fp = parse_user_agent(ANDROID_CHROME_UA)
    assert fp.model is None
    assert fp.platform == "Android"
    assert fp.platform_version == "14"
    assert fp.mobile is True
    assert fp.browser == "Chrome"


def test_parse_ua_desktop_browsers():
    windows = parse_user_agent(WINDOWS_CHROME_UA)
    assert windows.platform == "Windows"
    assert windows.browser == "Chrome"
    assert windows.mobile is False

    mac = parse_user_agent(MAC_SAFARI_UA)
    assert mac.platform == "macOS"
    assert mac.browser == "Safari"

    firefox = parse_user_agent(FIREFOX_UA)
    assert firefox.platform == "Windows"
    assert firefox.browser == "Firefox"


def test_build_device_label_prefers_model():
    ch = parse_ch_headers(
        {
            "sec-ch-ua-model": '"MacBook Pro"',
            "sec-ch-ua-platform": '"macOS"',
            "sec-ch-ua-platform-version": '"14.5"',
            "sec-ch-ua-mobile": "?0",
        }
    )
    assert build_device_label(ch) == "MacBook Pro · macOS 14.5"
    assert build_device_label(parse_user_agent(IPHONE_UA)) == (
        "iPhone · iOS 17.5 · Safari"
    )
    assert build_device_label(parse_user_agent(ANDROID_CHROME_UA)) == (
        "Android 14 · Chrome"
    )


def test_describe_session_device_handles_legacy_ua():
    assert describe_session_device(IPHONE_UA, IPHONE_UA) == (
        "iPhone · iOS 17.5 · Safari"
    )
    assert describe_session_device("MacBook Pro · macOS 14.5", "") == (
        "MacBook Pro · macOS 14.5"
    )
    assert describe_session_device("", "") == "未知设备"


def test_login_stores_device_label_from_client_hints(
    client, db_session, captured_email
) -> None:
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "a@example.com",
            "password": "password123",
            "nickname": "Alice",
        },
    )
    code = captured_email.messages[-1][2]
    client.post(
        "/api/v1/auth/email/verify",
        json={"email": "a@example.com", "code": code},
    )
    client.post(
        "/api/v1/auth/login",
        json={"email": "a@example.com", "password": "password123"},
        headers={
            "sec-ch-ua-model": '"MacBook Pro"',
            "sec-ch-ua-platform": '"macOS"',
            "sec-ch-ua-platform-version": '"14.5"',
            "sec-ch-ua-mobile": "?0",
        },
    )

    session = db_session.scalar(select(SessionModel))
    assert session is not None
    assert session.device_name == "MacBook Pro · macOS 14.5"
