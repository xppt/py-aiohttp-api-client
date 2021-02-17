aiohttp-api-client
===

Requires: python 3.6+, aiohttp.

Example:
```python
import aiohttp
from aiohttp_api_client.json_api import \
    JsonApiClient, JsonApiRequest, JsonApiError, JsonApiDetails

async def run(http_client: aiohttp.ClientSession):
    api_client = JsonApiClient(http_client)

    response = await api_client(JsonApiRequest('GET', 'https://example.com/api/'))
    assert response.json == {'ok': True}

    try:
        await api_client(JsonApiRequest('GET', 'https://example.com/api/bad-request/'))
    except JsonApiError as e:
        assert e.details == JsonApiDetails(
            http_status=400, http_reason='Bad Request', content_type='application/json',
            bytes=b'{"ok": false}', text='{"ok": false}',
        )
    else:
        assert False
```
