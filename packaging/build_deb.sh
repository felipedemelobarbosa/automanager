#!/usr/bin/env bash
# Monta o .deb a partir do programa gerado pelo PyInstaller (pasta dist/AutoManager).
# Uso: packaging/build_deb.sh <versão> [pasta_dist] [saída]
set -euo pipefail
VERSAO="${1:?informe a versão, ex.: 0.1.0}"
DIST="${2:-dist/AutoManager}"
SAIDA="${3:-AutoManager_${VERSAO}_amd64.deb}"
RAIZ="$(mktemp -d)"
trap 'rm -rf "$RAIZ"' EXIT
chmod 755 "$RAIZ"

mkdir -p "$RAIZ/DEBIAN" "$RAIZ/opt/automanager" "$RAIZ/usr/bin" "$RAIZ/usr/share/applications"
cp -a "$DIST/." "$RAIZ/opt/automanager/"
ln -s /opt/automanager/AutoManager "$RAIZ/usr/bin/automanager"
cat > "$RAIZ/usr/share/applications/automanager.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=AutoManager
Comment=Jogo manager de automobilismo
Exec=/opt/automanager/AutoManager
Terminal=false
Categories=Game;SportsGame;
DESK
cat > "$RAIZ/DEBIAN/control" <<CTRL
Package: automanager
Version: ${VERSAO}
Section: games
Priority: optional
Architecture: amd64
Maintainer: AutoManager <noreply@users.noreply.github.com>
Description: AutoManager – jogo manager de automobilismo
 Gerenciamento de equipes de automobilismo com interface no estilo Windows 9x.
 Jogos salvos, ligas e configurações ficam em ~/.local/share/automanager.
CTRL
dpkg-deb --root-owner-group --build "$RAIZ" "$SAIDA"
echo "$SAIDA"
