# Current Task

Verify the Pearl REST API prefix and auth against one demo device, then build `pearl-episodes pull`.
Acceptance: `uv run pearl-episodes list <recorder_id>` returns real rows from a demo device; `pull` writes
new files to `recordings/<serial>/` and skips files already pulled.
