"""All 49 bingo tile definitions for the Iron Foundry 7×7 board.

Tile coordinates use (row, col) with (1,1) at the top-left and (7,7) at the
bottom-right, matching the layout in common/tiles.py.
"""

from __future__ import annotations

from pydantic import BaseModel


class PoolRequirement(BaseModel):
    """A single pool-count constraint within a completion path.

    Attributes:
        label: Display name shown in /bingo progress (e.g. "Any ToB Weapon").
        eligible_items: Items that count toward this pool.
            Empty list means any submitted item counts.
        required_total: Number of qualifying submissions needed.
        unique_labels: If True, each distinct item_label counts at most once.
        item_weights: Per-item integer weights enabling value-weighted mode.
            When non-empty, the weighted sum of submitted items is compared
            against required_value instead of using the count-based fields.
        required_value: Target weighted sum (used only when item_weights set).
    """

    label: str
    eligible_items: list[str] = []
    required_total: int = 1
    unique_labels: bool = False
    item_weights: dict[str, int] = {}
    required_value: int = 0
    per_item_max: dict[str, int] = {}
    # Per-item approval cap: {item_label: max_approved_count}.
    # approve() will reject approval once this count is reached for the team+tile.


class CompletionPath(BaseModel):
    """A single way a tile can be completed.

    A tile is complete when **any one** path has all its requirements satisfied.
    Within a path, ALL constraints (requirements dict + every pool_requirement) must hold.

    Attributes:
        label: Human-readable name for this path.
        requirements: Named item requirements — {item_label: count_needed}.
        pool_requirements: Pool-count constraints — all must be satisfied (AND semantics).
    """

    label: str
    requirements: dict[str, int] = {}
    pool_requirements: list[PoolRequirement] = []


class TileDefinition(BaseModel):
    """Full specification for a single bingo tile.

    Attributes:
        row: Board row (1–7).
        col: Board column (1–7).
        description: Tile text from common/tiles.py.
        completion_paths: All possible ways to complete the tile.
        item_choices: Allowed values for TileSubmission.item_label (dropdown).
        is_team_wide: If True, every team member must have ≥1 approved sub.
        host_notes: Optional guidance for hosts reviewing submissions.
    """

    row: int
    col: int
    description: str
    completion_paths: list[CompletionPath]
    item_choices: list[str]
    is_team_wide: bool = False
    host_notes: str = ""


def tile_key(row: int, col: int) -> str:
    """Return the canonical string key for a tile, e.g. '3,4'."""
    return f"{row},{col}"


# ------------------------------------------------------------------
# Column 1
# ------------------------------------------------------------------

_1_1 = TileDefinition(
    row=1,
    col=1,
    description="obtain any 5 soulflame or oathplate drops",
    completion_paths=[
        CompletionPath(
            label="5 Soulflame/Oathplate Drops",
            pool_requirements=[
                PoolRequirement(
                    label="5 Soulflame/Oathplate Drops",
                    eligible_items=[
                        "Oathplate Helm",
                        "Oathplate Body",
                        "Oathplate Legs",
                        "Soulflame Horn",
                    ],
                    required_total=5,
                ),
            ],
        ),
    ],
    item_choices=[
        "Oathplate Helm",
        "Oathplate Body",
        "Oathplate Legs",
        "Soulflame Horn",
    ],
)

_2_1 = TileDefinition(
    row=2,
    col=1,
    description="complete 400 tempoross kc",
    completion_paths=[
        CompletionPath(
            label="400 Tempoross KC",
            pool_requirements=[
                PoolRequirement(label="400 Tempoross KC", required_total=1)
            ],
        ),
    ],
    item_choices=["400 Tempoross KC Screenshot"],
    host_notes="Submit a screenshot of Wise Old Man showing your team with 400+ KC",
)

_3_1 = TileDefinition(
    row=3,
    col=1,
    description="obtain a full set of dark mystic robes",
    completion_paths=[
        CompletionPath(
            label="Full Dark Mystic Set",
            requirements={
                "Dark Mystic Hat": 1,
                "Dark Mystic Top": 1,
                "Dark Mystic Bottom": 1,
                "Dark Mystic Gloves": 1,
                "Dark Mystic Boots": 1,
            },
        ),
    ],
    item_choices=[
        "Dark Mystic Hat",
        "Dark Mystic Top",
        "Dark Mystic Bottom",
        "Dark Mystic Gloves",
        "Dark Mystic Boots",
    ],
)

