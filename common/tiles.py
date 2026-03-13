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
2, 5 complete a full soulreaper axe
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
Row Y: 203 + (row-1)*131   →  r1=203  r2=334  r3=465  r4=596  r5=727  r6=858  r7=989
Col X: 167 + (col-1)*261   →  c1=167  c2=428  c3=689  c4=950  c5=1211 c6=1472 c7=1733

1, 1 = 203px Y, 167px X
1, 2 = 203px Y, 428px X
1, 3 = 203px Y, 689px X
1, 4 = 203px Y, 950px X
1, 5 = 203px Y, 1211px X
1, 6 = 203px Y, 1472px X
1, 7 = 203px Y, 1733px X

2, 1 = 334px Y, 167px X
2, 2 = 334px Y, 428px X
2, 3 = 334px Y, 689px X
2, 4 = 334px Y, 950px X
2, 5 = 334px Y, 1211px X
2, 6 = 334px Y, 1472px X
2, 7 = 334px Y, 1733px X

3, 1 = 465px Y, 167px X
3, 2 = 465px Y, 428px X
3, 3 = 465px Y, 689px X
3, 4 = 465px Y, 950px X
3, 5 = 465px Y, 1211px X
3, 6 = 465px Y, 1472px X
3, 7 = 465px Y, 1733px X

4, 1 = 596px Y, 167px X
4, 2 = 596px Y, 428px X
4, 3 = 596px Y, 689px X
4, 4 = 596px Y, 950px X
4, 5 = 596px Y, 1211px X
4, 6 = 596px Y, 1472px X
4, 7 = 596px Y, 1733px X

5, 1 = 727px Y, 167px X
5, 2 = 727px Y, 428px X
5, 3 = 727px Y, 689px X
5, 4 = 727px Y, 950px X
5, 5 = 727px Y, 1211px X
5, 6 = 727px Y, 1472px X
5, 7 = 727px Y, 1733px X

6, 1 = 858px Y, 167px X
6, 2 = 858px Y, 428px X
6, 3 = 858px Y, 689px X
6, 4 = 858px Y, 950px X
6, 5 = 858px Y, 1211px X
6, 6 = 858px Y, 1472px X
6, 7 = 858px Y, 1733px X

7, 1 = 989px Y, 167px X
7, 2 = 989px Y, 428px X
7, 3 = 989px Y, 689px X
7, 4 = 989px Y, 950px X
7, 5 = 989px Y, 1211px X
7, 6 = 989px Y, 1472px X
7, 7 = 989px Y, 1733px X
"""

# (row, col) → (y_px, x_px) — derived from the grid formula above
TILE_PIXEL_POSITIONS: dict[tuple[int, int], tuple[int, int]] = {
    (r, c): (203 + (r - 1) * 131, 167 + (c - 1) * 261)
    for r in range(1, 8)
    for c in range(1, 8)
}