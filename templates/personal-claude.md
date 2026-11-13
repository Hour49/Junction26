# Global instructions (<your name>)

Your own rules. Where they are more specific than the team block below (your wait tool, models, machines,
production systems), they win; where both cover the same thing, the stricter rule wins.

## Who and where
- Owner: <name> (GitHub <login>). Team Hour49, Junction 2026. Teammates' gh logins: Bogzx,
  Cucuteanu-Tudor-912, bbeatricecretu, madabotos.
- Machine: <OS, cores, RAM, GPU>. Never fill the RAM: one heavy job at a time, capped
  (`nice -n 15 systemd-run --user --scope -p MemoryMax=4G <cmd>`).
- Claude accounts: <one, or: a second one via `claude-acc 2`; its panes get `--env CLAUDE_CONFIG_DIR=$HOME/.claude-2`>.