_4_1 = TileDefinition(
    row=4,
    col=1,
    description="obtain burning claws or 2 tormented synapses",
    completion_paths=[
        CompletionPath(label="Burning Claws", requirements={"Burning Claws": 1}),
        CompletionPath(
            label="2 Tormented Synapses", requirements={"Tormented Synapse": 2}
        ),
    ],
    item_choices=["Burning Claws", "Tormented Synapse"],
)

_5_1 = TileDefinition(
    row=5,
    col=1,
    description="obtain a dragon hunter wand and 10 hueycoatl hides",
    completion_paths=[
        CompletionPath(
            label="DHW + 10 Hides",
            requirements={"Dragon Hunter Wand": 1, "Hueycoatl Hide": 4},
        ),
    ],
    item_choices=["Dragon Hunter Wand", "Hueycoatl Hide"],
    host_notes="10 hides being 4 sets of 3.",
)

_6_1 = TileDefinition(
    row=6,
    col=1,
    description="obtain all vale totems collection logs",
    completion_paths=[
        CompletionPath(
            label="All Vale Totems CLItems",
            requirements={
                "Greenman Mask": 1,
                "Fletching Knife": 1,
                "Bowstring Spool": 1,
            },
        ),
    ],
    item_choices=["Greenman Mask", "Fletching Knife", "Bowstring Spool"],
    host_notes="Submit each of the 3 items obtained from the Vale Totems minigame.",
)

_7_1 = TileDefinition(
    row=7,
    col=1,
    description="obtain any 2 uniques from cerberus",
    completion_paths=[
        CompletionPath(
            label="2 Cerberus Uniques",
            pool_requirements=[
                PoolRequirement(label="2 Cerberus Uniques", required_total=2)
            ],
        ),
    ],
    item_choices=[
        "Primordial Crystal",
        "Pegasian Crystal",
        "Eternal Crystal",
        "Smouldering Stone",
        "Jar of Souls",
        "Hellpuppy",
    ],
)

# ------------------------------------------------------------------
# Column 2
# ------------------------------------------------------------------

_1_2 = TileDefinition(
    row=1,
    col=2,
    description="obtain a dragon axe and a dragon harpoon",
    completion_paths=[
        CompletionPath(
            label="Dragon Axe + Dragon Harpoon",
            requirements={"Dragon Axe": 1, "Dragon Harpoon": 1},
        ),
    ],
    item_choices=["Dragon Axe", "Dragon Harpoon"],
)

_2_2 = TileDefinition(
    row=2,
    col=2,
    description="obtain any unique from nex",
    completion_paths=[
        CompletionPath(
            label="Nex Unique",
            pool_requirements=[PoolRequirement(label="Nex Unique", required_total=1)],
        ),
    ],
    item_choices=[
        "Torva Full Helm",
        "Torva Platebody",
        "Torva Platelegs",
        "Nihil Horn",
        "Zaryte Bow",
        "Ancient Hilt",
        "Nexling",
    ],
)

_3_2 = TileDefinition(
    row=3,
    col=2,
    description="obtain any 3 uniques from nightmare or phosani's",
    completion_paths=[
        CompletionPath(
            label="3 Nightmare/Phosani's Uniques",
            pool_requirements=[
                PoolRequirement(
                    label="3 Nightmare/Phosani's Uniques", required_total=3
                ),
            ],
        ),
    ],
    item_choices=[
        "Nightmare Staff",
        "Inquisitor's Great Helm",
        "Inquisitor's Hauberk",
        "Inquisitor's Plateskirt",
        "Inquisitor's Mace",
        "Eldritch Orb",
        "Volatile Orb",
        "Harmonious Orb",
        "Little Nightmare",
        "Parasitic Egg",
    ],
)

_4_2 = TileDefinition(
    row=4,
    col=2,
    description="obtain 15 spines from scurrius",
    completion_paths=[
        CompletionPath(label="15 Scurrius Spines", requirements={"Scurrius Spine": 15}),
    ],
    item_choices=["Scurrius Spine"],
)

_5_2 = TileDefinition(
    row=5,
    col=2,
    description="obtain a pair of ranger boots",
    completion_paths=[
        CompletionPath(label="Ranger Boots", requirements={"Ranger Boots": 1}),
    ],
    item_choices=["Ranger Boots"],
)

_6_2 = TileDefinition(
    row=6,
    col=2,
    description="obtain any mega rare from a raid",
    completion_paths=[
        CompletionPath(
            label="Raid Mega Rare",
            pool_requirements=[
                PoolRequirement(label="Raid Mega Rare", required_total=1)
            ],
        ),
    ],
    item_choices=[
        "Twisted Bow",
        "Scythe of Vitur",
        "Tumeken's Shadow",
        "Elder Maul",
        "Kodai Wand",
    ],
    host_notes="Mega rares are Twisted Bow, Scythe of Vitur, Tumekens Shadow, Elder Maul and Kodai Wand",
)

