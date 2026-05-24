"""
Fuseki 연결 설정을 런타임에 변경할 수 있는 mutable singleton.

시작값은 config.py (환경변수) 에서 읽고, PATCH /api/config/fuseki 로 갱신한다.
"""

from config import settings

_state: dict[str, str] = {
    "fuseki_base_url":      settings.fuseki_base_url,
    "fuseki_admin_user":    settings.fuseki_admin_user,
    "fuseki_admin_password": settings.fuseki_admin_password,
}


def get() -> dict[str, str]:
    """현재 설정을 복사본으로 반환한다."""
    return dict(_state)


def set(*, url: str, user: str | None = None, password: str | None = None) -> None:
    """설정을 갱신한다. None 값은 기존 값을 유지한다."""
    _state["fuseki_base_url"] = url
    if user is not None:
        _state["fuseki_admin_user"] = user
    if password is not None:
        _state["fuseki_admin_password"] = password


def base_url() -> str:
    return _state["fuseki_base_url"]


def auth() -> tuple[str, str]:
    return _state["fuseki_admin_user"], _state["fuseki_admin_password"]
