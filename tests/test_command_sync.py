"""Command sync must keep the Activity's Entry Point command, or Discord refuses it."""

import asyncio
from types import SimpleNamespace

from command_sync import merge_entry_points, sync_commands

ENTRY = {
    "id": "123",
    "application_id": "999",
    "version": "456",
    "name": "launch",
    "description": "",
    "type": 4,
    "handler": 2,
    "integration_types": [0, 1],
    "contexts": [0, 1, 2],
}
SLASH = {"id": "7", "name": "bismillah", "type": 1, "description": "x"}


def test_keeps_the_entry_point_and_drops_read_only_fields():
    body = merge_entry_points([{"name": "bismillah", "type": 1}], [SLASH, ENTRY])
    assert body[0] == {"name": "bismillah", "type": 1}
    assert body[1]["id"] == "123" and body[1]["type"] == 4 and body[1]["handler"] == 2
    assert "application_id" not in body[1] and "version" not in body[1]
    assert len(body) == 2


def test_no_entry_point_means_the_tree_payload_unchanged():
    tree = [{"name": "bismillah", "type": 1}]
    assert merge_entry_points(tree, [SLASH]) == tree


def test_sync_puts_the_merged_body():
    sent = {}

    async def get_global_commands(app_id):
        return [SLASH, ENTRY]

    async def bulk_upsert_global_commands(app_id, payload):
        sent["payload"] = payload
        return payload

    command = SimpleNamespace(to_dict=lambda tree: {"name": "bismillah", "type": 1})
    tree = SimpleNamespace(_get_all_commands=lambda: [command])
    bot = SimpleNamespace(
        tree=tree,
        application_id=999,
        http=SimpleNamespace(
            get_global_commands=get_global_commands,
            bulk_upsert_global_commands=bulk_upsert_global_commands,
        ),
    )
    assert asyncio.run(sync_commands(bot)) == 2
    assert [c["name"] for c in sent["payload"]] == ["bismillah", "launch"]
