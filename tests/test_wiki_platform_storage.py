"""跨运行时 wiki 存储适配测试；只使用内存替身。"""

import json

import pytest

from app.services.android import AndroidWikiStorage
from app.services.cloudflare import DurableWikiStorage


class _Cursor:
    def __init__(self, row=None):
        self.row = row

    def one(self):
        return self.row


class _Sql:
    def __init__(self):
        self.rows = {}

    def exec(self, query, *values):
        if query.startswith("SELECT"):
            return _Cursor(
                {"payload": self.rows[values[0]]} if values[0] in self.rows else None
            )
        if query.startswith("INSERT INTO community_wiki"):
            self.rows[values[0]] = values[1]
        return _Cursor()


class _DurableObjectStorage:
    def __init__(self):
        self.sql = _Sql()
        self.sync_count = 0

    async def sync(self):
        self.sync_count += 1


@pytest.mark.asyncio
async def test_durable_wiki_storage_persists_and_rejects_unsafe_keys():
    durable = _DurableObjectStorage()
    storage = DurableWikiStorage(durable)

    await storage.write("wiki/index.json", '{"schema":20}')

    assert await storage.read("wiki/index.json") == '{"schema":20}'
    assert durable.sync_count == 1
    with pytest.raises(ValueError, match="路径无效"):
        await storage.read("wiki/../state.json")
    with pytest.raises(ValueError, match="超过8MB"):
        await storage.write("wiki/state.json", "x" * (8_000_000 + 1))


@pytest.mark.asyncio
async def test_android_wiki_storage_uses_native_read_write_bridge():
    files = {}
    operations = []

    async def native_call(operation, payload):
        operations.append(operation)
        data = json.loads(payload)
        if operation == "wiki.read":
            return json.dumps({"content": files.get(data["path"])})
        files[data["path"]] = data["content"]
        return json.dumps({"saved": True})

    storage = AndroidWikiStorage(native_call)

    await storage.write("wiki/index.json", '{"schema":20}')

    assert await storage.read("wiki/index.json") == '{"schema":20}'
    assert operations == ["wiki.write", "wiki.read"]
