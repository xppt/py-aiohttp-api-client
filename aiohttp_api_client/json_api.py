import asyncio
import json
from typing import Any, Dict, Mapping, NamedTuple, NoReturn, Optional

import aiohttp
from aiohttp import ClientError, ClientTimeout
from aiohttp.hdrs import CONTENT_TYPE

JsonValue = Any  # may be possible to fix in future


class JsonApiRequest(NamedTuple):
    method: str
    url: str
    params: Optional[Mapping[str, str]] = None
    json: Optional[JsonValue] = None
    headers: Optional[Mapping[str, str]] = None
    timeout: float = 5.
    raise_for_status: bool = True


class JsonApiDetails(NamedTuple):
    network_error: Optional[str] = None
    errno: Optional[int] = None
    http_status: Optional[int] = None
    http_reason: Optional[str] = None
    content_type: Optional[str] = None
    bytes: Optional[bytes] = None
    text: Optional[str] = None


class JsonApiResult(NamedTuple):
    json: JsonValue
    details: JsonApiDetails


class JsonApiError(Exception):
    def __init__(self, name: str, details: JsonApiDetails):
        self.name = name
        self.details = details


class JsonApiClient:
    def __init__(self, http_client: aiohttp.ClientSession):
        self._http_client = http_client

    async def __call__(self, request: JsonApiRequest) -> JsonApiResult:
        """
        See `call_json_api`.

        :raises JsonApiError
        """

        return await call_json_api(self._http_client, request)


async def call_json_api(
        http_client: aiohttp.ClientSession, request: JsonApiRequest,
) -> JsonApiResult:
    """
    This function will execute http-request and parse json response as far as possible.
    It expects to receive correct Content-Type and forbids redirects.

    :raises JsonApiError
    """

    details: Dict[str, Any] = {}

    try:
        resp = await http_client.request(
            method=request.method,
            url=request.url,
            params=request.params,
            json=request.json,
            headers=request.headers,
            timeout=ClientTimeout(total=request.timeout),
            allow_redirects=False,
        )
    except (ClientError, asyncio.TimeoutError) as e:
        _raise_network_error(details, e)

    # be sure not to leave this function before resp.read() call
    details['http_status'] = resp.status
    details['http_reason'] = resp.reason
    details['content_type'] = resp.headers.get(CONTENT_TYPE)

    try:
        body = await resp.read()
    except (ClientError, asyncio.TimeoutError) as e:
        _raise_network_error(details, e)

    details['bytes'] = body

    if not _is_expected_content_type(details['content_type'] or ''):
        _raise_error('unexpected_content_type', details)

    try:
        # assume it won't raise ClientError-s
        # since whole body was already read
        text = await resp.text()
    except UnicodeDecodeError as e:
        _raise_error('malformed_json', details, e)

    details['text'] = text

    if request.raise_for_status and details['http_status'] >= 400:
        _raise_error('http_error', details)

    try:
        json_value = json.loads(text)
    except json.JSONDecodeError as e:
        _raise_error('malformed_json', details, e)

    return JsonApiResult(
        json=json_value,
        details=JsonApiDetails(**details),
    )


def _raise_error(name: str, details: dict, e: Optional[Exception] = None) -> NoReturn:
    raise JsonApiError(name, JsonApiDetails(**details)) from e


def _raise_network_error(details: dict, e: Exception) -> NoReturn:
    details['network_error'] = type(e).__name__
    if isinstance(e, OSError):
        details['errno'] = e.errno

    _raise_error('network_error', details, e)


def _is_expected_content_type(content_type: str) -> bool:
    # we don't need to parse media type params, so keep it simple
    ctype = content_type.split(';', 1)[0].strip(' \t').lower()
    return ctype == 'application/json'
