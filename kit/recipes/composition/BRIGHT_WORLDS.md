# Bright worlds (desert, salt flat, snow, beach): keep the ground readable

Track B worlds with a pale setting wash out by day: in the desert blind test (an internal task review) sand
and salt flat reached near-white (exposure 0.92, fog #dfe2e4, light sand albedo), so the "shimmering
salt flat" did not read apart from the dunes. `iamar-world shots` now WARNs on such frames
(`kit/shots/README.md`, "Washed-out frames").

Rules (ENGINEERING layer, style-independent):

1. **Ground albedo ceiling.** Keep the base colour of ground materials at or below about 0.70
   (sRGB #b3b3b3 in the brightest channel); pale means mid-light, never white. The sun and sky add
   the rest.
2. **Exposure.** Start a bright world at `environment.exposure` 0.7 to 0.8, not 1.0 or higher; raise
   it only if the shots' lower band stays under the WARN.
3. **Fog.** A fog colour near the horizon colour is fine; do not use a near-white fog with
   a density that reaches the near ground (it lifts the whole lower band).
4. **Contrast on the ground.** Salt crust, snow or white sand needs a second tone and a surface
   pattern: cracked-crust or ripple texture, a darker wet or shadowed band, scattered stones, tracks
   or footprints. Break any flat pale plane with a different tone every 10 to 20 m.
5. **Shadows.** Low sun (golden hour, 9 to 10 h or 15 to 16 h) gives long shadows that carry detail
   a noon sun flattens; use the day camera at a time the shadows read.
6. **Check.** Run `iamar-world shots <world> <out>`; no `WARN washed out` in `SHOTS.md`, and look at
   the day sheets yourself.

Style note: the thresholds are engineering limits; the colours you pick under them are your style
profile's business.
