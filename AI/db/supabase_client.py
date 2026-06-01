"""
Supabase 클라이언트 싱글톤.

모든 DB 접근은 이 모듈의 get_supabase()를 거쳐야 한다.
직접 create_client() 호출 금지.

service_role 키를 사용하므로 RLS를 우회할 수 있다.
client-side 코드(브라우저·앱)에서는 절대 사용하지 말 것.
"""
from __future__ import annotations

import httpx
from supabase import Client, create_client
from supabase.client import ClientOptions

from config import settings

_client: Client | None = None


def get_supabase() -> Client:
    """Supabase service_role 클라이언트 싱글톤 (HTTP/1.1 강제로 stale connection 방지)."""
    global _client
    if _client is None:
        _client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_KEY,
            options=ClientOptions(
                httpx_client=httpx.Client(http2=False),
            ),
        )
    return _client