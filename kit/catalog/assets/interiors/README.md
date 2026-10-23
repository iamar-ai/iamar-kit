# City room interiors (kit/catalog/assets/interiors)

The inside fittings of iamar city buildings, one room per building purpose (picked in
`kit/catalog/public_selection.json`): ceiling beams, inner wall frames and wainscot, counters, shelves,
stalls, lamps and inner doorways. The building (its shell) gives the floor, outer walls and roof, so
a room seen alone, as in its thumbnail, is an open frame.

Every room is moved by its shell's offset (`import_city_interiors.py`), the same offset
`import_city_buildings.py` gives the building: place the room at the building's position and
rotation and it fits inside, as in the city. When the shell is in the catalogue the two entries
pair (`pairings`) and each description names the other's id. Otherwise the description gives the
footprint to build around it.

```
copy kit/catalog/assets/interiors/interior_b007.glb to <world folder>/assets/interior_b007.glb, then
scene.json objects: {"asset": "assets/interior_b007.glb", "position": [x, 0, z], "collision": "mesh"}
(and the smithy b007.glb or b007_closed.glb at the same position)
```

The library (`interior_c02.glb`) ships its nine parts (archive, books, balusters, coffers, glass,
light shaft, meeting room, scriptorium, fire glow) in the same file, under the room's root; the inn
(`interior_c03.glb`) its fire glow. Rebuild with
`python3 kit/catalog/assets/import_city_interiors.py <iamar-models checkout>`; `--check` verifies
files, hashes, triangles and the shell offsets.

| File | Room | Triangles | Size (m) | Shell in the catalogue |
|---|---|---|---|---|
| `interior_b001.glb` | warriors' quarter bird supply shop interior | 3134 | 16.31 x 6.36 x 27.47 | `b001.glb` |
| `interior_b007.glb` | warriors' quarter smithy interior | 1301 | 7.16 x 6.35 x 17.11 | `b007.glb` |
| `interior_b012.glb` | mages' quarter rune shop interior | 902 | 7.48 x 6.35 x 13.97 | no (B012) |
| `interior_b021.glb` | warriors' quarter blacksmith forge interior | 964 | 14.85 x 6.35 x 7.16 | `b021.glb` |
| `interior_b034.glb` | mages' quarter curio shop interior | 1325 | 16.31 x 6.57 x 7.97 | no (B034) |
| `interior_b039.glb` | civic heart jousting supply store interior | 3289 | 11.19 x 6.35 x 24.31 | `b039.glb` |
| `interior_b048.glb` | mages' quarter wandmaker interior | 907 | 12.81 x 6.64 x 8.28 | no (B048) |
| `interior_b055.glb` | civic heart healer's shop interior | 689 | 8.34 x 6.35 x 6.28 | `b055.glb` |
| `interior_b058.glb` | city hall interior | 5002 | 27.46 x 9.54 x 11.22 | `b058.glb` |
| `interior_b075.glb` | herbalists' quarter tool shop interior | 3098 | 20.93 x 6.49 x 31.67 | no (B075) |
| `interior_b077.glb` | herbalists' quarter herb shop interior | 656 | 12.15 x 6.35 x 3.25 | no (B077) |
| `interior_b081.glb` | bank interior | 8132 | 59.26 x 10.29 x 20.38 | no (B081) |
| `interior_b082.glb` | trading hall interior | 4482 | 21.79 x 9.04 x 13.4 | `b082.glb` |
| `interior_b086.glb` | herbalists' quarter bookshop interior | 507 | 7.71 x 6.47 x 6.23 | no (B086) |
| `interior_b119.glb` | civic heart bakery interior | 574 | 5.11 x 6.65 x 6.98 | no (B119) |
| `interior_b129.glb` | civic heart horse supply shop interior | 3423 | 38.66 x 6.68 x 24.39 | no (no export) |
| `interior_bird01.glb` | giant-bird aerie interior | 1266 | 27.57 x 13.5 x 29.49 | `bird01.glb` |
| `interior_c02.glb` | library interior | 26494 | 49.35 x 18.17 x 71.01 | `c02.glb` |
| `interior_c03.glb` | inn and tavern interior | 9610 | 38.5 x 12.42 x 28.09 | `c03.glb` |
| `interior_dragon01.glb` | small-dragon stable interior | 808 | 29.59 x 10.5 x 20.67 | `dragon01.glb` |
| `interior_s01.glb` | horse stable interior | 648 | 29.12 x 3.5 x 15.78 | `s01.glb` |
| `interior_w01.glb` | weapons hall interior | 4810 | 44.92 x 6.72 x 24.14 | `w01.glb` |
