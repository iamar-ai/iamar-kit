# Question sets per world type (job I3)

One file per type of the router in `../PROTOCOL.md` section 4: `town`, `nature`, `interior`, `social`, `quest`, `shop`, `education`, `gallery`, `event`, `other`. Each has the type-specific questions (stage 4) with defaults and examples, traps and checks, reuse hints, what goes into the brief, and a persona dry run. `examples/<type>/` holds the approved worked brief (`brief.json` + `world.brief.md`). Test: `python3 kit/tests/interview/types_test.py`.
