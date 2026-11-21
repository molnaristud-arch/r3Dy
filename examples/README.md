# Real runs of the agents

Each folder is one real scan processed by the controller agent (`agent/controller.py`). The photos are not included (size); everything the agents produced is:

| file | what it is |
|---|---|
| `transcript.txt` | the decisions, tool calls and results, one line each (Hungarian, as shown live in the terminal) |
| `agent_log.jsonl` | the raw event log, including the model's summarised reasoning (`kind: "gondolat"`) |
| `qa.json` | the last verdict of the independent quality-check agent (`agent/qa.py`) |
| `preview/view_0..3.png` | renders of the finished model, front then every 90° |

## Scans

- **`scan-1-handheld/`** – 38 photos, phone held by hand, background sheet held by hand. All 38 registered, but the model was tilted and had background stuck to it. The quality agent said *broken* (`hibas`); the controller masked the background and rebuilt, the verdict improved to *suspect* (`gyanus`), and it published the model (15 steps, ~10 min).
- **`scan-2-fixed-phone/`** – 76 photos from a fixed phone at two heights; all 76 registered into one model with clearly sharper geometry. The controller run in `transcript.txt` was stopped during its second reconstruction, so it has no `finish` line; the model is from its first reconstruction.

**Disc removal (later pass, both scans).** After these runs we added `remove_disc` to the agent's `cleanup_model` tool: it finds the printed turntable disc as the dominant plane (RANSAC), levels the model on it, takes the **true scale from the disc's known 19 cm diameter** and cuts the disc off. Both scans were then re-processed with the agent's own tools (`agent/tools.py <scan> cleanup_model '{"remove_disc": true}'`, `render_preview`, `quality_check`) – the `preview/` images and `qa.json` are from that pass, the transcripts are from the original runs.

| | tilt corrected | size from the disc | quality agent |
|---|---|---|---|
| scan 1 | 38.5° | 6.2 × 6.5 × 1.0 cm | `gyanus` |
| scan 2 | 92.1° | 6.3 × 7.8 × 1.2 cm | `gyanus` |

(A real Arduino Uno is 6.9 × 5.3 cm, ~7.5 cm with the USB socket.) Both are live: https://r3dy-web.vercel.app

Verdict words in the logs: `jo` = good, `gyanus` = suspect, `hibas` = broken. Log tags: `vezérlő` = controller, `eszköz` = tool call, `eredmény` = result, `gondolat` = reasoning summary, `kész` = finished.
