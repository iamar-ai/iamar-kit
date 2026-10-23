# Job 3812: house --furnish evidence (eva, 2026-10-23)

    iamar-world assets building house beach_house.glb --rooms bedroom:3,living,kitchen,bath:2 --floors 2 --style beach --furnish
    HOUSE ... 619164 bytes 4020 triangles ... floors 2 rooms 7 size 9.8x9.8 lights 4

Rendered on eva (Godot 4.7.2, software GL under xvfb, `tests/kit_house_furnish/shot.gd`) with
the sidecar's ceiling lights; colours are not a lighting judgement.

- `plan_floor_0.png`, `plan_floor_1.png`: from above, everything over 2.3 m cut away (cut walls
  are not drawn). Ground: sofa, rug, armchair, bookshelf in the living room; counter in the
  kitchen; bathtub. Upstairs: a bed, wardrobe and rug in each of three bedrooms; the second bath.
- `bedroom_from_door.png`, `living_from_door.png`, `kitchen_from_door.png`, `bath_from_door.png`:
  from each doorway; doorways open, windows uncovered.
- `beach_house.rooms.json`: the sidecar with each room's `furniture`.
