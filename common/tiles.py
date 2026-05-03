tiles: str = """
Coordinates | Rest
ROW | COLUMN | Description


1, 1 obtain any 5 soulflame or oathplate drops
2, 1 complete 400 tempoross kc
3, 1 obtain a full set of dark mystic robes
4, 1 obtain burning claws or 2 tormented synapses
5, 1 obtain a dragon hunter wand and 10 hueycoatl hides
6, 1 obtain all vale totems collection logs
7, 1 obtain any 2 uniques from cerberus

1, 2 obtain a dragon axe and a dragon harpoon
2, 2 obtain any unique from nex
3, 2 obtain any 3 uniques from nightmare or phosani’s
4, 2 obtain 15 spines from scurrius
5, 2 obtain a pair of ranger boots
6, 2 obtain any mega rare from a raid
7, 2 obtain a broken dragon hook

1, 3 complete a full venator bow
2, 3 obtain any 2 uniques from zalcano
3, 3 gain 10m experience in a non-combat skill
4, 3 obtain an eternal gem or an imbued heart
5, 3 obtain the berserker, archer, and seers rings
6, 3 obtain a teleport anchoring scroll
7, 3 obtain 6 crystal armor seeds or 1 enhanced seed

1, 4 obtain any rev weapon or 10m in emblems
2, 4 obtain all 3 sets of perilous moons gear
3, 4 obtain 3 bloodshards
4, 4 all team members submit a correct submission screenshot
5, 4 obtain an eye of ayak and a mokhaiotl cloth or avernic treads
6, 4 obtain any 2 abyssal dyes or abyssal protector
7, 4 obtain a fang, lightbearer, or any masori piece

1, 5 obtain any 5 different pets
2, 5 obtain any justiciar piece, avernic defender and any tob weapon
3, 5 obtain a pharaoh’s sceptre
4, 5 complete 400 guardians of the rift kc
5, 5 complete full malediction and odium wards
6, 5 obtain any 6 uniques from royal titans
7, 5 obtain holy footwear and mole slippers

1, 6 obtain all uniques from brutus
2, 6 obtain any elemental tome
3, 6 obtain a metamorphic dust or 2 ancestral kits
4, 6 complete any full godsword
5, 6 obtain bryophyta's staff and obor's club
6, 6 obtain a dragon warhammer
7, 6 obtain sulphur blades, glacial temotli, and antler guard

1, 7 complete a full voidwaker
2, 7 obtain a dragon 2h, dragon pickaxe, and a dragon chainbody
3, 7 obtain any rare deep sea trawling fish
4, 7 gain 10m experience in a combat skill
5, 7 obtain 4 zenyte shards or complete a full ballista
6, 7 obtain any 3 slayer helm recolor drops (excluding hood and ca’s)
7, 7 complete one full set of barrows gear



"""

frontend_tile_positions_px = """
ROW, COL = Y px, X px
Row Y: 201 + (row-1)*131   →  r1=201  r2=332  r3=463  r4=594  r5=725  r6=856  r7=987
Col X: 163 + (col-1)*(1592/6)  →  c1=163  c2=428  c3=694  c4=959  c5=1224 c6=1490 c7=1755

1, 1 = 201px Y, 163px X
1, 2 = 201px Y, 428px X
1, 3 = 201px Y, 694px X
1, 4 = 201px Y, 959px X
1, 5 = 201px Y, 1224px X
1, 6 = 201px Y, 1490px X
1, 7 = 201px Y, 1755px X

2, 1 = 332px Y, 163px X
2, 2 = 332px Y, 428px X
2, 3 = 332px Y, 694px X
2, 4 = 332px Y, 959px X
2, 5 = 332px Y, 1224px X
2, 6 = 332px Y, 1490px X
2, 7 = 332px Y, 1755px X

3, 1 = 463px Y, 163px X
3, 2 = 463px Y, 428px X
3, 3 = 463px Y, 694px X
3, 4 = 463px Y, 959px X
3, 5 = 463px Y, 1224px X
3, 6 = 463px Y, 1490px X
3, 7 = 463px Y, 1755px X

4, 1 = 594px Y, 163px X
4, 2 = 594px Y, 428px X
4, 3 = 594px Y, 694px X
4, 4 = 594px Y, 959px X
4, 5 = 594px Y, 1224px X
4, 6 = 594px Y, 1490px X
4, 7 = 594px Y, 1755px X

5, 1 = 725px Y, 163px X
5, 2 = 725px Y, 428px X
5, 3 = 725px Y, 694px X
5, 4 = 725px Y, 959px X
5, 5 = 725px Y, 1224px X
5, 6 = 725px Y, 1490px X
5, 7 = 725px Y, 1755px X

6, 1 = 856px Y, 163px X
6, 2 = 856px Y, 428px X
6, 3 = 856px Y, 694px X
6, 4 = 856px Y, 959px X
6, 5 = 856px Y, 1224px X
6, 6 = 856px Y, 1490px X
6, 7 = 856px Y, 1755px X

7, 1 = 987px Y, 163px X
7, 2 = 987px Y, 428px X
7, 3 = 987px Y, 694px X
7, 4 = 987px Y, 959px X
7, 5 = 987px Y, 1224px X
7, 6 = 987px Y, 1490px X
7, 7 = 987px Y, 1755px X
"""

# (row, col) → (y_px, x_px) - derived from the grid formula above
# y step is 131px, x step is 1592/6 ≈ 265.33px (x rounded to nearest int)
TILE_PIXEL_POSITIONS: dict[tuple[int, int], tuple[int, int]] = {
    (r, c): (201 + (r - 1) * 131, round(163 + (c - 1) * (1592 / 6)))
    for r in range(1, 8)
    for c in range(1, 8)
}
