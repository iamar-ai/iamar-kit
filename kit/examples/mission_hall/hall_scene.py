"""Writes <package>/manifest.json and scene.json: the hall, its lights and sounds, the
return portal, the eight mission-givers and their missions.

    python3 kit/examples/mission_hall/hall_scene.py worlds/mission_hall \
        [--city iamar://local/oakhaven] [--id mission_hall] [--owner you] [--author "Your Name"]

--city is the world the portal and the missions lead to (default the built-in city,
iamar://local/oakhaven; any address of docs/WORLD_FORMAT.md section on portals works).

Positions come from the hall's geometry (mission_hall.py, the Blender step): booths every
45 degrees round from +Z at radius 34 (the giver stands 2.3 m into the alcove), braziers
at radius 19 between them, the gallery floor at y 8 between radius 29 and 34, the dais
top at y 0.9 with the portal ring at z -1.5.
"""
import argparse
import json
import math
import os

ap = argparse.ArgumentParser(description="Write the Mission Hall's manifest.json and scene.json")
ap.add_argument("package", nargs="?", default="worlds/mission_hall")
ap.add_argument("--city", default="iamar://local/oakhaven", help="world the portal and missions lead to")
ap.add_argument("--id", default="mission_hall", help="this world's id")
ap.add_argument("--owner", default="you", help="hub account that will publish it")
ap.add_argument("--author", default="Your Name")
ARGS = ap.parse_args()
PKG = ARGS.package
OAK = ARGS.city


def d(a):
    return math.sin(math.radians(a)), math.cos(math.radians(a))


def at(a, r, y=0.0):
    s, c = d(a)
    return [round(s * r, 2), y, round(c * r, 2)]


def gallery(a):
    return at(a, 31.6, 8.1)


def booth(k):
    return at(45.0 * k, 36.3)


