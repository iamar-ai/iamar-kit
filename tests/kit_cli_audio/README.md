# Kit audio-device initialization contract

The kit's source-Godot and downloaded-browser launchers explicitly select
`--audio-driver Dummy` before every engine/user argument separator. This applies
to noninteractive kit processes, including finite preview/perf/image captures and
headless serving. It avoids trying to open an output device that the job does not
need. Ordinary direct game launch, project settings, system drivers and audio
asset validation are unchanged. Blender paths receive no Godot option.

Run `python tests/kit_cli_audio/argv_test.py`. It executes the actual thin Bash
launcher with an inert argv recorder instead of any engine. It checks source,
explicit downloaded and auto-discovered downloaded routes; one browser invocation
per command; spaces; explicit current-directory forwarding; headless/render policy;
and the Dummy audio prefix. Windows release behavior is covered separately by the
Wine acceptance run, not claimed by this argv-only fixture.

Run `node tests/kit_cli_audio/supervised_test.mjs /path/to/iamar/backend` against
an existing backend checkout. It uses the unchanged real process supervisor and
Bash launcher with an inert Python recorder. Warnings stay allowed; actual
native-shaped SCRIPT ERROR and ERROR prefixes, including the prior ALSA-shaped
error, remain refused. The correction prevents unnecessary device initialization;
it does not add an error exception or suppress logs.

These fixtures do not execute Godot, a renderer, a package opener or real signing,
audio or networking. They are launch-contract/component evidence.
Actual graphical authoring verification must use its separately authorized gate.