_7_2 = TileDefinition(
    row=7,
    col=2,
    description="obtain a broken dragon hook",
    completion_paths=[
        CompletionPath(
            label="Broken Dragon Hook", requirements={"Broken Dragon Hook": 1}
        ),
    ],
    item_choices=["Broken Dragon Hook"],
)

# ------------------------------------------------------------------
# Column 3
# ------------------------------------------------------------------

_1_3 = TileDefinition(
    row=1,
    col=3,
    description="complete a full venator bow",
    completion_paths=[
        CompletionPath(label="Venator Bow", requirements={"Venator Shard": 5}),
    ],
    item_choices=["Venator Shard"],
)

_2_3 = TileDefinition(
    row=2,
    col=3,
    description="obtain any 2 uniques from zalcano",
    completion_paths=[
        CompletionPath(
            label="2 Zalcano Uniques",
            pool_requirements=[
                PoolRequirement(label="2 Zalcano Uniques", required_total=2)
            ],
        ),
    ],
    item_choices=["Smolcano", "Zalcano Shard", "Onyx", "Crystal Tool Seed"],
)

_3_3 = TileDefinition(
    row=3,
    col=3,
    description="gain 10m experience in a non-combat skill",
    completion_paths=[
        CompletionPath(
            label="10m Non-Combat XP",
            pool_requirements=[
                PoolRequirement(label="10m Non-Combat XP", required_total=1)
            ],
        ),
    ],
    item_choices=["10m XP Proof Screenshot"],
    host_notes="Submit a before/after screenshot or XP tracker showing 10m+ XP gained in one non-combat skill during the event.",
)

_4_3 = TileDefinition(
    row=4,
    col=3,
    description="obtain an eternal gem or an imbued heart",
    completion_paths=[
        CompletionPath(label="Eternal Gem", requirements={"Eternal Gem": 1}),
        CompletionPath(label="Imbued Heart", requirements={"Imbued Heart": 1}),
    ],
    item_choices=["Eternal Gem", "Imbued Heart"],
)

_5_3 = TileDefinition(
    row=5,
    col=3,
    description="obtain the berserker, archer, and seers rings",
    completion_paths=[
        CompletionPath(
            label="All 3 Dagannoth Rings",
            requirements={"Berserker Ring": 1, "Archers Ring": 1, "Seers Ring": 1},
        ),
    ],
    item_choices=["Berserker Ring", "Archers Ring", "Seers Ring"],
)

_6_3 = TileDefinition(
    row=6,
    col=3,
    description="obtain a teleport anchoring scroll",
    completion_paths=[
        CompletionPath(
            label="Teleport Anchoring Scroll",
            requirements={"Teleport Anchoring Scroll": 1},
        ),
    ],
    item_choices=["Teleport Anchoring Scroll"],
)

_7_3 = TileDefinition(
    row=7,
    col=3,
    description="obtain 6 crystal armor seeds or 1 enhanced seed",
    completion_paths=[
        CompletionPath(
            label="6 Crystal Armour Seeds",
            pool_requirements=[
                PoolRequirement(
                    label="6 Crystal Armour Seeds",
                    eligible_items=["Crystal Armour Seed"],
                    required_total=6,
                ),
            ],
        ),
        CompletionPath(
            label="Enhanced Crystal Weapon Seed",
            requirements={"Enhanced Crystal Weapon Seed": 1},
        ),
    ],
    item_choices=["Crystal Armour Seed", "Enhanced Crystal Weapon Seed"],
)

# ------------------------------------------------------------------
# Column 4
# ------------------------------------------------------------------

