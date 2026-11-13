#!/usr/bin/env bash
# setup.sh: install the Hour49 agent setup for this user (docs/TEAM-AGENTS.md section 2). Safe to rerun.
#   tools/setup.sh            do everything
#   tools/setup.sh --offline  skip the steps that download (handoff hook, herdr skill)
# It changes only files under $HOME, and backs up each file before changing it (<file>.bak-<time>):
#   ~/.claude/CLAUDE.md       team rules between hour49-team markers; the rest of the file is kept
#   ~/.claude/settings.json   attribution off, skipDangerousModePermissionPrompt (other keys kept)
#   ~/.local/bin              symlinks: board, claude-acc, waitw.sh
#   ~/.claude/hooks           context-handoff hook (Bogzx/claude-context-handoff install.sh)
#   ~/.claude/skills/herdr    herdr skill (only if missing)
#   herdr's claude integration (herdr integration install claude), if herdr is installed
# It never installs system packages; it lists what is missing instead.
set -euo pipefail
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
offline=0
[ "${1:-}" = "--offline" ] && offline=1
stamp="$(date +%Y%m%d-%H%M%S)"
claude_dir="$HOME/.claude"
bin="$HOME/.local/bin"
mkdir -p "$claude_dir" "$bin"

say() { printf '%s\n' "$*"; }
backup() { [ -e "$1" ] && cp -p "$1" "$1.bak-$stamp" && say "  backup: $1.bak-$stamp"; return 0; }

say "== prerequisites"
missing=()
for cmd in claude gh git python3 jq herdr uv; do
  command -v "$cmd" >/dev/null 2>&1 || missing+=("$cmd")
done
if [ ${#missing[@]} -gt 0 ]; then
  say "  missing: ${missing[*]} (install them, see docs/TEAM-AGENTS.md section 2, then rerun)"
else
  say "  all present"
fi
case ":$PATH:" in *":$bin:"*) ;; *) say "  note: $bin is not on PATH; add it (e.g. in ~/.profile) and log in again" ;; esac

say "== ~/.claude/CLAUDE.md"
python3 - "$claude_dir/CLAUDE.md" "$repo/templates/personal-claude.md" "$repo/templates/team-claude.md" "$stamp" <<'PY'
import shutil, sys
from pathlib import Path
target, personal, team, stamp = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]
BEGIN, END = "<!-- hour49-team:begin -->", "<!-- hour49-team:end -->"
block = f"{BEGIN}\n{team.read_text().rstrip()}\n{END}\n"
if not target.exists():
    target.write_text(personal.read_text().rstrip() + "\n\n" + block)
    print(f"  created {target}: fill in the <...> placeholders in 'Who and where'")
    raise SystemExit
old = target.read_text()
if BEGIN in old and END in old:
    head, rest = old.split(BEGIN, 1)
    new = head + block + rest.split(END, 1)[1].lstrip("\n")
else:
    new = old.rstrip() + "\n\n" + block
if new == old:
    print("  team rules already up to date")
else:
    shutil.copy2(target, target.with_name(f"{target.name}.bak-{stamp}"))
    target.write_text(new)
    print(f"  team rules {'updated' if BEGIN in old else 'appended'} (backup {target.name}.bak-{stamp})")
PY

say "== ~/.claude/settings.json"
python3 - "$claude_dir/settings.json" "$stamp" <<'PY'
import json, shutil, sys
from pathlib import Path
path, stamp = Path(sys.argv[1]), sys.argv[2]
before = json.loads(path.read_text()) if path.exists() else {}
after = json.loads(json.dumps(before))
after["attribution"] = {**after.get("attribution", {}), "commit": "", "pr": "", "sessionUrl": False}
after["skipDangerousModePermissionPrompt"] = True
if after == before:
    print("  already up to date")
else:
    if path.exists():
        shutil.copy2(path, path.with_name(f"{path.name}.bak-{stamp}"))
    path.write_text(json.dumps(after, indent=2) + "\n")
    print("  attribution off, skipDangerousModePermissionPrompt on")
PY

say "== ~/.local/bin"
for tool in board claude-acc waitw.sh; do
  link="$bin/$tool"
  if [ -e "$link" ] && [ ! -L "$link" ]; then
    say "  skipped $tool: $link exists and is not a symlink"
  else
    ln -sfn "$repo/tools/$tool" "$link"
    say "  $tool -> $repo/tools/$tool"
  fi
done

if [ "$offline" = 1 ]; then
  say "== offline: skipped the handoff hook and the herdr skill"
else
  say "== context-handoff hook"
  src="$HOME/.local/share/claude-context-handoff"
  if [ -d "$src/.git" ]; then git -C "$src" pull -q --ff-only; else git clone -q https://github.com/Bogzx/claude-context-handoff.git "$src"; fi
  (cd "$src" && ./install.sh | sed 's/^/  /')

  say "== herdr skill"
  skill="$claude_dir/skills/herdr/SKILL.md"
  if [ -e "$skill" ]; then
    say "  present, left alone"
  else
    mkdir -p "$(dirname "$skill")"
    curl -fsSL https://raw.githubusercontent.com/herdrdev/herdr/master/skills/herdr/SKILL.md -o "$skill"
    say "  installed $skill"
  fi
fi

if command -v herdr >/dev/null 2>&1; then
  say "== herdr claude integration"
  herdr integration status 2>/dev/null | grep '^claude:' | sed 's/^/  /' || true
  if ! herdr integration status 2>/dev/null | grep -q '^claude: current'; then
    herdr integration install claude | sed 's/^/  /'
  fi
fi

say "== done. Next: docs/TEAM-AGENTS.md section 3 (checks)."
