# Documentation

Rules for the pages under `docs/`, built with Zensical (`zensical.toml`). The language and privacy rules of the root
`AGENTS.md` apply: English only, never real user data.

## Text
- A page holds the decisions and their reason, one sentence per idea. What the code already says (paths, settings,
  every edge case) stays in the code; the page names the issue that built it (#261) for the rest.
- Visual first, text after: a section opens on its overview diagram, then the detail. A reader who stops after the
  first diagram still has the essential.
- The happy path apart from the failures: a flow shows the way through, and the failures get their own section or
  diagram, with what catches each one.
- An accepted risk is written next to what it concerns, with the issue that would close it.

## Diagrams
- **Mermaid** for an overview: it scales to the text column. Vertical (`flowchart TB`) beyond 4 or 5 nodes, as a wide
  `LR` one shrinks until unreadable; short labels, as long ones stretch the boxes.
- **Swimlanes** (`<div class="seq">`, rendered by `javascripts/sequence.js`, its format in the file's header comment)
  for a flow across programs, step by step. Wider than the column, they fold under the section they detail
  (`??? example "Title"`, the block indented by 4 spaces); their Expand button shows them over the page.
- Check every new or changed diagram in the browser (`make docs-serve`) before pushing, not only `make docs-build`.