_1_4 = TileDefinition(
    row=1,
    col=4,
    description="obtain any rev weapon or 10m in emblems",
    completion_paths=[
        CompletionPath(
            label="Any Rev Weapon",
            pool_requirements=[
                PoolRequirement(
                    label="Any Rev Weapon",
                    eligible_items=[
                        "Craw's Bow",
                        "Thammaron's Sceptre",
                        "Viggora's Chainmace",
                    ],
                    required_total=1,
                ),
            ],
        ),
        CompletionPath(
            label="10m GP in Artefacts",
            pool_requirements=[
                PoolRequirement(
                    label="Artefact Value (×500k GP)",
                    item_weights={
                        "Ancient Emblem": 1,  # 500k GP
                        "Ancient Totem": 2,  # 1m GP
                        "Ancient Statuette": 4,  # 2m GP
                        "Ancient Medallion": 8,  # 4m GP
                        "Ancient Effigy": 16,  # 8m GP
                        "Ancient Relic": 32,  # 16m GP
                    },
                    required_value=20,  # 20 × 500k = 10m GP
                ),
            ],
        ),
    ],
    item_choices=[
        "Craw's Bow",
        "Thammaron's Sceptre",
        "Viggora's Chainmace",
        "Webweaver Bow",
        "Accursed Sceptre",
        "Ursine Chainmace",
        "Ancient Emblem",
        "Ancient Totem",
        "Ancient Statuette",
        "Ancient Medallion",
        "Ancient Effigy",
        "Ancient Relic",
    ],
    host_notes="Rev weapon path: Craw's Bow, Thammaron's Sceptre, or Viggora's Chainmace. Artefacts path: submit each artefact individually — any mix totalling 10m GP counts (Emblem=500k, Totem=1m, Statuette=2m, Medallion=4m, Effigy=8m, Relic=16m).",
)

_2_4 = TileDefinition(
    row=2,
    col=4,
    description="obtain all 3 sets of perilous moons gear",
    completion_paths=[
        CompletionPath(
            label="All 3 Perilous Moons Sets",
            requirements={
                "Blood Moon Helm": 1,
                "Blood Moon Chestplate": 1,
                "Blood Moon Tassets": 1,
                "Dual Macuahuitl": 1,
                "Blue Moon Helm": 1,
                "Blue Moon Chestplate": 1,
                "Blue Moon Tassets": 1,
                "Blue Moon Spear": 1,
                "Eclipse Moon Helm": 1,
                "Eclipse Moon Chestplate": 1,
                "Eclipse Moon Tassets": 1,
                "Eclipse Atlatl": 1,
            },
        ),
    ],
    item_choices=[
        "Blood Moon Helm",
        "Blood Moon Chestplate",
        "Blood Moon Tassets",
        "Dual macuahuitl",
        "Blue Moon Helm",
        "Blue Moon Chestplate",
        "Blue Moon Tassets",
        "Blue Moon Spear",
        "Eclipse Moon Helm",
        "Eclipse Moon Chestplate",
        "Eclipse Moon Tassets",
        "Eclipse Atlatl",
    ],
)

_3_4 = TileDefinition(
    row=3,
    col=4,
    description="obtain 2 bloodshards",
    completion_paths=[
        CompletionPath(label="2 Bloodshards", requirements={"Bloodshard": 2}),
    ],
    item_choices=["Bloodshard"],
)

_4_4 = TileDefinition(
    row=4,
    col=4,
    description="all team members submit a correct submission screenshot",
    completion_paths=[],
    item_choices=["Submission Screenshot"],
    is_team_wide=True,
    host_notes="Every team member must have at least one approved submission for this tile.",
)

_5_4 = TileDefinition(
    row=5,
    col=4,
    description="obtain an eye of ayak and a mokhaiotl cloth or avernic treads",
    completion_paths=[
        CompletionPath(
            label="Eye of Ayak + Cloth/Treads",
            pool_requirements=[
                PoolRequirement(
                    label="Eye of Ayak",
                    eligible_items=["Eye of Ayak"],
                    required_total=1,
                ),
                PoolRequirement(
                    label="Mokhaiotl Cloth or Avernic Treads",
                    eligible_items=["Mokhaiotl Cloth", "Avernic Treads"],
                    required_total=1,
                ),
            ],
        ),
    ],
    item_choices=["Eye of Ayak", "Mokhaiotl Cloth", "Avernic Treads"],
)

_6_4 = TileDefinition(
    row=6,
    col=4,
    description="obtain any 2 abyssal dyes or abyssal protector",
    completion_paths=[
        CompletionPath(
            label="2 Abyssal Dyes",
            pool_requirements=[
                PoolRequirement(
                    label="2 Abyssal Dyes",
                    eligible_items=[
                        "Abyssal Red Dye",
                        "Abyssal Green Dye",
                        "Abyssal Blue Dye",
                    ],
                    required_total=2,
                ),
            ],
        ),
        CompletionPath(
            label="Abyssal Protector",
            requirements={"Abyssal Protector": 1},
        ),
    ],
    item_choices=[
        "Abyssal Red Dye",
        "Abyssal Green Dye",
        "Abyssal Blue Dye",
        "Abyssal Protector",
    ],
)

