# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Trajectory tracer for **billard français (carambole)** — 3 balls (white, yellow, red) on a blue cloth, top-down view. The current target is a recorded mp4 (`datas/video.mp4`); the long-term target is a live NDI feed from OBS. Architecture is intentionally modular so the capture source can be swapped without touching detection/tracking/rendering.

## Run

```powershell
python src/main.py                # uses datas/video.mp4 by default
python src/main.py <other.mp4>    # arbitrary file
```

At startup a window opens on the first frame — drag a rectangle around the playing surface (inside the cushions) and press **Enter** to validate. Then during playback:

- **Space** — pause/resume
- **R** — redraw the play-zone rectangle (also clears trails). Needed because the source video starts with a grey intro screen.
- **C** — clear trails manually
- **Q** / **Esc** — quit

## Architecture

Pipeline per frame (`src/main.py` orchestrates):

1. **`capture.VideoSource`** — thin wrapper over `cv2.VideoCapture`. The interface (`read`, `release`, `fps`, `width`, `height`) is what will be reimplemented for an NDI source later; nothing else in the code reads from cv2 directly for video I/O.
2. **`table.select_table_rect` / `rect_to_mask`** — user-drawn rectangle on the first frame, turned into a binary ROI mask. Auto-detection of the blue cloth was tried and rejected (too brittle).
3. **`detector.detect_balls(frame, roi_mask)`** — HSV thresholding per color (`HSV_RANGES`) → morphology → contour selection. Filters used to reject the bois/bandes and shirt of the player: ROI mask, radius bounds (`MIN_RADIUS`/`MAX_RADIUS`), circularity ≥ `MIN_CIRCULARITY`. Red uses two H-ranges since it wraps around 0. Returns `{color: (x, y, r)}`.
4. **`tracker.Trajectories`** — per-ball deque of positions. Motion detection uses the last `MOTION_WINDOW` frames; when total inter-frame displacement of every tracked ball stays under `MOTION_PIX_THRESHOLD`, balls are considered still. After `STILL_HOLD_SECONDS + KEEP_AFTER_STILL_SECONDS` seconds of stillness the trails auto-clear (end of point). Drawing applies a moving-average smoothing of width `SMOOTH_WINDOW` to the polyline only — raw points stay untouched.

All tunable thresholds live at the top of `detector.py` and `tracker.py`. Adjust there rather than threading parameters through call sites.

## Notes for future changes

- The play-zone rectangle is the primary defense against false positives outside the table. If detection of a color breaks, first check whether the ball is inside the ROI before widening HSV ranges.
- `Erreurs/` holds screenshots of past detection failures (shirt detected as white, cushion detected as red) — useful as regression cases when tuning.
- No tests, no lint config, no requirements.txt yet. Dependencies in use: `opencv-python`, `numpy`.
