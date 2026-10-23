"""What the generators read from a style profile (kit/style/schema/style.schema.json).

* colours: a region's wall / timber / roof / trim / ground_stone / ground_storeys / paints,
  falling back to the palette, then to neutral defaults; weathered per role by the profile's
  `weathering.roles` (MpStyle._shade: each house gets its own small shift, by seed);
* dimensions: storey, door, window, bay, jetty, oriel, corner tower, eave overhang, roof pitch
  (`dimensions`), with the iamar city's numbers as defaults for a profile that leaves them out;
* materials: each role is bound to one of the profile's painted layers (`materials.layers`),
  so a world painted with `check_style.py --paint` puts its texture on the right faces;
* budgets: `budgets.triangles.building` (and `landmark`).
"""
from __future__ import annotations

import colorsys
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import check_style  # noqa: E402

DEFAULT_DIMS = {
    "storey_m": 3.2, "storey_scale": {"ground": [1.0, 1.32], "top": [0.84, 1.0]},
    "door_m": [2.1, 2.3], "window_width_m": [0.62, 1.15], "window_height_storey_fraction": [0.36, 0.5],
    "window_bay_m": [1.9, 3.1], "eave_overhang_m": [0.42, 0.66], "jetty_m": [0.32, 0.55],
    "oriel_m": {"width": [1.6, 2.4], "depth": [0.45, 0.6]}, "corner_tower_radius_m": [1.0, 1.35],
    "roof_pitch_rise_per_run": [0.72, 0.88, 1.04, 1.2, 1.36],
}
NEUTRAL = {"wall": "#e6dcc6", "timber": "#5c3b22", "roof": "#4d6d93", "trim": "#6a5a48",
           "stone": "#b0a898", "window": "#2f4660", "iron": "#4d5157", "paint": "#7a2e2a"}
# role -> painter layers to look for, best first (kit/tools/paint_materials.py names)
ROLE_LAYERS = {
    "wall": ["plaster"], "stone": ["ashlar", "stone", "granite"], "timber": ["timber"],
    "roof": ["slate", "slate_dark", "glazed", "shingle", "thatch"], "trim": ["trim"], "iron": ["iron"],
}


