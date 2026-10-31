# Audit method

Scope: all learner decisions in eight current White/Black opening-training PGNs, including OnlyMove snapshots and private Chessable packs. Historical reading games contain intentional mistakes and are not mandatory-move decisions. Strategy and ending courses need separate audits.

Deduplication uses board placement, side, castling rights, legal en-passant rights and chosen UCI move. Scores favor the learner at the root. A move outside MultiPV 3 receives a forced-root search. All reported PVs are legality-checked.

The first pass is a bounded screen, not deep proof. Deeper selection includes a loss of at least 0.50 pawns or a selected position at or below -1.00 for the learner (even if the current move is best), plus the seven requested Black branch anchors. The target is depth 24 with actual depths and time-capped exceptions recorded. Search uncertainty means a small centipawn difference is not a unique-move theorem.

Publication uses an explicit allowlist. Systematic book-derived libraries stay private. Do not make the entire working project public by changing visibility.

The audit makes no paid calls, live course resets or automatic repertoire rewrites. Corrections are separate proposals with source and engine provenance.