_7_4 = TileDefinition(
    row=7,
    col=4,
    description="obtain a fang, lightbearer, or any masori piece",
    completion_paths=[
        CompletionPath(label="Osmumten's Fang", requirements={"Osmumten's Fang": 1}),
        CompletionPath(label="Lightbearer", requirements={"Lightbearer": 1}),
        CompletionPath(
            label="Any Masori Piece",
            pool_requirements=[
                PoolRequirement(
                    label="Any Masori Piece",
                    eligible_items=[
                        "Masori Mask",
                        "Masori Body",
                        "Masori Chaps",
                    ],
                    required_total=1,
                ),
            ],
        ),
    ],
    item_choices=[
        "Osmumten's Fang",
        "Lightbearer",
        "Masori Mask",
        "Masori Body",
        "Masori Chaps",
    ],
)

# ------------------------------------------------------------------
# Column 5
# ------------------------------------------------------------------

_1_5 = TileDefinition(
    row=1,
    col=5,
    description="obtain any 5 different pets",
    completion_paths=[
        CompletionPath(
            label="5 Different Pets",
            pool_requirements=[
                PoolRequirement(
                    label="5 Different Pets",
                    required_total=5,
                    unique_labels=True,
                ),
            ],
        ),
    ],
    item_choices=[
        # Boss pets
        "Abyssal Orphan",
        "Baby Mole",
        "Callisto Cub",
        "Chompy Chick",
        "Hellpuppy",
        "Herbi",
        "Ikkle Hydra",
        "Jal-Nib-Rek",
        "Kalphite Princess",
        "Lil' Creator",
        "Lil' Viathan",
        "Lil' Zik",
        "Little Nightmare",
        "Muphin",
        "Nexling",
        "Noon",
        "Olmlet",
        "Pet Chaos Elemental",
        "Pet Dark Core",
        "Pet Dagannoth Prime",
        "Pet Dagannoth Rex",
        "Pet Dagannoth Supreme",
        "Pet General Graardor",
        "Pet K'ril Tsutsaroth",
        "Pet Kraken",
        "Pet Kree'arra",
        "Pet Penance Queen",
        "Pet Smoke Devil",
        "Pet Snakeling",
        "Pet Zilyana",
        "Prince Black Dragon",
        "Scorpia's Offspring",
        "Skotos",
        "Smol Heredit",
        "Smolcano",
        "Sraracha",
        "Tiny Tempor",
        "Tumeken's Guardian",
        "Tzrek-Jad",
        "Venenatis Spiderling",
        "Vet'ion Jr.",
        "Vorki",
        "Wisp",
        "Youngllef",
        # Skilling pets
        "Baby Chinchompa",
        "Beaver",
        "Bloodhound",
        "Giant Squirrel",
        "Heron",
        "Phoenix",
        "Rift Guardian",
        "Rock Golem",
        "Rocky",
        "Tangleroot",
        # Newer pets
        "Baron",
        "Beef",
        "Bran",
        "Butch",
        "Dom",
        "Gull",
        "Huberte",
        "Moxi",
        "Nid",
        "Quetzin",
        "Scurry",
        "Soup",
        "Yami",
        "Other Pet",
    ],
    host_notes="Each of the 5 pets must be a different pet. Select 'Other Pet' for pets not in the list and note the name.",
)

_2_5 = TileDefinition(
    row=2,
    col=5,
    description="obtain any justiciar piece, avernic defender and any tob weapon",
    completion_paths=[
        CompletionPath(
            label="Justiciar + Avernic + ToB Weapon",
            requirements={"Avernic Defender Hilt": 1},
            pool_requirements=[
                PoolRequirement(
                    label="Any Justiciar Piece",
                    eligible_items=[
                        "Justiciar Faceguard",
                        "Justiciar Chestguard",
                        "Justiciar Legguards",
                    ],
                    required_total=1,
                ),
                PoolRequirement(
                    label="Any ToB Weapon",
                    eligible_items=[
                        "Ghrazi Rapier",
                        "Sanguinesti Staff",
                        "Scythe of Vitur",
                    ],
                    required_total=1,
                ),
            ],
        ),
    ],
    item_choices=[
        "Justiciar Faceguard",
        "Justiciar Chestguard",
        "Justiciar Legguards",
        "Avernic Defender Hilt",
        "Ghrazi Rapier",
        "Sanguinesti Staff",
        "Scythe of Vitur",
    ],
)

_3_5 = TileDefinition(
    row=3,
    col=5,
    description="obtain a pharaoh's sceptre",
    completion_paths=[
        CompletionPath(
            label="Pharaoh's Sceptre", requirements={"Pharaoh's Sceptre": 1}
        ),
    ],
    item_choices=["Pharaoh's Sceptre"],
)

