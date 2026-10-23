"""Recipe measure (one recipe per file; kit/recipes/make_recipes.py collects them, sorted by ORDER)."""

ORDER = 390
r("measure", "Measure on the low-end machine", "measurement",
  "Every change is measured before and after on Amber-class hardware, with fixed-view screenshots compared.",
  "Always.", ["Run perf in the busiest view and the widest view.", "Compare fixed-view screenshots before and after.", "Report the numbers."], {},
  "perf, preview.", "Time.", "oakhaven tools/perf_probe.gd, autotest frame-time metrics", "manual")
