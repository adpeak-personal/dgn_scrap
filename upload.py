"""백엔드 / GCS 업로드 공통 헬퍼.

cafe_scrap.py, it_blog.py 등에서 공유. 토큰은 모듈 전역에서 1회 발급해 재사용.
"""
import time
import json
import hmac
import hashlib
import base64
import requests


BACKEND_BASE = "http://localhost:3041"        # zk-back .env PORT
JWT_SECRET = "dev-secret-change-me"           # zk-back .env JWT_SECRET 와 동일해야 함
MASTER_USER_ID = 13                            # changyong112@naver.com (마스터 고정)
MASTER_ROLE = "ADMIN"


def _b64url(data: bytes) -> bytes:
    return base64.urlsafe_b64encode(data).rstrip(b'=')


def make_master_token() -> str:
    """zk-back JWT_SECRET 로 마스터(user 13) access 토큰을 직접 서명해서 반환.
    (/api/auth/master 로그인과 동일한 Bearer 토큰 — 비밀번호 없이 고정 발급)"""
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload = {"sub": MASTER_USER_ID, "role": MASTER_ROLE, "type": "access",
               "iat": now, "exp": now + 3600}
    seg = (_b64url(json.dumps(header, separators=(',', ':')).encode()) + b'.' +
           _b64url(json.dumps(payload, separators=(',', ':')).encode()))
    sig = hmac.new(JWT_SECRET.encode(), seg, hashlib.sha256).digest()
    return (seg + b'.' + _b64url(sig)).decode()


_master_token = None


def auth_headers() -> dict:
    """매 호출마다 토큰 재사용 (만료 1h)."""
    global _master_token
    if _master_token is None:
        _master_token = make_master_token()
    return {"Authorization": f"Bearer {_master_token}"}


def download_image(url: str, referer: str | None = None):
    """이미지 다운로드. 일부 사이트(네이버 카페 pstatic 등)는 Referer 필요.
    (bytes, content_type) 반환, 실패 시 None."""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        if referer:
            headers["Referer"] = referer
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        ct = r.headers.get("Content-Type", "image/jpeg")
        if not ct.startswith("image/"):
            ct = "image/jpeg"
        return r.content, ct
    except Exception as e:
        print(f"    이미지 다운로드 실패: {e}")
        return None


def upload_image_to_gcs(content: bytes, filename: str, content_type: str):
    """백엔드 /api/upload/image 로 업로드 → GCS tmp URL 반환, 실패 시 None."""
    try:
        files = {"file": (filename, content, content_type)}
        r = requests.post(f"{BACKEND_BASE}/api/upload/image",
                          headers=auth_headers(), files=files, timeout=60)
        r.raise_for_status()
        return r.json().get("url")
    except Exception as e:
        print(f"    이미지 업로드 실패: {e}")
        return None


def upload_image_url_to_gcs(src_url: str, filename: str,
                            referer: str | None = None):
    """src_url 다운로드 → 백엔드 업로드 한 번에 처리. 성공 시 GCS URL, 실패 시 None."""
    dl = download_image(src_url, referer=referer)
    if not dl:
        return None
    content, ct = dl
    return upload_image_to_gcs(content, filename, ct)