_4_5 = TileDefinition(
    row=4,
    col=5,
    description="complete 400 guardians of the rift kc",
    completion_paths=[
        CompletionPath(
            label="400 GOTR KC",
            pool_requirements=[PoolRequirement(label="400 GOTR KC", required_total=1)],
        ),
    ],
    item_choices=["400 GOTR KC Screenshot"],
    host_notes="Submit a screenshot of your Guardians of the Rift completion count at 400+.",
)

_5_5 = TileDefinition(
    row=5,
    col=5,
    description="complete full malediction and odium wards",
    completion_paths=[
        CompletionPath(
            label="Both Wards",
            requirements={
                "Malediction Ward Shard 1": 1,
                "Malediction Ward Shard 2": 1,
                "Malediction Ward Shard 3": 1,
                "Odium Ward Shard 1": 1,
                "Odium Ward Shard 2": 1,
                "Odium Ward Shard 3": 1,
            },
        ),
    ],
    item_choices=[
        "Malediction Ward Shard 1",
        "Malediction Ward Shard 2",
        "Malediction Ward Shard 3",
        "Odium Ward Shard 1",
        "Odium Ward Shard 2",
        "Odium Ward Shard 3",
    ],
)

_6_5 = TileDefinition(
    row=6,
    col=5,
    description="obtain any 6 uniques from royal titans",
    completion_paths=[
        CompletionPath(
            label="6 Royal Titans Uniques",
            pool_requirements=[
                PoolRequirement(
                    label="6 Royal Titans Uniques",
                    required_total=6,
                    per_item_max={"Giantsoul Amulet": 2},
                ),
            ],
        ),
    ],
    item_choices=[
        "Fire Element Staff Crown",
        "Ice Element Staff Crown",
        "Mystic Vigour Prayer Scroll",
        "Deadeye Prayer Scroll",
        "Bran",
        "Giantsoul Amulet",
    ],
    host_notes="Submit any unique drops from the Royal Titans boss. 6 drops required.",
)

_7_5 = TileDefinition(
    row=7,
    col=5,
    description="obtain holy footwear and mole slippers",
    completion_paths=[
        CompletionPath(
            label="Holy Sandals + Mole Slippers",
            requirements={"Holy Sandals": 1, "Mole Slippers": 1},
        ),
    ],
    item_choices=["Holy Sandals", "Mole Slippers"],
)

# ------------------------------------------------------------------
# Column 6
# ------------------------------------------------------------------

_1_6 = TileDefinition(
    row=1,
    col=6,
    description="obtain all uniques from brutus",
    completion_paths=[
        CompletionPath(
            label="All Brutus Uniques",
            requirements={"Mooleta": 1, "Bottomless Milk Bucket": 1, "Cow slippers": 1},
        ),
    ],
    item_choices=["Mooleta", "Bottomless Milk Bucket", "Cow slippers"],
)

_2_6 = TileDefinition(
    row=2,
    col=6,
    description="obtain any elemental tome",
    completion_paths=[
        CompletionPath(
            label="Any Elemental Tome",
            pool_requirements=[
                PoolRequirement(
                    label="Any Elemental Tome",
                    eligible_items=["Tome of Fire", "Tome of Water", "Tome of Earth"],
                    required_total=1,
                ),
            ],
        ),
    ],
    item_choices=["Tome of Fire", "Tome of Water", "Tome of Earth"],
)

_3_6 = TileDefinition(
    row=3,
    col=6,
    description="obtain a metamorphic dust or 2 ancestral kits",
    completion_paths=[
        CompletionPath(label="Metamorphic Dust", requirements={"Metamorphic Dust": 1}),
        CompletionPath(
            label="2 Ancestral Kits", requirements={"Ancestral Colouring Kit": 2}
        ),
    ],
    item_choices=["Metamorphic Dust", "Ancestral Kit"],
)

_4_6 = TileDefinition(
    row=4,
    col=6,
    description="complete any full godsword",
    completion_paths=[
        CompletionPath(
            label="Any Full Godsword",
            requirements={
                "Godsword Shard 1": 1,
                "Godsword Shard 2": 1,
                "Godsword Shard 3": 1,
            },
            pool_requirements=[
                PoolRequirement(
                    label="Any Godsword Hilt",
                    eligible_items=[
                        "Armadyl Hilt",
                        "Bandos Hilt",
                        "Saradomin Hilt",
                        "Zamorak Hilt",
                        "Ancient Hilt",
                    ],
                    required_total=1,
                ),
            ],
        ),
    ],
    item_choices=[
        "Godsword Shard 1",
        "Godsword Shard 2",
        "Godsword Shard 3",
        "Armadyl Hilt",
        "Bandos Hilt",
        "Saradomin Hilt",
        "Zamorak Hilt",
        "Ancient Hilt",
    ],
    host_notes="Submit all 3 godsword shards and any one godsword hilt. All 5 hilts (Armadyl, Bandos, Saradomin, Zamorak, Ancient) are valid.",
)

