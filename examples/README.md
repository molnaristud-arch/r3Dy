# Real runs of the agents

Each folder is one real scan processed by the controller agent (`agent/controller.py`). The photos are not included (size); everything the agents produced is:

| file | what it is |
|---|---|
| `transcript.txt` | the decisions, tool calls and results, one line each (Hungarian, as shown live in the terminal) |
| `agent_log.jsonl` | the raw event log, including the model's summarised reasoning (`kind: "gondolat"`) |
| `qa.json` | the last verdict of the independent quality-check agent (`agent/qa.py`) |
| `preview/view_0..3.png` | renders of the finished model, front then every 90° |

## Scans

- **`scan-1-handheld/`** – 38 photos, phone held by hand, background sheet held by hand. All 38 registered, but the model was tilted and had background stuck to it. The quality agent said *broken* (`hibas`); the controller masked the background and rebuilt, the verdict improved to *suspect* (`gyanus`), and it published the model (15 steps, ~10 min). Live: https://r3dy-web.vercel.app
- **`scan-2-fixed-phone/`** – 76 photos from a fixed iPhone at two heights; all 76 registered into one model with clearly sharper geometry.

Verdict words in the logs: `jo` = good, `gyanus` = suspect, `hibas` = broken. Log tags: `vezérlő` = controller, `eszköz` = tool call, `eredmény` = result, `gondolat` = reasoning summary, `kész` = finished.