# ---------------------------------------------------------------- the people
NPCS = [
    {"id": "guildmaster", "name": "Guildmaster Corvin", "title": "Adventurers' Guild", "k": 0,
     "look": {"hero": "villager_man", "height": 1.92, "build": 1.1, "hair": "Hair_SimpleParted", "hair_color": "b8b8b8", "beard": "Hair_Beard", "skin": "e8d0bc"},
     "outfit": {"chest": "plate", "dye": "crimson", "head": "none", "main_hand": "sword", "off_hand": "none", "trim_dye": "gold"},
     "idle": "idle", "emotes": ["talk", "interact"],
     "greeting": ["Welcome to the Mission Hall, traveller. Every guild in the realm posts its work here. Look for the gold marks.",
                  "Back again? The boards never empty. Neither do my coffers, for those who deliver."]},
    {"id": "ranger_captain", "name": "Captain Sera Thornwood", "title": "Rangers of the Weald", "k": 1,
     "look": {"hero": "villager_woman", "height": 1.76, "hair": "Hair_Long", "hair_color": "8a3a1e", "skin": "f0dccb"},
     "outfit": {"chest": "leather", "dye": "forest", "head": "hood", "main_hand": "bow", "off_hand": "none", "pants_dye": "umber"},
     "idle": "idle", "emotes": ["talk"],
     "greeting": ["Rangers watch the roads so farmers can sleep. Care to walk a road for us?"]},
    {"id": "beast_tamer", "name": "Oona Wildheart", "title": "Beast Tamers", "k": 2,
     "look": {"hero": "villager_woman", "height": 1.7, "hair": "Hair_Buns", "hair_color": "161210", "skin": "8a6248"},
     "outfit": {"chest": "leather", "dye": "teal", "head": "none", "main_hand": "none", "off_hand": "none", "pants_dye": "moss", "boots_dye": "umber"},
     "idle": "idle", "emotes": ["talk", "interact"],
     "greeting": ["Every creature can be understood. Even the ones that bite. Especially those."]},
    {"id": "bounty_keeper", "name": "Grimsby Holt", "title": "Bounty Office", "k": 3,
     "look": {"hero": "smith", "height": 1.9, "build": 1.14, "hair": "", "beard": "Hair_Beard", "hair_color": "3a2418", "skin": "c49a7c"},
     "outfit": {"chest": "leather", "dye": "charcoal", "head": "none", "main_hand": "axe", "off_hand": "none", "pants_dye": "slate"},
     "idle": "guard", "emotes": ["talk"],
     "greeting": ["Bounties. Posted, paid, no questions. Bring proof or bring nothing."]},
    {"id": "archmage", "name": "Archmage Valerius", "title": "Arcane Conclave", "k": 4,
     "look": {"hero": "villager_man", "height": 1.86, "hair": "Hair_Long", "hair_color": "e0e0e0", "beard": "Hair_Beard", "skin": "f4e2d4"},
     "outfit": {"chest": "robe", "dye": "violet", "head": "wizard_hat", "main_hand": "staff", "off_hand": "spellbook", "trim_dye": "gold"},
     "idle": "spell", "emotes": ["cast", "talk"],
     "greeting": ["Hm? Ah, a visitor. Mind the circle, it is older than it looks. So am I."]},
    {"id": "cartographer", "name": "Mistress Ilse Marrow", "title": "Cartographers", "k": 5,
     "look": {"hero": "villager_lady", "height": 1.7, "hair": "Hair_Buns", "hair_color": "5a3a22", "skin": "fbe8dc"},
     "outfit": {"chest": "robe", "dye": "royal", "head": "circlet", "main_hand": "none", "off_hand": "spellbook", "trim_dye": "ivory"},
     "idle": "idle", "emotes": ["interact", "talk"],
     "greeting": ["Every map is a promise that the world is exactly so. Help me keep my promises."]},
    {"id": "merchant_prince", "name": "Prince Aurelio Vance", "title": "Merchants' Exchange", "k": 6,
     "look": {"hero": "villager_man", "height": 1.84, "hair": "Hair_SimpleParted", "hair_color": "2a1c14", "beard": "", "skin": "d8b49a"},
     "outfit": {"chest": "robe", "dye": "gold", "head": "circlet", "main_hand": "dagger", "off_hand": "none", "trim_dye": "crimson"},
     "idle": "idle", "emotes": ["talk", "interact"],
     "greeting": ["Coin, cloth, cargo and couriers. The Exchange moves the world. Browse, or better, work."],
     "shop": [["head", "circlet", 90], ["chest", "chain", 80], ["off_hand", "kite_shield", 70], ["main_hand", "mace", 65], ["dye", "gold", 40]]},
    {"id": "knight_commander", "name": "Dame Rowena Brightshield", "title": "Order of the Dawn", "k": 7,
     "look": {"hero": "villager_woman", "height": 1.8, "build": 1.04, "hair": "Hair_Buns", "hair_color": "e0c070", "skin": "fff0e6"},
     "outfit": {"chest": "plate", "dye": "ivory", "head": "winged_helm", "main_hand": "sword", "off_hand": "kite_shield", "trim_dye": "gold"},
     "idle": "guard", "emotes": ["talk"],
     "greeting": ["The Dawn keeps watch in every land the portals reach. Stand with us."]},
]

# ---------------------------------------------------------------- the missions
Q = []


def quest(qid, giver, title, offer, waiting, thanks, steps, gold, xp, reward=(), **kw):
    q = {"id": qid, "title": title, "giver": giver, "offer": offer, "waiting": waiting, "thanks": thanks,
         "steps": steps, "gold": gold, "xp": xp, "reward": list(reward)}
    q.update(kw)
    Q.append(q)


def oak(o):
    o = dict(o)
    o["world"] = OAK
    return o


THORNBURY = [60.0, 580.0]   # Terrain.THORNBURY
SOUTH_GATE = [0.0, 99.0]
POND = [100.0, -30.0]
GLADE = [-98.0, -40.0]

