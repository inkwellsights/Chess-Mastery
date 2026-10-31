# Chess Mastery: practice routine and local audit tools

A personal chess-training project using opening recall, strategy, endings and slow-game review.

## Public/private split

This repository contains the routine, original audit code, methodology and aggregate audit results. It excludes books, scans, OCR, all course PGNs/annotations, browser/account backups, personal games and credentials. Leaving out PDFs alone does not make a reconstructed book course appropriate for public redistribution.

Private course content is backed up separately. This public folder is not a complete restore of Chessable or OnlyMove content or repetition history.

## Daily use

Import weekly_chess_routine.csv into Google Sheets. It repeats seven days with an 11-hour planned base and three slow games. Optional extra study is not in the base. The routine refers to private Chessable chapters, which are not distributed here.

## Local engine audit

Python and Stockfish 19 are required. Install requirements.txt. The engine binary is not bundled.

The audit tool is a snapshot of the personal workflow, not a ready-made repertoire. Its default SOURCES paths point to excluded private study folders. To reuse it, edit SOURCES to reference your own PGNs and learner side (True for White, False for Black), set ENGINE to your own Stockfish 19 executable, and choose an OUT folder for your run. All paths are relative to the repository root unless absolute. Then run:

    python tools/audit_opening_courses_20261031.py all

Use prepare, screen, deep or report to resume phases separately. Do not change PGNs inside an existing audit run; the input inventory is hash-locked.

The full fixed-node screen uses Stockfish 19 MultiPV 3, 500,000 nodes per root. Two engines use three threads each. A chosen move outside the top three gets a separate 500,000-node search. The deeper pass targets depth 24, capped at 90 seconds per root. The report states actual depth and does not label capped searches depth-24 complete.

No external API or API key is required. Engine findings cannot establish book completeness, teaching quality, publication rights or a promised rating/title outcome.

## Verified snapshot: 2026-10-31

- 1,223 learner decisions screened across 1,212 positions with Stockfish 19, MultiPV 3.
- 20 deeper checks completed depth 24. Nine improvement proposals remain pending and were not automatically applied.
- Eleven cross-course choice differences were addressed in the private OnlyMove repertoire: nine reachable choices changed, one already compatible, one superseded branch retired. After reload and native re-export, 309 unchanged review cards, settings, activity and games were verified preserved.
- The engine audit predates that alignment. It is not a fresh engine audit of the updated live repertoire. See audit-summary.json for the original run snapshot; its publication flag describes that earlier run, not this repository's current visibility.
- Book conversion is best effort and incomplete. Strategy/endings were outside the opening engine audit. No title or rating outcome is promised.

The private courses are not available from this repository. This is a public tools-and-methodology release, not a complete backup of the study library. You can adapt the routine and audit workflow to material you have permission to use. Public availability alone does not grant rights to redistribute the excluded books or courses.
