# City views for the track question (B3)

Twelve small pictures of the iamar city, a **street**, a **landmark** and the **skyline** for
each quarter, so an agent can show the user what "like the iamar city" means
(`kit/interview/common.md` B3, `kit/interview/tracks/README.md` section 2). Send the three
pictures of the quarter closest to the user's wish; if they have no wish yet, send
`civic_street.jpg`, `civic_landmark.jpg` and `civic_skyline.jpg`. If your session cannot
show images, give the user the file paths and describe them with the quarter's `mood` line in
`kit/style/iamar/style.json`.

| Quarter | Street | Landmark | Skyline |
|---|---|---|---|
| civic (centre, cathedral, south gate) | [civic_street.jpg](civic_street.jpg) west gate street into the cathedral market | [civic_landmark.jpg](civic_landmark.jpg) the cathedral from its fountain market | [civic_skyline.jpg](civic_skyline.jpg) the South Gate from the forest road |
| mages | [mages_street.jpg](mages_street.jpg) north back lane | [mages_landmark.jpg](mages_landmark.jpg) Starweave School of Magic from the portal court | [mages_skyline.jpg](mages_skyline.jpg) east gate and violet towers from the east bridge |
| warriors | [warriors_street.jpg](warriors_street.jpg) inn and warriors' lane (smithy signs, ember lamps) | [warriors_landmark.jpg](warriors_landmark.jpg) the big weapons shop on the north gate street | [warriors_skyline.jpg](warriors_skyline.jpg) north gate and roofs from the north bridge |
| herbalists | [herbalists_street.jpg](herbalists_street.jpg) the processional high street from inside the South Gate | [herbalists_landmark.jpg](herbalists_landmark.jpg) the library from its viewing forecourt | [herbalists_skyline.jpg](herbalists_skyline.jpg) the herb garden and the library from the portal landing |

All at 16:30 game time (golden hour), eye height 1.7 m unless `views.json` says otherwise,
960x540 JPEG (about 120 KB each, 1.45 MB together). Rendered on 2026-10-20 from the iamar browser source (not public)
`b648a60b` (the masterplan city with its baked lightmaps from the iamar-models mesh archive (not public)), software
renderer (Xvfb, Mesa llvmpipe), the Fast frame (no MSAA, no sun shadow): what a Fast-preset
player sees, a little softer than the GPU game.

## Rendering them again

`views.json` holds every camera in city plan coordinates (`worlds/oakhaven_masterplan/city-masterplan.json`
of the iamar browser source (not public); x, z; the South Gate is at +z) with heights above the ground. `city_views.gd`
renders them from an iamar checkout that has the city's baked files (`baked/masterplan`) and has
been imported once (`godot --headless --path <iamar> --import`):

    OAK_LOOK=off offscreen godot --path <iamar checkout> --resolution 1280x720 \
        -s <kit>/kit/gallery/city/city_views.gd -- <kit>/kit/gallery/city/views.json <out dir> [view id,...]

It prints `CV <id> eye=... target=...` per view and `CV_DONE <n>`; about 3 minutes for all
twelve in software. Never on a real display (`offscreen` only). Check: `python3 kit/tests/gallery/city_views_test.py`.

Traps met while choosing the cameras (2026-10-20): footprints in the plan include interior halls,
so a camera placed on open-looking ground inside a footprint (the warriors' training ground lies in
the weapons shop's footprint) renders an interior; market stalls and awnings stand in front of
most low cameras in the cathedral market, so that view stands 5 m up; a camera on a 5 m lane
beside a 30 m building sees only a wall: stand across the widest street or square from it.

Licence: renders of the project's own city (`kit/inventory/licences.json` row
`original-procedural`; project licence not yet chosen, so the public export withholds them until
the maintainer decides).
