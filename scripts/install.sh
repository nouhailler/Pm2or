#!/usr/bin/env bash
# Installe PM² Desktop depuis les releases GitHub, sur Debian amd64.
#
#   curl -fsSL https://raw.githubusercontent.com/nouhailler/Pm2or/main/scripts/install.sh | bash
#
# Options (avec curl | bash : « | bash -s -- --dry-run ») :
#   --version X.Y.Z   installe cette version au lieu de la dernière
#   --dry-run         télécharge et vérifie le paquet, sans l'installer
#   --help            affiche cette aide
#
# La version et les noms de fichiers viennent de l'API GitHub : rien n'est à
# modifier ici à chaque release. Le paquet n'est installé que si son empreinte
# SHA-256 correspond au fichier SHA256SUMS publié dans la même release.

set -euo pipefail

REPOSITORY="nouhailler/Pm2or"
API="https://api.github.com/repos/$REPOSITORY/releases"
RELEASES_PAGE="https://github.com/$REPOSITORY/releases"
DOWNLOAD_PREFIX="$RELEASES_PAGE/download/"

fail() {
    printf 'Erreur : %s\n' "$1" >&2
    exit 1
}

fetch() {
    curl --proto '=https' --tlsv1.2 -fsSL --retry 2 "$@"
}

usage() {
    sed -n '2,13p' "$0" 2>/dev/null | sed 's/^# \{0,1\}//' ||
        printf 'Options : --version X.Y.Z, --dry-run, --help\n'
}

# Extrait les URL d'un JSON sans dépendre de jq, et n'accepte que ce dépôt.
asset_urls() {
    grep -oE '"browser_download_url": *"[^"]*"' |
        sed -E 's/^"browser_download_url": *"//; s/"$//' |
        { grep -F "$DOWNLOAD_PREFIX" || true; }
}

only_one() {
    local label="$1" matches
    matches="$(cat)"
    [ -n "$matches" ] || fail "$label introuvable dans la release. Consultez $RELEASES_PAGE"
    [ "$(printf '%s\n' "$matches" | wc -l)" -eq 1 ] || fail "plusieurs fichiers pour : $label."
    printf '%s\n' "$matches"
}

run_apt() {
    # Avec curl | bash, l'entrée standard est le script : apt doit lire le terminal.
    if [ "$(id -u)" -eq 0 ]; then
        set -- apt-get install "$1"
    else
        set -- sudo apt-get install "$1"
    fi
    if { : </dev/tty; } 2>/dev/null; then
        "$@" </dev/tty
    else
        "$@" -y </dev/null
    fi
}

main() {
    local version="" dry_run=0
    while [ "$#" -gt 0 ]; do
        case "$1" in
            --version)
                [ "$#" -ge 2 ] || fail "--version attend un numéro, par exemple 0.1.8."
                version="${2#v}"
                shift 2
                ;;
            --dry-run) dry_run=1; shift ;;
            --help | -h) usage; return 0 ;;
            *) fail "option inconnue : $1" ;;
        esac
    done
    case "$version" in
        "" | [0-9]*) ;;
        *) fail "numéro de version invalide : $version" ;;
    esac
    case "$version" in
        *[!0-9A-Za-z.-]*) fail "numéro de version invalide : $version" ;;
    esac

    local tool
    for tool in curl sha256sum dpkg dpkg-deb apt-get; do
        command -v "$tool" >/dev/null 2>&1 ||
            fail "$tool est requis. Ce script vise Debian ; voir $RELEASES_PAGE"
    done
    [ "$(dpkg --print-architecture)" = "amd64" ] ||
        fail "seule l'architecture amd64 est publiée (ici : $(dpkg --print-architecture))."

    local endpoint="$API/latest"
    [ -z "$version" ] || endpoint="$API/tags/v$version"

    local release
    release="$(fetch -H 'Accept: application/vnd.github+json' "$endpoint")" ||
        fail "GitHub ne répond pas ou limite les requêtes, ou cette version n'existe pas. Réessayez plus tard ou consultez $RELEASES_PAGE"

    local tag urls deb_url sums_url deb_name sums_name
    tag="$(printf '%s\n' "$release" | grep -oE '"tag_name": *"[^"]*"' | head -n 1 | sed -E 's/.*"([^"]*)"$/\1/')" || true
    [ -n "$tag" ] || fail "réponse de GitHub incomplète."
    urls="$(printf '%s\n' "$release" | asset_urls)"
    deb_url="$(printf '%s\n' "$urls" | grep -E '_amd64\.deb$' | only_one 'Paquet Debian amd64')"
    sums_url="$(printf '%s\n' "$urls" | grep -E '/SHA256SUMS[^/]*$' | only_one 'Fichier SHA256SUMS')"
    deb_name="${deb_url##*/}"
    sums_name="${sums_url##*/}"
    printf 'PM² Desktop %s : %s\n' "$tag" "$deb_name"

    local directory
    directory="$(mktemp -d)"
    # shellcheck disable=SC2064 # le chemin doit être figé dès maintenant
    trap "rm -rf -- '$directory'" EXIT
    chmod 755 "$directory" # apt lit le paquet avec son propre utilisateur

    printf 'Téléchargement…\n'
    fetch -o "$directory/$deb_name" "$deb_url" || fail "téléchargement du paquet impossible."
    fetch -o "$directory/$sums_name" "$sums_url" || fail "téléchargement des empreintes impossible."

    local expected
    expected="$(grep -E "^[0-9a-fA-F]{64}[[:space:]]+\*?$(printf '%s' "$deb_name" | sed 's/[.]/\\./g')\$" "$directory/$sums_name" || true)"
    [ -n "$expected" ] || fail "aucune empreinte publiée pour $deb_name. Installation annulée."
    (cd "$directory" && printf '%s\n' "$expected" | sha256sum -c --quiet - >/dev/null 2>&1) ||
        fail "empreinte SHA-256 incorrecte pour $deb_name. Installation annulée."
    printf 'Empreinte SHA-256 vérifiée.\n'

    [ "$(dpkg-deb -f "$directory/$deb_name" Package 2>/dev/null || true)" = "pm2-desktop" ] ||
        fail "$deb_name n'est pas le paquet attendu. Installation annulée."
    chmod 644 "$directory/$deb_name"

    if [ "$dry_run" -eq 1 ]; then
        printf 'Mode --dry-run : rien n’a été installé.\n'
        return 0
    fi

    printf 'Installation avec apt (mot de passe administrateur et confirmation possibles)…\n'
    run_apt "$directory/$deb_name" || fail "apt n'a pas pu installer le paquet. Vérifiez les prérequis sur $RELEASES_PAGE"
    printf 'Installé. Lancez l’application avec : pm2-desktop\n'
}

# main n'est appelé qu'ici : un téléchargement interrompu n'exécute rien.
main "$@"
