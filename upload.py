"""이미지 업로드 공통 헬퍼.

- 이미지: 파이썬에서 직접 GCS 로 업로드 (백엔드 우회 → nginx 크기 제한/JWT/서버 부하 없음).
  백엔드 sharp 파이프라인을 Pillow 로 재현 (EXIF 회전, 최대 1600px, webp q80).

- JWT 헬퍼 (make_master_token / auth_headers): 다른 백엔드 API 호출용으로 유지.
  현재는 이미지 업로드가 GCS 직접이라 auth_headers 는 여기서 안 씀.

cafe_scrap.py, it_blog.py 등에서 공유.
"""
import io
import os
import time
import json
import uuid
import hmac
import hashlib
import base64
import requests
from datetime import datetime
from dotenv import load_dotenv
from google.cloud import storage
from PIL import Image, ImageOps

load_dotenv()

# ─── zzikko 백엔드(옵션) ─────────────────────────────────────
# 여러 사이트를 한 파이썬 환경에서 다룰 가능성 대비, ZK_ prefix 로 zzikko 값들을 구분.
# 이미지 업로드 외 API 호출(blog-jobs 큐 등) 은 여전히 여기 사용.
BACKEND_BASE = os.getenv("ZK_BACK_API", "http://localhost:3041")
JWT_SECRET = os.getenv("ZK_JWT_SECRET", "dev-secret-change-me")
ZK_MASTER_USER_ID = int(os.getenv("ZK_MASTER_USER_ID", "13"))
MASTER_ROLE = "ADMIN"

# ─── GCS 직접 업로드 설정 ─────────────────────────────────────
# .env 필수: ZK_GCS_BUCKET, GCS_KEY_FILE (서비스 계정 JSON 경로)
GCS_BUCKET = os.getenv("ZK_GCS_BUCKET", "")
GCS_KEY_FILE = os.getenv("GCS_KEY_FILE", "./community-gcs-key.json")
# 폴더 prefix 는 이제 백엔드가 /due 응답의 job.board_slug 로 알려준다.
# 혹시 호출부에서 지정 안 하면 이 값으로 폴백.
DEFAULT_DEST_PREFIX = "blog"

# Pillow 이미지 처리 파라미터 (백엔드 sharp 와 동일)
MAX_DIMENSION = 1600
WEBP_QUALITY = 80


# ─── JWT 헬퍼 ────────────────────────────────────────────────
def _b64url(data: bytes) -> bytes:
    return base64.urlsafe_b64encode(data).rstrip(b'=')


def make_master_token() -> str:
    """zk-back JWT_SECRET 로 마스터(user 13) access 토큰을 직접 서명해서 반환."""
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload = {"sub": ZK_MASTER_USER_ID, "role": MASTER_ROLE, "type": "access",
               "iat": now, "exp": now + 3600}
    seg = (_b64url(json.dumps(header, separators=(',', ':')).encode()) + b'.' +
           _b64url(json.dumps(payload, separators=(',', ':')).encode()))
    sig = hmac.new(JWT_SECRET.encode(), seg, hashlib.sha256).digest()
    return (seg + b'.' + _b64url(sig)).decode()


_master_token = None


def auth_headers() -> dict:
    """매 호출마다 토큰 재사용 (만료 1h). 백엔드 API 호출용."""
    global _master_token
    if _master_token is None:
        _master_token = make_master_token()
    return {"Authorization": f"Bearer {_master_token}"}


# ─── 이미지 다운로드/처리/업로드 ─────────────────────────────
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


def _process_image(raw: bytes) -> bytes:
    """EXIF 회전 → 최대 1600px 안에서 축소 → webp q80.
    백엔드 gcs.ts 의 sharp 파이프라인과 동일한 결과.
    """
    img = Image.open(io.BytesIO(raw))
    # EXIF 회전 보정 (사진의 orientation 태그 반영)
    img = ImageOps.exif_transpose(img)
    # webp 저장에 필요한 안전 모드로 변환
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    # sharp 의 fit:'inside' withoutEnlargement 와 동일 — 원본이 작으면 그대로
    img.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    img.save(out, format="WEBP", quality=WEBP_QUALITY, method=4)
    return out.getvalue()


# ─── GCS 클라이언트 (모듈 전역 lazy 초기화) ──────────────────
_gcs_bucket = None


def _get_bucket():
    global _gcs_bucket
    if _gcs_bucket is not None:
        return _gcs_bucket
    if not GCS_BUCKET:
        raise RuntimeError("GCS_BUCKET 이 설정되지 않았습니다. (.env 확인)")
    if not os.path.exists(GCS_KEY_FILE):
        raise RuntimeError(f"GCS 서비스 계정 키 파일이 없습니다: {GCS_KEY_FILE}")
    client = storage.Client.from_service_account_json(GCS_KEY_FILE)
    _gcs_bucket = client.bucket(GCS_BUCKET)
    return _gcs_bucket


def _gcs_key(dest_prefix: str, ext: str = "webp") -> str:
    """{prefix}/YYYY/MM/DD/{uuid}.{ext}"""
    prefix = (dest_prefix or DEFAULT_DEST_PREFIX).strip("/")
    d = datetime.now()
    return f"{prefix}/{d.year:04d}/{d.month:02d}/{d.day:02d}/{uuid.uuid4().hex}.{ext}"


def upload_image_to_gcs(content: bytes, filename: str, content_type: str,
                        dest_prefix: str | None = None) -> str | None:
    """이미지 바이트 → 리사이즈/webp → GCS 직접 업로드 → 공개 URL 반환.

    Args:
        dest_prefix: 저장 폴더 prefix (게시판 slug). 미지정 시 DEFAULT_DEST_PREFIX.
                     보통 백엔드 /due 응답의 job['board_slug'] 를 그대로 넘긴다.

    filename 인자는 뒤 호환용 — 실제 GCS 키는 uuid 기반으로 새로 생성한다.
    """
    try:
        processed = _process_image(content)
    except Exception as e:
        print(f"    이미지 처리 실패: {e}")
        return None
    try:
        bucket = _get_bucket()
        key = _gcs_key(dest_prefix or DEFAULT_DEST_PREFIX, "webp")
        blob = bucket.blob(key)
        blob.cache_control = "public, max-age=31536000, immutable"
        blob.upload_from_string(processed, content_type="image/webp")
        return f"https://storage.googleapis.com/{GCS_BUCKET}/{key}"
    except Exception as e:
        print(f"    GCS 업로드 실패: {e}")
        return None


def upload_image_url_to_gcs(src_url: str, filename: str,
                            referer: str | None = None,
                            dest_prefix: str | None = None) -> str | None:
    """src_url 다운로드 → 리사이즈/webp → GCS 직접 업로드. 성공 시 공개 URL.

    Args:
        dest_prefix: 저장 폴더 prefix (게시판 slug). 미지정 시 DEFAULT_DEST_PREFIX.
    """
    dl = download_image(src_url, referer=referer)
    if not dl:
        return None
    content, ct = dl
    return upload_image_to_gcs(content, filename, ct, dest_prefix=dest_prefix)
