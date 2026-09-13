#!/bin/bash
# Bruk: bash publish-macos.sh 2.0.0 [sti/til/ki-varslinger-2.0.0.zip]
# Kjorer pa macOS med Bash 3.2+, Git, GitHub CLI, Python 3 og rsync.
set -euo pipefail

V="${1:-}"
if [[ ! "$V" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Bruk: bash $0 2.0.0 [sti/til/ki-varslinger-2.0.0.zip]" >&2
  exit 1
fi
GH_REPO="SebastianKristo/ki-varslinger"
REPO="$HOME/Documents/HomeAssistant/ki-varslinger"
ZIP="${2:-$HOME/Downloads/ki-varslinger-$V.zip}"
TAG="v$V"
for CMD in git gh python3 rsync; do
  command -v "$CMD" >/dev/null 2>&1 || { echo "Mangler $CMD. Installer med Homebrew: brew install git gh python rsync" >&2; exit 1; }
done
[ -f "$ZIP" ] || { echo "Finner ikke $ZIP" >&2; exit 1; }
gh auth status --hostname github.com >/dev/null 2>&1 || { echo "Kjor gh auth login forst." >&2; exit 1; }
# Git bruker den allerede innloggede GitHub CLI-en for HTTPS-autentisering.
git_gh() { git -c credential.helper= -c 'credential.helper=!gh auth git-credential' "$@"; }

TMP_WORK="$(mktemp -d "${TMPDIR:-/tmp}/ki-varslinger.XXXXXX")"
trap 'rm -rf -- "$TMP_WORK"' EXIT
# Pakk bare ut sikre relative filer under den forventede rotmappen.
python3 - "$ZIP" "$TMP_WORK" "$V" <<'PY'
import json, pathlib, stat, sys, zipfile
archive, destination, version = sys.argv[1:]
with zipfile.ZipFile(archive) as z:
    if sum(i.file_size for i in z.infolist()) > 50 * 1024 * 1024:
        raise SystemExit('ZIP-pakken er uventet stor.')
    for i in z.infolist():
        p = pathlib.PurePosixPath(i.filename)
        if p.is_absolute() or '..' in p.parts or not p.parts or p.parts[0] != 'ki-varslinger' or '.git' in p.parts or '\\' in i.filename:
            raise SystemExit('Ugyldig filsti i ZIP-pakken: ' + i.filename)
        if stat.S_ISLNK(i.external_attr >> 16):
            raise SystemExit('Symbolske lenker er ikke tillatt i pakken.')
    z.extractall(destination)
root = pathlib.Path(destination) / 'ki-varslinger'
manifest = json.loads((root / 'custom_components/ki_notifications/manifest.json').read_text())
if manifest['version'] != version or manifest['domain'] != 'ki_notifications':
    raise SystemExit('Versjon eller domenenavn i pakken stemmer ikke.')
for required in ('hacs.json', 'README.md', 'RELEASE.md', 'LICENSE'):
    if not (root / required).is_file():
        raise SystemExit('Mangler ' + required)
PY
SOURCE="$TMP_WORK/ki-varslinger"

mkdir -p "$(dirname "$REPO")"
if [ ! -d "$REPO/.git" ]; then
  if [ -e "$REPO" ]; then
    echo "$REPO finnes allerede, men er ikke et Git-repo. Flytt den manuelt forst." >&2
    exit 1
  fi
  git_gh clone "https://github.com/$GH_REPO.git" "$REPO"
fi
cd "$REPO"
ORIGIN="$(git remote get-url origin)"
case "$ORIGIN" in
  "https://github.com/$GH_REPO.git"|"https://github.com/$GH_REPO"|"git@github.com:$GH_REPO.git"|"ssh://git@github.com/$GH_REPO.git") ;;
  *) echo "Feil origin i $REPO: $ORIGIN" >&2; exit 1 ;;
esac
[ -z "$(git status --porcelain)" ] || { echo "Repoet har lokale endringer. Commit eller stash dem forst." >&2; exit 1; }
git_gh fetch origin --tags
if git rev-parse --verify "refs/tags/$TAG" >/dev/null 2>&1; then
  echo "$TAG finnes allerede. Bruk en ny versjon; eksisterende tagger overskrives ikke." >&2
  exit 1
fi
if git show-ref --verify --quiet refs/remotes/origin/main; then
  git switch main
  git merge --ff-only origin/main
  [ "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" ] || { echo "Lokal main har upubliserte commits. Handter dem forst." >&2; exit 1; }
else
  # Tillat ogsa et helt tomt repo, men ikke en annen eksisterende hovedgren.
  if git rev-parse --verify HEAD >/dev/null 2>&1; then
    echo "Fant ingen origin/main i et eksisterende repo. Kontroller grenene manuelt." >&2
    exit 1
  fi
  git symbolic-ref HEAD refs/heads/main
fi
# Unnga aa endre metadata eller filer forst og deretter oppdage manglende Git-identitet.
git var GIT_AUTHOR_IDENT >/dev/null
[ "$(gh repo view "$GH_REPO" --json isPrivate --jq .isPrivate)" = false ] || { echo "Repoet ma vaere offentlig for vanlig HACS-installasjon." >&2; exit 1; }

# Ved oppgradering slettes kun utdaterte filer i integrasjonens egen mappe.
# Andre mapper/filer i repoet beholdes.
mkdir -p custom_components/ki_notifications
rsync -a --delete "$SOURCE/custom_components/ki_notifications/" custom_components/ki_notifications/
rsync -a --exclude '.git' --exclude 'custom_components' "$SOURCE/" "$REPO/"

gh repo edit "$GH_REPO" --enable-issues --description "Varsling, autolas, Heimdall/Alarmo-synk og lokal webhook-opplasing for Home Assistant." --add-topic home-assistant --add-topic hacs --add-topic custom-integration

git add -- custom_components/ki_notifications .github .gitignore hacs.json README.md LES_MEG.md TESTING.md RELEASE.md LICENSE scripts sounds tests
git diff --cached --quiet && { echo "Ingen endringer aa publisere." >&2; exit 1; }
git commit -m "Varslinger og sikkerhet v$V"
git tag -a "$TAG" -m "Varslinger og sikkerhet $V"
# Publiser commit og tag samlet. Ingen force-push.
git_gh push --atomic origin main "refs/tags/$TAG"

gh release create "$TAG" "$ZIP" --repo "$GH_REPO" --verify-tag --title "Varslinger og sikkerhet $V" --notes-file RELEASE.md
printf '\nPublisert: https://github.com/%s/releases/tag/%s\n' "$GH_REPO" "$TAG"
printf 'Kontroller GitHub Actions: https://github.com/%s/actions\n' "$GH_REPO"