# The Guildmaster: the hub's own story
quest("welcome", "guildmaster", "Welcome to the Hall",
      "Every hero starts somewhere, and here that means shaking hands. Introduce yourself to Captain Thornwood of the Rangers, Archmage Valerius and Prince Aurelio of the Exchange. Their booths are round the ring, under the banners.",
      "Three handshakes. The Captain is to my left, the Archmage behind the portal, the Prince across the hall.",
      "Good. Now they know your face, and so do I. Take this for your trouble, and come back when you want real work.",
      [[{"kind": "talk", "npc": "ranger_captain", "text": "Meet Captain Sera Thornwood", "choice": "The Guildmaster sent me to introduce myself.", "line": "Did he? Then you walk well, and you will walk far. Come back when you want a road to watch."},
        {"kind": "talk", "npc": "archmage", "text": "Meet Archmage Valerius", "choice": "Good day, Archmage. I am new to the Hall.", "line": "New? Everyone is new to something. I am new to being old. Off you go, and mind the circle."},
        {"kind": "talk", "npc": "merchant_prince", "text": "Meet Prince Aurelio Vance", "choice": "The Guildmaster suggests we should know each other.", "line": "A sensible man, Corvin. I am always glad to know someone who might carry things for me. For coin, naturally."}]],
      25, 90, chain="hall", accept="Off you go. Smile at them; it costs nothing, and it pays well.")
quest("proving", "guildmaster", "The Proving Fields",
      "Words are cheap. Slimes are not. Step through the portal to Oakhaven and clear four of them from the nest south of Thornbury, then come back and tell me how it went.",
      "Four slimes, south of Thornbury in Oakhaven. The portal on the dais will take you there.",
      "Four! And you still have all your fingers. The Guild counts you as one of its own now. Wear this helm with pride.",
      [oak({"kind": "kill", "kinds": ["slime", "blue_slime"], "count": 4, "camps": [0], "text": "Slimes slain near Thornbury (Oakhaven)"})],
      60, 160, ["head", "iron_helm"], requires=["welcome"], chain="hall")
quest("champion", "guildmaster", "A Champion's Errand",
      "Lord Aldren of Oakhaven asked the Guild for a champion, and I have named you. Present yourself at his keep, then bring down one of the great slimes that trouble his lands.",
      "Lord Aldren is in the throne room of Oakhaven's keep. The big slimes nest out in the fields.",
      "Lord Aldren writes that you did the Guild proud. This shield is from both of us.",
      [oak({"kind": "talk", "npc": "Lord Aldren Oakheart", "at": [0.0, -125.5], "text": "Present yourself to Lord Aldren (Oakhaven)", "choice": "The Mission Hall names me your champion, my lord.", "line": "The Hall's champion! Good. My fields need one. The great slimes are the worst of it: bring one down and my people will breathe easier."}),
       oak({"kind": "kill", "kinds": ["big_slime"], "count": 1, "camps": [1, 2, 3], "text": "A great slime slain (Oakhaven)"})],
      150, 380, ["off_hand", "kite_shield"], requires=["proving"], chain="hall")

# Captain Sera Thornwood: roads and places
quest("thornbury_patrol", "ranger_captain", "Patrol to Thornbury",
      "Walk the south road of Oakhaven for me: out through the south gate and on down to Thornbury's green. Keep your eyes open. Then come back and report.",
      "Oakhaven's south gate first, then Thornbury, down the road.",
      "Road clear, green quiet. That is a good report. Take this bow; a ranger should have one.",
      [oak({"kind": "goto", "target": SOUTH_GATE, "radius": 7, "text": "Pass Oakhaven's south gate"}),
       oak({"kind": "goto", "target": THORNBURY, "radius": 16, "text": "Reach Thornbury's green"})],
      40, 120, ["main_hand", "bow"])
