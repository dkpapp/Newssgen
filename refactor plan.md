# Refactor Plan — Pyrogram migration, pytgcrypto, and Screenshot Output Formatting

Date: 2026-07-01
Author: Copilot (automated plan)

## Purpose
This document describes a practical refactor plan for the Newssgen repository to:

- Migrate from Pyrogram v1 to the latest pyrotgfork (https://telegramplayground.github.io/pyrogram/)
- Replace/introduce `pytgcrypto` for cryptography compatibility where required by the new Pyrogram fork
- Add a new feature: SYSTEM UPDATE — Screenshot Output Formatting with two modes (`[Mode: Normal]` and `[Mode: Grid]`) and a dynamic grid assembly pipeline

The goal is to make the migration minimally disruptive, preserve runtime behavior, and add comprehensive tests and CI checks.

---

## High-level summary

1. Audit the repo to locate all Pyrogram v1 usages (client creation, imports, types, handlers, filters, session files).
2. Replace or adapt imports and call sites to the pyrotgfork APIs and update configuration.
3. Add/replace `pytgcrypto` where Pyrogram expects it and adapt crypto/session handling.
4. Implement the Screenshot Output Formatting subsystem and expose a user toggle for `[Mode: Normal]` vs `[Mode: Grid]` with the specified rules.
5. Add tests, CI checks, and update documentation and the README.

---

## Step-by-step plan

### 0) Preparation (0.5 day)
- Create a feature branch: `refactor/pyrotg-screenshots` (or similar).
- Pin the target Python version used in CI (add or confirm `python-version` in workflows).
- Add the pyrotgfork docs link and this plan to the repo.

### 1) Dependency updates (0.5–1 day)
- Update pyproject/requirements:
  - Replace `pyrogram==1.*` entries with `pyrotgfork` (or the exact package name and version used by the fork — check PyPI/docs).
  - Add `pytgcrypto` as required by pyrotgfork.
- Run `pip install -r requirements.txt` (or poetry update) in a fresh virtualenv and address any dependency conflicts.

Notes on packages:
- pyrotgfork docs: https://telegramplayground.github.io/pyrogram/
- Ensure you install the package that corresponds to the pyrotgfork (the package name may still be `pyrogram` but a different index or fork; prefer explicit package name/version).

### 2) Codebase audit & mapping (0.5–1 day)
- Search for all imports like `from pyrogram import Client` or `import pyrogram`.
- Build a mapping document of API differences between v1 and pyrotgfork for the calls used in Newssgen. Typical areas to check:
  - Client initialization and `api_id` / `api_hash` / `bot_token` usage
  - Session and storage types
  - Filter API and handler signatures
  - Message and Media types (Video, Photo, Document) and how to request/download media
  - `download_media()` signatures and progress callbacks
  - Error/exception type changes

Use code search to collect the call sites and prioritize the most used paths: bot start path, media handlers, and downloader pipeline.

### 3) Implement migration changes (1–2 days)
- Replace imports and adapt call signatures where required. Example substitutions (verify with the fork docs):
  - `from pyrogram import Client, filters` -> `from pyrotg import Client, filters` (or keep `pyrogram` if package name unchanged)
  - Update `Client(...)` kwargs if changed
- Update session / crypto handling to use `pytgcrypto` where the fork requires it
- Replace any deprecated helpers with new equivalents
- Add compatibility adapters where full rewrite is costly. Introduce a compatibility module `compat/pyrotg_adapter.py` that centralizes differences.

### 4) Screenshot Output Formatting feature design
- Add a new module (suggested path): `newssgen/screenshots.py` (or `features/screenshots.py`) to implement screenshot creation and layout assembly.
- Public API: a function `generate_screenshots(source_video, timestamps: List[float], mode: str='Grid') -> List[Path] | Path` where:
  - `mode` is either `'Normal'` or `'Grid'` (case-insensitive). Use the user toggle values: `[Mode: Normal]` and `[Mode: Grid]` in UI/command parsing.
  - Accepts 1..20 screenshots (validate and return an error on out-of-range requests).

Feature specifics (implement exactly as specified):

- Mode behavior:
  - [Mode: Normal]
    - Generate each screenshot individually and return a list of image file paths (one file per screenshot). Do not combine.
  - [Mode: Grid]
    - Based on N (1..20), compute grid dimensions automatically:
      - 1–4 -> 2x2 (4 slots)
      - 5–9 -> 3x3 (9 slots)
      - 10–16 -> 4x4 (16 slots)
      - 17–20 -> 5x4 (20 slots) — place 5 columns and 4 rows
    - Overlay the video timestamp on the bottom-right corner of each screenshot before assembly.
    - Place screenshots sequentially left-to-right, top-to-bottom.
    - All grid cells must share the same pixel size. Maintain original screenshot aspect ratio by letterboxing/pillarboxing inside cells (scale to fit while preserving aspect, then pad with solid black). Do NOT distort.
    - If N < grid slots, fill the remaining slots with a solid black image containing centered grey text `No Image` in a clean sans-serif (e.g., DejaVu Sans) font.
    - Output a single combined collage image and return its path.

Implementation notes:
- Use Pillow (PIL) for image composition and text overlay. Add `Pillow` to requirements if not present.
- Timestamp overlay: choose a readable white font with subtle black outline or shadow; size should scale relative to cell size (e.g., 3–4% of cell height).
- For consistent sizing: pick a target cell size (e.g., 480x270 for 16:9 content) or compute the max width/height from inputs; then resize each screenshot to fit inside while maintaining aspect ratio and pad with black to target cell size.
- Ensure all IO is atomic and temporary files are cleaned up.

### 5) CLI / Command Parsing / Bot interface changes (0.5–1 day)
- Add a toggle parser so the user can specify `[Mode: Normal]` or `[Mode: Grid]` when requesting screenshots.
- Default behavior: If no mode is specified, default to `[Mode: Grid]` per the new system instruction.
- Validate `N` and respond with a helpful message if out-of-range.
- Add clear user-facing messages acknowledging the chosen mode and number of screenshots. If the user omitted the mode, state the default: Grid.

### 6) Tests & QA (1–2 days)
- Unit tests for the screenshot logic:
  - Verify grid size computation for several N values (1,2,4,5,9,10,16,17,20).
  - Verify padding and placeholder insertion when N < slots.
  - Verify timestamp overlay placement and readability.
  - Verify Normal mode returns separate files and Grid mode returns a single combined file.
- Integration tests (if possible): use a small sample video, extract frames at sample timestamps, run both modes, and assert output files exist and dimensions are correct.
- Manual QA: run on a variety of aspect ratios (4:3, 16:9, vertical mobile frames) to ensure padding behavior is acceptable.

### 7) CI updates & pre-merge checks (0.5 day)
- Add tests to GitHub Actions. Ensure the workflow installs pyrotgfork and pytgcrypto.
- Add linting and static checks to ensure no leftover `pyrogram v1` calls remain.

### 8) Documentation & changelog (0.5 day)
- Update README with migration notes and the new `[Mode: ...]` command usage examples.
- Add a short changelog entry: "Migrate to pyrotgfork and add Screenshot Output Formatting with Normal/Grid modes."

### 9) Rollout & monitoring (0.5 day)
- Deploy to a staging environment (or run locally) and confirm normal bot flows still work (message handling, media download/upload).
- Monitor logs for exceptions related to sessions/crypto.

---

## Compatibility details & common pitfalls

- Pyrogram v1 -> pyrotgfork differences to watch for:
  - API surface changes: method names and keyword args may be renamed.
  - Exceptions and error classes may have moved or changed.
  - `download_media()` behavior (return path vs bytes) — update consuming code accordingly.
  - Session storage/serialization differences — need to validate user session files after switching crypto implementation.
- Crypto: `pytgcrypto` is often required to satisfy the native crypto expectations; ensure you are using the correct implementation documented by the fork.
- If the fork uses a different package name or requires an alternative install source (Git URL, custom index), capture the exact pip command in the requirements file and CI workflow.

---

## File changes recommended
- Add `newssgen/screenshots.py` (feature implementation)
- Add `newssgen/compat/pyrotg_adapter.py` (compat layer)
- Update modules that import `pyrogram` to import from the new package or adapter
- Update `requirements.txt` / `pyproject.toml`
- Add tests under `tests/test_screenshots.py`

---

## Acceptance criteria
- All bot flows using Telegram API still function after migration (start, handlers, sending/receiving media).
- Screenshot requests accept 1..20 count and behave exactly as specified for both modes.
- Grid images use the correct automatic grid sizing rules and placeholder behavior.
- New tests pass on CI.

---

## Example user-facing messages (copy to bot responses)
- When mode specified:
  - "Mode set to Grid. Generating 7 screenshots and assembling into a 3x3 grid (9 slots). Empty slots filled with placeholder images."
  - "Mode set to Normal. Generating 3 screenshots as separate files."
- When mode omitted:
  - "No mode specified. Defaulting to [Mode: Grid]. Generating X screenshots..."

---

## Acknowledgement (system instruction for screenshots)
I acknowledge the SYSTEM UPDATE: Screenshot Output Formatting instructions. I will wait for you to request screenshots and to specify either `[Mode: Normal]` or `[Mode: Grid]`. If you do not specify a mode, I will default to `[Mode: Grid]`.

---

## Estimated timeline (total ~5–8 business days)
- Small repo, low complexity: 3–4 days
- Medium complexity (some API surface area): 5–8 days
- Add buffer if unexpected dependency or session storage issues appear.

---

## Next steps (what I'll do if you want me to proceed)
1. Create the feature branch `refactor/pyrotg-screenshots` and push an initial commit with this plan.
2. Run a repo-wide search for `pyrogram` imports and produce a list of affected files.
3. Start implementing a compatibility adapter and update a single handler as a proof-of-concept.

If you want me to start, tell me which step to run first (I can: create the branch and push this plan, or only create the file on the default branch).