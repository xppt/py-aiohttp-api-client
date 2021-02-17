import json
from typing import Optional
from unittest.mock import Mock

import asynctest
from aiohttp import ClientError, ClientOSError, ClientTimeout
from asynctest import CoroutineMock

from aiohttp_api_client.json_api import (
    JsonApiDetails, JsonApiError, JsonApiRequest, JsonApiResult, call_json_api
)


class JsonApiTestCase(asynctest.TestCase):
    async def test_calling_api(self):
        value = {'key': 1}
        value_text = json.dumps(value)
        value_bytes = value_text.encode()

        self.assertEqual(
            await self._call(value),
            self._make_result(value),
        )

        with self.assertRaises(JsonApiError) as ctx:
            await self._call(value, req_error=ClientError)

        self.assertEqual(
            ctx.exception.details, self._make_details(req_error='ClientError'),
        )

        with self.assertRaises(JsonApiError) as ctx:
            await self._call(value, req_error=ClientOSError(123, 'msg'))

        self.assertEqual(
            ctx.exception.details,
            self._make_details(req_error='ClientOSError', errno=123),
        )

        with self.assertRaises(JsonApiError) as ctx:
            await self._call(value, ctype=None)

        self.assertEqual(
            ctx.exception.details,
            self._make_details(value_bytes, ctype=None),
        )

        with self.assertRaises(JsonApiError) as ctx:
            await self._call(value, ctype='application/xml')

        self.assertEqual(
            ctx.exception.details,
            self._make_details(value_bytes, ctype='application/xml'),
        )

        with self.assertRaises(JsonApiError) as ctx:
            await self._call(value=b'\x80\x80\x80')

        self.assertEqual(
            ctx.exception.details,
            self._make_details(b'\x80\x80\x80'),
        )

        with self.assertRaises(JsonApiError) as ctx:
            await self._call(value, status=400)

        self.assertEqual(
            ctx.exception.details,
            self._make_details(value_text, status=400),
        )

        malformed_json = value_text + '{}'
        with self.assertRaises(JsonApiError) as ctx:
            await self._call(value=malformed_json)

        self.assertEqual(
            ctx.exception.details,
            self._make_details(malformed_json),
        )

    async def _call(
            self, json_value=None, value=None, req_error=None, body_error=None,
            ctype: Optional[str] = 'application/json', status=200, reason='OK',
    ):
        if value is None:
            value = json.dumps(json_value)

        if isinstance(value, str):
            value = value.encode()

        response = Mock()
        response.read = CoroutineMock(side_effect=body_error or [value])
        response.text = CoroutineMock(side_effect=lambda: value.decode())
        response.status = status
        response.reason = reason
        response.headers = {'Content-Type': ctype} if ctype is not None else {}

        http_client = Mock()
        http_client.request = CoroutineMock(side_effect=req_error or [response])

        url = 'https://ya.ru/'

        result = await call_json_api(http_client, JsonApiRequest('GET', url))

        http_client.request.assert_awaited_once_with(
            method='GET', url=url, params=None, json=None, headers=None,
            timeout=ClientTimeout(total=5), allow_redirects=False,
        )

        return result

    def _make_details(
            self, value=None, ctype: Optional[str] = 'application/json', status=200, reason='OK',
            req_error=None, body_error=None, errno=None,
    ):
        if req_error is not None:
            return JsonApiDetails(network_error=req_error, errno=errno)

        details = dict(
            content_type=ctype, http_status=status, http_reason=reason, network_error=body_error,
            errno=errno,
        )

        if isinstance(value, dict):
            value = json.dumps(value)

        if isinstance(value, str):
            details['text'] = value
            value = value.encode()

        if isinstance(value, bytes):
            details['bytes'] = value

        return JsonApiDetails(**details)  # type: ignore

    def _make_result(self, value, **kwargs):
        return JsonApiResult(value, self._make_details(value, **kwargs))