_5_6 = TileDefinition(
    row=5,
    col=6,
    description="obtain bryophyta's staff and obor's club",
    completion_paths=[
        CompletionPath(
            label="Bryophyta's Staff + Obor's Club",
            requirements={"Bryophyta's Staff": 1, "Obor's Club": 1},
        ),
    ],
    item_choices=["Bryophyta's Staff", "Obor's Club"],
)

_6_6 = TileDefinition(
    row=6,
    col=6,
    description="obtain a dragon warhammer",
    completion_paths=[
        CompletionPath(label="Dragon Warhammer", requirements={"Dragon Warhammer": 1}),
    ],
    item_choices=["Dragon Warhammer"],
)

_7_6 = TileDefinition(
    row=7,
    col=6,
    description="obtain sulphur blades, glacial temotli, and antler guard",
    completion_paths=[
        CompletionPath(
            label="Sulphur Blades + Glacial Temotli + Antler Guard",
            requirements={
                "Sulphur Blades": 1,
                "Glacial Temotli": 1,
                "Antler Guard": 1,
            },
        ),
    ],
    item_choices=["Sulphur Blades", "Glacial Temotli", "Antler Guard"],
)

# ------------------------------------------------------------------
# Column 7
# ------------------------------------------------------------------

_1_7 = TileDefinition(
    row=1,
    col=7,
    description="complete a full voidwaker",
    completion_paths=[
        CompletionPath(label="Voidwaker", requirements={"Voidwaker": 1}),
    ],
    item_choices=["Voidwaker Blade", "Voidwaker Gem", "Voidwaker Hilt", "Voidwaker"],
)

_2_7 = TileDefinition(
    row=2,
    col=7,
    description="obtain a dragon 2h, dragon pickaxe, and a dragon chainbody",
    completion_paths=[
        CompletionPath(
            label="D2H + D Pick + D Chain",
            requirements={
                "Dragon 2H Sword": 1,
                "Dragon Pickaxe": 1,
                "Dragon Chainbody": 1,
            },
        ),
    ],
    item_choices=["Dragon 2H Sword", "Dragon Pickaxe", "Dragon Chainbody"],
)

_3_7 = TileDefinition(
    row=3,
    col=7,
    description="obtain any rare deep sea trawling fish",
    completion_paths=[
        CompletionPath(
            label="Rare Trawling Fish",
            pool_requirements=[
                PoolRequirement(label="Rare Trawling Fish", required_total=1)
            ],
        ),
    ],
    item_choices=[
        "Giant blue Krill",
        "Golden Haddock",
        "Orangefin",
        "Huge Halibut",
        "Purplefin",
        "Swift Marlin",
    ],
)

_4_7 = TileDefinition(
    row=4,
    col=7,
    description="gain 10m experience in a non combat skill",
    completion_paths=[
        CompletionPath(
            label="10m Non Combat XP",
            pool_requirements=[
                PoolRequirement(label="10m Non-Combat XP", required_total=1)
            ],
        ),
    ],
    item_choices=["10m XP Proof Screenshot"],
)

_5_7 = TileDefinition(
    row=5,
    col=7,
    description="obtain 4 zenyte shards or complete a full ballista",
    completion_paths=[
        CompletionPath(label="4 Zenyte Shards", requirements={"Zenyte Shard": 4}),
        CompletionPath(
            label="Ballista",
            requirements={
                "Ballista Limbs": 1,
                "Heavy/Light Frame": 1,
                "Ballista Spring": 1,
                "Monkey Tail": 1,
            },
        ),
    ],
    item_choices=[
        "Zenyte Shard",
        "Ballista Limbs",
        "Ballista Spring",
        "Heavy/Light Frame",
        "Monkey Tail",
    ],
    host_notes="For the ballista path, submit each component individually (Ballista Limbs, Frame, Spring, Monkey Tail). Both Light and Heavy Ballista count.",
)