quest("pond_watch", "ranger_captain", "Eyes on the Mill Pond",
      "Something has been stirring the mill pond east of Oakhaven, and the miller will not say what. Go and look. Stand on its shore and see.",
      "The mill pond is east of Oakhaven's walls, past the windmill.",
      "Frogs, turtles and a very fat duck? I will tell the miller he can stop worrying. Here is your pay.",
      [oak({"kind": "goto", "target": POND, "radius": 22, "text": "Look over the mill pond (Oakhaven)"})],
      30, 90, requires=["thornbury_patrol"])

# Oona Wildheart: beasts and riding
quest("saddle_up", "beast_tamer", "Saddle Up",
      "Horses and riders have to trust each other. Go to Wren's stable in Oakhaven, ask her for a steady mount, then ride it to Thornbury and on to the mill pond.",
      "Wren's stable, then Thornbury and the mill pond, on horseback. Walk up to a horse and press F.",
      "You came back in one piece and so did the horse. That is trust. Here, a little something from my purse.",
      [oak({"kind": "talk", "npc": "Wren", "at": [58.0, 31.0], "text": "Ask Wren for a mount (Oakhaven)", "choice": "Oona Wildheart sent me for a steady horse.", "line": "Oona! She taught me half of what I know. Take any of them, they are all steady for a friend of hers."}),
       oak({"kind": "ride", "target": THORNBURY, "radius": 16, "text": "Ride to Thornbury's green"}),
       oak({"kind": "ride", "target": POND, "radius": 22, "text": "Ride on to the mill pond"})],
      45, 130)
quest("young_dragon", "beast_tamer", "The Young Dragon",
      "A young dragon has made a nest in the far south-west of Oakhaven's valley. It must learn that people are not food. Go and humble it. Gently, if you can.",
      "The whelp's nest is far to the south-west of Oakhaven, past the slime fields.",
      "Humbled, not hurt? You have the makings of a tamer. Wear this circlet; the beasts will know you by it.",
      [oak({"kind": "kill", "kinds": ["whelp"], "count": 1, "areas": [[[-150.0, 165.0], 24.0]], "text": "Humble the young dragon (Oakhaven)"})],
      120, 300, ["head", "circlet"], requires=["saddle_up"])

# Grimsby Holt: bounties
quest("bounty_slimes", "bounty_keeper", "Bounty: Slime Nests",
      "Six slimes. Any colour, any nest in Oakhaven. They are eating the farmers' cabbages and the farmers are eating my ear about it. Proof of kill, then pay.",
      "Six slimes from Oakhaven's nests. South of Thornbury is closest.",
      "Six. Counted. Paid. Pleasure doing business.",
      [oak({"kind": "kill", "kinds": ["slime", "blue_slime"], "count": 6, "camps": [0, 4], "text": "Slimes slain for the bounty (Oakhaven)"})],
      70, 160)
quest("bounty_big", "bounty_keeper", "Bounty: The Big Ones",
      "Now the real money. Two great slimes, the kind that split when you look at them wrong. They sit in the far nests of Oakhaven's valley.",
      "Two great slimes. East, north-east or south-west of Oakhaven.",
      "Two big ones. You are either very brave or very stupid, and the Office pays both the same. Take the axe too.",
      [oak({"kind": "kill", "kinds": ["big_slime"], "count": 2, "camps": [1, 2, 3], "text": "Great slimes slain (Oakhaven)"})],
      180, 420, ["main_hand", "axe"], requires=["bounty_slimes"])
quest("bounty_fowl", "bounty_keeper", "Bounty: Fowl Conspiracy",
      "Old Hob of Oakhaven swears the chickens are plotting. He has paid for a bounty. I do not ask. Five chickens, whacked till they puff. They come back, apparently.",
      "Five chickens. The south road of Oakhaven is thick with them.",
      "Five! Hob will sleep tonight. Probably. Here is his coin.",
      [oak({"kind": "kill", "kinds": ["chicken"], "count": 5, "areas": [[[-14.0, 112.0], 7.0], [[44.0, 44.0], 6.0]], "text": "Conspiring chickens taught a lesson (Oakhaven)"})],
      30, 60)

