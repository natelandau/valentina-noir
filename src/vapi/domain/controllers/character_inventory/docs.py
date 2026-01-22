"""Character inventory endpoint documentation."""

LIST_INVENTORY_ITEMS_DESCRIPTION = """\
Retrieve a paginated list of items in a character's inventory.

Items can include equipment, consumables, weapons, or other possessions tracked for the character.
"""

GET_INVENTORY_ITEM_DESCRIPTION = """\
Retrieve detailed information about a specific inventory item including its type, description, and mechanical properties.
"""

CREATE_INVENTORY_ITEM_DESCRIPTION = """\
Add a new item to a character's inventory.

Specify the item type, name, description, and any mechanical properties such as damage or armor values.

**Note:** Only the character's player or a storyteller can add items.
"""

UPDATE_INVENTORY_ITEM_DESCRIPTION = """\
Modify an inventory item's properties such as name, description, or quantity.

Only include fields that need to be changed; omitted fields remain unchanged.

**Note:** Only the character's player or a storyteller can update items.
"""

DELETE_INVENTORY_ITEM_DESCRIPTION = """\
Remove an item from a character's inventory.

**Note:** Only the character's player or a storyteller can delete items. This action cannot be undone.
"""
