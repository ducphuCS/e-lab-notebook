"""Ingredients service — schema definitions.

Source of truth for the v0 ingredient schema
(frontend/ingredients/README.md §5.1, Q1/Q5 resolutions).
"""

# Columns in display order; `custom_fields` is a JSON-encoded mapping.
INGREDIENT_FIELDS = (
    "id",
    "name",
    "item_code",
    "item_description",
    "supplier",
    "notes",
    "uom",
    "state",
    "custom_fields",
)

# Physical states offered by the UI selectbox (README Q5). Owner-extensible.
INGREDIENT_STATES = ("liquid", "solid", "powder", "gas", "paste", "gel")

INGREDIENTS_DDL = """
CREATE TABLE IF NOT EXISTS ingredients (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT NOT NULL,
    item_code        TEXT,
    item_description TEXT,
    supplier         TEXT,
    notes            TEXT,
    uom              TEXT,
    state            TEXT,
    custom_fields    TEXT NOT NULL DEFAULT '{}'
);
"""