class Style:
    def __init__(self, ref: str, region: str | None = None, seed: int = 0):
        self.ref = ref
        self.prof, _ = check_style.load(ref)
        regions = self.prof.get("regions") or {}
        if region is None:
            region = next(iter(regions), None)
        if region is not None and region not in regions:
            raise ValueError("profile %s has no region %r (has: %s)" % (self.prof.get("id"), region, ", ".join(regions)))
        self.region_name = region
        self.region = regions.get(region, {}) if region else {}
        self.seed = seed
        self.dims = dict(DEFAULT_DIMS)
        self.dims.update(self.prof.get("dimensions") or {})
        self.own_dims = set((self.prof.get("dimensions") or {}).keys())
        self.palette = {k: v["hex"] for k, v in (self.prof.get("palette") or {}).items() if isinstance(v, dict) and "hex" in v}
        self.layers = (self.prof.get("materials") or {}).get("layers") or {}
        self.tile_m = float((self.prof.get("materials") or {}).get("tile_m", 4.0))
        self.weather = ((self.prof.get("weathering") or {}).get("roles")) or {}
        tri = (self.prof.get("budgets") or {}).get("triangles") or {}
        self.budget = {"building": int(tri.get("building", 3000)), "landmark": int(tri.get("landmark", 15000)),
                       "prop": int(tri.get("prop", 300))}

    # ---------------------------------------------------------------- numbers
    def rng(self, salt: str) -> random.Random:
        return random.Random("%s/%s/%d/%s" % (self.prof.get("id"), self.region_name, self.seed, salt))

    def pick(self, key, salt, sub=None):
        v = self.dims.get(key)
        if sub is not None:
            v = (v or {}).get(sub)
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, list) and len(v) == 2 and key != "roof_pitch_rise_per_run":
            return self.rng(salt).uniform(float(v[0]), float(v[1]))
        if isinstance(v, list) and v:
            return float(self.rng(salt).choice(v))
        raise KeyError(key)

    def pitch(self, eaves: float, inradius: float) -> float:
        """Roof rise per metre: the profile's pitch list, else its roof height fraction.

        A profile with both (iamar: pitches 0.72-1.36, roof 1/3-1/2 of the height) keeps the roof's
        share of the whole building in range: a picked pitch whose roof is too low or too high for
        these eaves is replaced by one of the list that fits, else set to the nearest bound. Without
        this a three-storey house took a quarter-height roof (harbour blind-test review, an internal task).
        The fallback stays within the lint's pitch range (smallest pitch - pitch_slack to largest +
        pitch_slack): narrow wings (L and U arms) may then stay under the share, and wide 1-storey
        houses over it, which the report's roof_share shows and style-gen warns about (an internal task)."""
        if "roof_pitch_rise_per_run" in self.own_dims or "roof_height_fraction" not in self.own_dims:
            k = self.pick("roof_pitch_rise_per_run", "pitch")
            f = self.dims.get("roof_height_fraction") if "roof_height_fraction" in self.own_dims else None
            if not f or inradius <= 0 or eaves <= 0:
                return k
            lo, hi = float(f[0]), float(f[1])
            share = lambda kk: kk * inradius / (eaves + kk * inradius)
            if lo <= share(k) <= hi:
                return k
            pitches = [float(p) for p in self.dims["roof_pitch_rise_per_run"]]
            fits = [p for p in pitches if lo <= share(p) <= hi]
            if fits:
                return self.rng("pitch_fit").choice(fits)
            bound = lo if share(k) < lo else hi
            slack = float((self.prof.get("lint") or {}).get("pitch_slack", 0.15))
            floor, ceiling = min(pitches) * (1.0 - slack) + 1e-3, max(pitches) * (1.0 + slack) - 1e-3
            return min(ceiling, max(floor, bound / max(1e-3, 1.0 - bound) * eaves / inradius))
        f = self.dims["roof_height_fraction"]
        frac = self.rng("pitch").uniform(float(f[0]), float(f[1]))
        # roof height as a share of the whole building: rise = frac / (1 - frac) x eaves
        rise = frac / max(1e-3, 1.0 - frac) * eaves
        return max(0.08, rise / max(inradius, 0.5))

    # ---------------------------------------------------------------- colours
    def colour(self, role: str, salt: str = "") -> str:
        r = self.region
        if role == "stone":
            gs = r.get("ground_storeys")
            h = (self.rng("ground" + salt).choice(gs) if gs else None) or r.get("ground_stone")
        elif role == "paint":
            ps = r.get("paints")
            h = self.rng("paint" + salt).choice(ps) if ps else None
        else:
            h = r.get(role)
        if not h:
            for name in {"wall": ["plaster"], "timber": ["timber"], "roof": ["roof_slate"], "trim": ["trim_stone"],
                         "stone": ["stone", "castle"], "window": ["window"], "iron": ["iron", "black_iron"],
                         "paint": ["door"]}.get(role, []):
                if name in self.palette:
                    h = self.palette[name]
                    break
            else:
                h = self._layer_tint(role) or NEUTRAL.get(role, "#cccccc")
        return self.weathered(h, {"stone": "wall", "paint": "timber", "window": None, "iron": None}.get(role, role), salt)

    def _layer_tint(self, role):
        lay = self.layer(role)
        return (self.layers.get(lay) or {}).get("tint") if lay else None

    def weathered(self, h: str, role: str | None, salt: str) -> str:
        w = self.weather.get(role) if role else None
        if not w:
            return h
        r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
        hh, s, v = colorsys.rgb_to_hsv(r, g, b)
        rng = self.rng("weather/%s/%s" % (role, salt))
        # weathering scales are the city's (mats.gd); applied half strength, because region
        # colours are already the plan's muted palette
        s *= 1.0 - (1.0 - float(w.get("saturation_scale", 1.0))) * 0.5
        v *= 1.0 - (1.0 - float(w.get("value_scale", 1.0))) * 0.5
        hh = (hh + rng.uniform(-1, 1) * float(w.get("hue_jitter", 0.0))) % 1.0
        s = min(1.0, max(0.0, s + rng.uniform(-1, 1) * float(w.get("saturation_jitter", 0.0)) * 0.5))
        v = min(1.0, max(0.12, v + rng.uniform(-1, 1) * float(w.get("value_jitter", 0.0)) * 0.5))
        r, g, b = colorsys.hsv_to_rgb(hh, s, v)
        return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))

    # ---------------------------------------------------------------- materials
    def layer(self, role: str) -> str | None:
        """The profile's painted layer for a role: one whose `use` names this region, else the first
        with a matching painter layer, else None."""
        want = ROLE_LAYERS.get(role, [])
        cands = [k for k, v in self.layers.items() if isinstance(v, dict) and v.get("layer") in want]
        if not cands:
            return None
        reg = (self.region_name or "").lower().rstrip("s")
        if reg:
            for k in cands:
                if reg and reg in str(self.layers[k].get("use", "")).lower():
                    return k
        cands.sort(key=lambda k: want.index(self.layers[k]["layer"]))
        if role == "roof":
            civic = [k for k in cands if "civic" in str(self.layers[k].get("use", "")).lower()]
            return (civic or cands)[0]
        return cands[0]

    def window_glow(self) -> str:
        """the lit-window colour: the region's `window_glow`, else the palette's, lamp or candle glow."""
        return self.region.get("window_glow") or self.palette.get("window_glow") or self.palette.get("lamp_glow") or self.palette.get("candle") or "#ffc060"

    def materials(self, salt: str = "") -> dict:
        """role -> material spec {name, color, layer}; material names are the layer names, so one
        texture per layer fits; a role without a layer keeps its role name."""
        out = {}
        roof_layer = self.layer("roof")
        for role in ("wall", "stone", "timber", "roof", "trim", "iron", "window", "paint"):
            lay = {"paint": self.layer("timber"), "window": None}.get(role, self.layer(role))
            if role == "roof" and roof_layer is None:
                lay = self.layer("wall")   # a flat clay roof (desert): the wall's layer
            if role == "trim" and lay is None:
                lay = self.layer("timber")
            if role == "stone" and lay is None:
                lay = self.layer("wall")
            name = {"window": "window", "paint": (lay + "_paint") if lay else "paint"}.get(role, lay or role)
            if role == "trim" and lay == self.layer("timber"):
                name = (lay or "timber") + "_trim"
            if role == "stone" and lay == self.layer("wall"):
                name = (lay or "wall") + "_stone"
            if role == "roof" and lay == self.layer("wall"):
                name = (lay or "wall") + "_roof"
            out[role] = {"name": name, "color": self.colour(role, salt), "layer": lay,
                         "roughness": 0.35 if role == "window" else (0.6 if role == "iron" else 0.9)}
        # glazing (an internal task): smooth dark glass with a faint warm interior glow. A package's
        # emissive is constant (no clock dims it), so it is kept under the daylit glass: at 0.5 the
        # panes read flat amber by day, dusk and night alike (harbour a5 R2); at WINDOW_GLOW the
        # glass reads dark blue-grey against sunlit walls and warm against the night walls. An
        # emissive material also stays live-lit through bake_vertex_light (harbour a4: baked peach)
        out["window"].update(roughness=0.12, emissive=self.window_glow(), emissive_strength=WINDOW_GLOW)
        out["cap"] = dict(out["roof"], name=out["roof"]["name"] + "_cap",
                          color=self.weathered(_darker(out["roof"]["color"]), None, salt))
        return out

    def textures(self, mats: dict, tex_dir: Path | None) -> dict:
        """material name -> PNG bytes for every material whose layer has <tex_dir>/<layer>.png."""
        if not tex_dir:
            return {}
        out = {}
        for spec in mats.values():
            lay = spec.get("layer")
            if lay and (tex_dir / (lay + ".png")).is_file():
                out[spec["name"]] = (tex_dir / (lay + ".png")).read_bytes()
        return out


WINDOW_GLOW = 0.2   # emissive strength of house glass (an internal task; lanterns use 1.3)


def _darker(h, f=0.82):
    r, g, b = (int(h[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % (round(r * f), round(g * f), round(b * f))
