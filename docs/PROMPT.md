# Claude Code kickoff prompt

Paste this into a fresh `claude` session in this repository.

---

Start by reading, in this order, and do not write code until you have:

1. `CLAUDE.md`, `.claude/PROJECT_CONTEXT.md`, `docs/ARCHITECTURE.md`.
2. The four documents and the model on Google Drive (use the Google Drive connector; links in
   `docs/context/README.md`):
   - Epiphan-Physical-AI-Capture-Opportunity-Brief.pdf, the market and Epiphan's play
   - Epiphan-Physical-AI-Capture-At-A-Glance.pdf, the two-page version
   - Epiphan-Physical-AI-Lab-Proof-of-Concept.pdf, what the lab test measures and the open product questions
   - Epiphan-Physical-AI-Capture-Pro-Forma.xlsx, the three-year scenario model (read the Read me and Inputs sheets)
3. The Open X-Embodiment README (github.com/google-deepmind/open_x_embodiment) and the dataset sheet it links,
   with attention to how episodes are stored (RLDS) and which datasets use two or more exterior cameras.

Then write, before any code, a short plan in `.claude/PLAN.md` that answers: what one packaged episode from a
Pearl-2 looks like on disk in LeRobot layout and in RLDS; which Pearl REST calls produce it and which
documentation page confirms each call; how a take that rolled over into several 500 MB files is stitched; what
the manifest carries that the product does not; and how an operator session over Epiphan Edge MCP (start, wait,
stop, pull, package) is logged. List what you could not confirm from documentation as open questions for
Product, and do not guess at them.

Constraints you must keep: no claim about multi-camera alignment or timing anywhere (record `clock_source`
only); no OpenAI; Python 3.12 async with type hints and `uv`; every Epiphan Edge write asks first and names the
device and channel; the visible fleet is Epiphan's shared demo team, so record only when I say so in the
session; recordings and internal documents never go to GitHub.

When the plan is written, stop and show it to me. We build after I have read it.
