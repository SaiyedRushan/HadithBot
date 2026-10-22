"""Sync the slash commands without deleting the Activity's Entry Point command.

Once Activities are turned on for the application, Discord gives it an Entry
Point command (type 4, shown as "Launch" in the App Launcher). Discord refuses
any bulk overwrite of the global commands that leaves it out (error 50240,
"You cannot remove this app's Entry Point command in a bulk update
operation"). discord.py's ``tree.sync()`` is exactly that bulk overwrite, built
only from the commands in the tree, so with Activities on it would fail in
``setup_hook`` and the bot would never start.

This does the same PUT, with any existing Entry Point command carried along.
"""

import logging

ENTRY_POINT_TYPE = 4

# The fields Discord accepts back on a PUT. The GET also returns read-only ones
# (application_id, version, ...) that a PUT should not echo.
_ENTRY_POINT_FIELDS = (
    "id",
    "name",
    "description",
    "type",
    "handler",
    "integration_types",
    "contexts",
    "name_localizations",
    "description_localizations",
    "default_member_permissions",
    "nsfw",
)

logger = logging.getLogger("HadithBot")


def merge_entry_points(tree_payload: list[dict], existing: list[dict]) -> list[dict]:
    """The tree's commands plus every Entry Point command already registered."""
    kept = [
        {k: c[k] for k in _ENTRY_POINT_FIELDS if k in c}
        for c in existing
        if c.get("type") == ENTRY_POINT_TYPE
    ]
    return list(tree_payload) + kept


async def sync_commands(bot) -> int:
    """Replace the global commands with the tree's, keeping the Entry Point.

    Returns how many commands Discord now has registered.
    """
    tree = bot.tree
    payload = [command.to_dict(tree) for command in tree._get_all_commands()]
    existing = await bot.http.get_global_commands(bot.application_id)
    body = merge_entry_points(payload, existing)
    data = await bot.http.bulk_upsert_global_commands(bot.application_id, payload=body)
    if len(body) != len(payload):
        logger.info("Kept the Activity's Entry Point command while syncing")
    return len(data)