_6_7 = TileDefinition(
    row=6,
    col=7,
    description="obtain any 3 slayer helm recolor drops (excluding hood and ca's)",
    completion_paths=[
        CompletionPath(
            label="3 Slayer Helm Recolors",
            pool_requirements=[
                PoolRequirement(
                    label="3 Slayer Helm Recolors",
                    eligible_items=[
                        "Black Slayer Helmet",
                        "Green Slayer Helmet",
                        "Red Slayer Helmet",
                        "Purple Slayer Helmet",
                        "Turquoise Slayer Helmet",
                        "Hydra Slayer Helmet",
                    ],
                    required_total=3,
                ),
            ],
        ),
    ],
    item_choices=[
        "Black Slayer Helmet",
        "Green Slayer Helmet",
        "Red Slayer Helmet",
        "Purple Slayer Helmet",
        "Turquoise Slayer Helmet",
        "Hydra Slayer Helmet",
    ],
    host_notes="Excludes the slayer hood and combat achievement recolors.",
)

_7_7 = TileDefinition(
    row=7,
    col=7,
    description="complete one full set of barrows gear",
    completion_paths=[
        CompletionPath(
            label="Ahrim's Set",
            requirements={
                "Ahrim's Hood": 1,
                "Ahrim's Robetop": 1,
                "Ahrim's Robeskirt": 1,
                "Ahrim's Staff": 1,
            },
        ),
        CompletionPath(
            label="Dharok's Set",
            requirements={
                "Dharok's Helm": 1,
                "Dharok's Platebody": 1,
                "Dharok's Platelegs": 1,
                "Dharok's Greataxe": 1,
            },
        ),
        CompletionPath(
            label="Guthan's Set",
            requirements={
                "Guthan's Helm": 1,
                "Guthan's Platebody": 1,
                "Guthan's Chainskirt": 1,
                "Guthan's Warspear": 1,
            },
        ),
        CompletionPath(
            label="Karil's Set",
            requirements={
                "Karil's Coif": 1,
                "Karil's Leathertop": 1,
                "Karil's Leatherskirt": 1,
                "Karil's Crossbow": 1,
            },
        ),
        CompletionPath(
            label="Torag's Set",
            requirements={
                "Torag's Helm": 1,
                "Torag's Platebody": 1,
                "Torag's Platelegs": 1,
                "Torag's Hammers": 1,
            },
        ),
        CompletionPath(
            label="Verac's Set",
            requirements={
                "Verac's Helm": 1,
                "Verac's Brassard": 1,
                "Verac's Plateskirt": 1,
                "Verac's Flail": 1,
            },
        ),
    ],
    item_choices=[
        # Ahrim's
        "Ahrim's Hood",
        "Ahrim's Robetop",
        "Ahrim's Robeskirt",
        "Ahrim's Staff",
        # Dharok's
        "Dharok's Helm",
        "Dharok's Platebody",
        "Dharok's Platelegs",
        "Dharok's Greataxe",
        # Guthan's
        "Guthan's Helm",
        "Guthan's Platebody",
        "Guthan's Chainskirt",
        "Guthan's Warspear",
        # Karil's
        "Karil's Coif",
        "Karil's Leathertop",
        "Karil's Leatherskirt",
        "Karil's Crossbow",
        # Torag's
        "Torag's Helm",
        "Torag's Platebody",
        "Torag's Platelegs",
        "Torag's Hammers",
        # Verac's
        "Verac's Helm",
        "Verac's Brassard",
        "Verac's Plateskirt",
        "Verac's Flail",
    ],
    host_notes="Any one of the 6 barrows sets counts. All 4 pieces of a single brother's set must be obtained.",
)

# ------------------------------------------------------------------
# Registry
# ------------------------------------------------------------------

TILE_DEFINITIONS: dict[str, TileDefinition] = {
    tile_key(t.row, t.col): t
    for t in [
        _1_1,
        _2_1,
        _3_1,
        _4_1,
        _5_1,
        _6_1,
        _7_1,
        _1_2,
        _2_2,
        _3_2,
        _4_2,
        _5_2,
        _6_2,
        _7_2,
        _1_3,
        _2_3,
        _3_3,
        _4_3,
        _5_3,
        _6_3,
        _7_3,
        _1_4,
        _2_4,
        _3_4,
        _4_4,
        _5_4,
        _6_4,
        _7_4,
        _1_5,
        _2_5,
        _3_5,
        _4_5,
        _5_5,
        _6_5,
        _7_5,
        _1_6,
        _2_6,
        _3_6,
        _4_6,
        _5_6,
        _6_6,
        _7_6,
        _1_7,
        _2_7,
        _3_7,
        _4_7,
        _5_7,
        _6_7,
        _7_7,
    ]
}


def get_tile_def(key: str) -> TileDefinition | None:
    """Return the TileDefinition for a 'row,col' key, or None if not found."""
    return TILE_DEFINITIONS.get(key)