# Archmage Valerius: magic
quest("moonwater", "archmage", "Moonwater",
      "The deepest water of Oakhaven's mill pond remembers the moon. I need someone to swim out to its very middle and let the pond have a look at them. Do not ask me to explain.",
      "Swim out to the middle of Oakhaven's mill pond, where it is deep.",
      "Yes, I can smell the moon on you. Thank you. Keep this book; the pond seems to like you.",
      [oak({"kind": "goto", "target": POND, "radius": 5, "text": "Swim to the middle of the mill pond (Oakhaven)"})],
      50, 140, ["off_hand", "spellbook"])
quest("singing_stones", "archmage", "The Singing Stones",
      "West of Oakhaven's walls is a glade where the standing stones hum. Go and stand among them, then tell Ysolde the alchemist what you heard. She keeps notes for me.",
      "The glade with the standing stones is west of Oakhaven. Ysolde's shop is by the west gate.",
      "Ysolde's note says you hummed along. Excellent. The hat is yours; it hums too.",
      [oak({"kind": "goto", "target": GLADE, "radius": 12, "text": "Listen among the standing stones (Oakhaven)"}),
       oak({"kind": "talk", "npc": "Ysolde", "at": [-43.6, -4.9], "text": "Tell Ysolde what you heard (Oakhaven)", "choice": "The Archmage asked me to tell you what the stones sang.", "line": "A low chord and a high shimmer? Just as he said. I will write it down. Go tell the old man he was right, he loves that."})],
      60, 170, ["head", "wizard_hat"], requires=["moonwater"])

# Mistress Ilse Marrow: maps
quest("lost_pages", "cartographer", "Pages on the Gallery",
      "A gust from the oculus scattered my new chart of the valley all over the gallery upstairs. Three pages. The stairs are on either side of the hall.",
      "Three map pages on the gallery. Take the stairs up.",
      "All three, and not a crease. You have careful hands. Here, for your trouble.",
      [{"kind": "pickup", "item": "Map Page", "look": "book", "text": "Map pages found on the gallery", "spots": [gallery(20.0), gallery(160.0), gallery(250.0)]}],
      30, 80)
quest("chart_south", "cartographer", "Chart the South Road",
      "My chart of Oakhaven stops at its walls. Walk the south road for me, past the gate to Thornbury, and let Mistress Elowen at Oakhaven's library copy what you saw.",
      "Oakhaven's south gate, Thornbury, then the library in the Scholars' Quarter.",
      "Elowen's copy arrived by the evening post. A beautiful road. Thank you.",
      [oak({"kind": "goto", "target": SOUTH_GATE, "radius": 7, "text": "Pace out Oakhaven's south gate"}),
       oak({"kind": "goto", "target": THORNBURY, "radius": 16, "text": "Mark Thornbury on the chart"}),
       oak({"kind": "talk", "npc": "Mistress Elowen", "at": [23.0, -36.0], "text": "Have Mistress Elowen copy the chart (Oakhaven)", "choice": "Mistress Marrow of the Mission Hall asks you to copy this chart.", "line": "Ilse's hand, I would know it anywhere. Leave it with me, I will copy it tonight."})],
      70, 180, requires=["lost_pages"])

# Prince Aurelio Vance: trade (and a shop)
quest("letter_pell", "merchant_prince", "A Letter for Tomas Pell",
      "Tomas Pell keeps the general store in Oakhaven's Market Row. I have a letter of credit for him, and I trust no courier but a hero. Deliver it; he will pay you himself.",
      "Tomas Pell's store is on Market Row, south of Oakhaven's fountain.",
      "The Prince pays his couriers through me, and generously. Here is your fee, and a blade from my own shelf.",
      [oak({"kind": "talk", "npc": "Tomas Pell", "at": [-19.0, 50.0], "text": "Deliver the letter to Tomas Pell (Oakhaven)", "choice": "A letter from Prince Aurelio of the Mission Hall.", "line": "From the Prince himself? A letter of credit! This will keep my shelves full all winter."})],
      40, 90, ["main_hand", "dagger"], turn_in="Tomas Pell", turn_in_world=OAK,
      accept="Straight to Tomas, mind. He will settle with you himself.")
