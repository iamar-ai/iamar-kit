// tests/kit_playtest/reach: script entities for the playtest's interact-key reach checks.
// Rebuild: iamar-world compile-typescript tests/kit_playtest/reach/world.ts tests/kit_playtest/reach/world <out>
//  * a cylinder 0.5 m up: in the key's 2.5 m reach from where `use` stands (1.8 m out)
//    (using it also plays the package sound asset:audio/ding.ogg: playtest names it, an internal task)
//  * a sphere 3 m up: out of reach from the ground (about 3.5 m from a visitor's feet)
//  * a box with a second sphere 1 m from it on the spawn side: the key picks that sphere
// Spawn (0, 0, 8); +Y up, metres.

let cyl = 0, high = 0, box = 0, decoy = 0;

function on_init(): void {
  cyl = iamar.entity_spawn("cylinder", 0, 0.5, 0, 0);
  high = iamar.entity_spawn("sphere", 6, 3.0, 0, 0);
  box = iamar.entity_spawn("box", -6, 0.5, 0, 0);
  decoy = iamar.entity_spawn("sphere", -5.4, 0.5, 0.8, 0);
}

function on_interact(player: number, entity: number): void {
  if (entity === cyl) {
    iamar.ui_note("used the cylinder");
    iamar.sound_play("asset:audio/ding.ogg", 0, 0.5, 0);
  }
  else if (entity === high) iamar.ui_note("used the high sphere");
  else if (entity === box) iamar.ui_note("used the box");
  else if (entity === decoy) iamar.ui_note("used the decoy sphere");
}
