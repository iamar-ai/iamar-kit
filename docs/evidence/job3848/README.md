# Job 3848: interior lights for generated houses

World: `iamar-world new beach_house --template beach`, plus
`assets building house models/house.glb --rooms bedroom:3,living,kitchen,bath:2 --style beach`
placed at [0, 2.4, 40] rotated [0, -90, 0] (collision mesh). Rendered on zoe (Arc 140V,
Godot 4.7.2, `preview --quick --size 960x540`, kit d4d997f + browser 02e75029 source).

- `*_no_lights.png`: the house with only sun and sky ambient (the sim's flat grey-blue rooms).
  `validate` on this scene: `WARN objects[0] models/house.glb: 7 of 7 rooms have no light ...`
  with a light that fixes it.
- `*_lit.png`: the same views after adding the sidecar's 4 lights with the house's position
  and yaw (`KitHouseRooms.scene_lights`); `validate` no longer warns. Preview TARGETS PASS
  (21 draw calls, worst frame 5.0 ms).