quest("spice_run", "merchant_prince", "The Spice Run",
      "Maribel of the Rusty Tankard owes the Exchange for a crate of pepper. Collect, politely. She is a good customer.",
      "The Rusty Tankard, north of Oakhaven's fountain.",
      "Paid in full and with a pie thrown in. You may keep the pie.",
      [oak({"kind": "talk", "npc": "Maribel Hollow", "at": [-2.3, -35.8], "text": "Collect from Maribel at the Rusty Tankard (Oakhaven)", "choice": "The Merchants' Exchange sends its regards, and its bill.", "line": "The pepper! Worth every copper. Here, and take a pie back for the Prince."})],
      50, 100, requires=["letter_pell"])

# Dame Rowena Brightshield: the Order of the Dawn
quest("vigil", "knight_commander", "The Vigil",
      "Every knight of the Dawn keeps a vigil before taking vows. Light the two candles set out on the gallery, then tell the Guildmaster you stand ready. He likes to know.",
      "Two candles on the gallery, then a word with Guildmaster Corvin.",
      "You kept the vigil. The Dawn sees you. Wear its mail.",
      [{"kind": "pickup", "item": "Dawn Candle", "look": "herb", "text": "Vigil candles lit on the gallery", "spots": [gallery(60.0), gallery(200.0)]},
       {"kind": "talk", "npc": "guildmaster", "text": "Tell the Guildmaster you stand ready", "choice": "I have kept the Dawn's vigil.", "line": "Have you now! Rowena's knights are the best of us. Go and tell her I said so."}],
      40, 110, ["chest", "chain"])
quest("blessing", "knight_commander", "Blessing of the Dawn",
      "Brother Aldous keeps the Dawn's chapel in Oakhaven. Take him my greeting and receive his blessing. Stay with him after; he will see you rewarded.",
      "Brother Aldous, at Oakhaven's chapel.",
      "Rowena asked me to see you rewarded, and the Dawn keeps its word. Go in light.",
      [oak({"kind": "talk", "npc": "Brother Aldous", "at": [-34.0, -25.3], "text": "Receive Brother Aldous's blessing (Oakhaven)", "choice": "Dame Rowena of the Mission Hall sends her greeting.", "line": "Rowena! Kneel, child. May the Dawn walk with you through every portal. Now, a little something from the chapel's chest."})],
      60, 150, turn_in="Brother Aldous", turn_in_world=OAK, requires=["vigil"])

# ---------------------------------------------------------------- scene
npcs = []
for n in NPCS:
    k = n.pop("k")
    e = {"id": n["id"], "name": n["name"], "title": n["title"], "kind": "villager",
         "look": n["look"], "outfit": n["outfit"], "position": booth(k), "yaw": 45.0 * k,
         "idle": n["idle"], "emotes": n["emotes"], "wander_radius": 0, "greeting": n["greeting"]}
    if "shop" in n:
        e["shop"] = n["shop"]
    npcs.append(e)

braziers = [at(22.5 + 45 * k, 19.0, 1.32) for k in range(8)]
objects = [
    {"id": "hall", "asset": "assets/hall.glb", "position": [0, 0, 0], "collision": "none", "cast_shadow": False},
    {"id": "hall_collision", "asset": "assets/hall_collision.glb", "position": [0, 0, 0], "collision": "mesh", "cast_shadow": False, "visible_range": 0.01},
    {"id": "sun_shaft", "asset": "assets/shaft.glb", "position": [0, 0, 0], "collision": "none", "cast_shadow": False},
    {"id": "portal_veil", "asset": "assets/veil.glb", "position": [0, 2.6, -1.5], "animation": "swirl", "collision": "none", "cast_shadow": False},
]
for i, b in enumerate(braziers):
    objects.append({"id": "flame_%d" % i, "asset": "assets/flame.glb", "position": b, "animation": "flicker", "collision": "none", "cast_shadow": False, "visible_range": 70})

