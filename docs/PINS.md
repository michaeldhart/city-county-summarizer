# Pins

Briefs pinned to the front page. A pinned brief is **always included** when the
front page is built, even if the ranking would have cut it — but it is *not*
moved to the top. It sits wherever its rank puts it, so pinning keeps something
on the page without faking its importance.

Add a row to pin. Delete the row to unpin. `ccs front-page` reads this file at
runtime, the same way the app reads `SCOPE.md`.

Two things worth knowing:

- **A pin beats the count, not the date window.** Once a brief's meeting falls
  outside the window, the pin stops mattering. To hold something longer, build
  with a wider `--window-days` rather than expecting the pin to resurrect it.
- **Pins are matched on the brief id**, which is a hash of the headline. If that
  meeting is re-briefed and the headline changes, the id changes with it and the
  pin dangles — `ccs front-page` warns rather than silently pinning something
  you never read. Copy the new id in, or drop the row.

Brief ids are printed by `ccs front-page --list-briefs`.

| Brief | Headline (for your reference — not matched on) |
|---|---|
| | |