lights = [{"id": "oculus", "type": "spot", "position": [0, 38, 0], "rotation": [-88.5, 0, 0], "spot_angle": 7, "range": 48, "attenuation": 0.3, "color": "#fff0d8", "energy": 5.0}]
for k in range(8):
    p = at(45.0 * k, 35.0, 3.4)
    lights.append({"id": "booth_%d" % k, "type": "point", "position": p, "color": "#ffc27a", "energy": 1.6, "range": 7.5})
lights.append({"id": "portal_glow", "type": "point", "position": [0, 2.6, -0.8], "color": "#8fd8ff", "energy": 1.4, "range": 7})

sounds = [{"id": "hall", "file": "audio/hall_ambience.ogg", "volume_db": -4, "loop": True}]
for i, b in enumerate(braziers):
    sounds.append({"id": "brazier_%d" % i, "file": "audio/brazier.ogg", "position": b, "radius": 9, "volume_db": -7, "loop": True})

scene = {
    "format": "iamar-scene", "format_version": 0,
    "x-source": "Built by kit/examples/mission_hall: mission_hall.py (geometry, baked light) and hall_scene.py (this file).",
    "environment": {
        "sky": {"type": "procedural", "top_color": "#3d6ea8", "horizon_color": "#a9c3dc", "ground_color": "#4a4438"},
        "sun": {"enabled": False},
        "ambient": {"color": "#8a7a66", "energy": 0.85, "source": "color"},
        "fog": {"enabled": True, "color": "#5a4a3a", "density": 0.004},
        "exposure": 1.0,
    },
    "objects": objects,
    "lights": lights,
    "spawn_points": [{"id": "default", "position": [0, 0.9, 4.6], "yaw": 0},
                     {"id": "from_oakhaven", "position": [0, 0.9, 4.6], "yaw": 0}],
    "sounds": sounds,
    "portals": [{"id": "to_oakhaven", "to": OAK + "#from_mission_hall", "label": "Oakhaven", "position": [0, 0.9, -1.5], "yaw": 0,
                 "size": [2.6, 3.2, 0.6], "visual": "none", "color": "#7fd6ff"}],
    "npcs": npcs,
    "quests": Q,
}
manifest = {
    "format": "iamar-world", "format_version": 0,
    "id": ARGS.id,
    "name": "The Mission Hall",
    "description": "A great round hall under a coffered dome, lit by a shaft of sunlight through its oculus. Eight guilds keep booths round the ring, and their mission-givers send heroes out through the portal on the dais into Oakhaven and back.",
    "author": {"name": ARGS.author, "owner": ARGS.owner},
    "version": "1.0.0",
    "api_version": "0.1",
    "scene": "scene.json",
    "spawn": "default",
    "budgets": {"triangles": 150000, "objects": 64, "texture_size": 2048, "texture_bytes": 100663296,
                "lights": 12, "package_bytes": 16777216, "audio_bytes": 1048576, "script_bytes": 0},
    "features": ["sky", "fog", "objects", "lights", "sounds", "portals", "npcs", "quests", "animation"],
    "license": "CC0-1.0",
    "credits": [
        {"files": ["assets/hall.glb"], "author": "Built with Blender by mission_hall.py from the iamar kit's material library and, with --props, Quaternius Fantasy Props MegaKit props", "license": "CC0-1.0", "source": "https://github.com/iamar-ai/iamar-kit, https://quaternius.com"},
    ],
}
os.makedirs(PKG, exist_ok=True)
with open(os.path.join(PKG, "scene.json"), "w") as f:
    json.dump(scene, f, indent=1)
    f.write("\n")
with open(os.path.join(PKG, "manifest.json"), "w") as f:
    json.dump(manifest, f, indent=2)
    f.write("\n")
print("SCENE", len(npcs), "npcs", len(Q), "quests", len(objects), "objects", len(lights), "lights")
