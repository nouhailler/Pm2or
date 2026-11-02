// Vérifie en ligne que la dernière release convient à scripts/install.sh, et indique
// si les captures et l'audit du site datent d'une version antérieure.
import { VERSION } from "../site.config.mjs";

const repository = "nouhailler/Pm2or";
const response = await fetch(`https://api.github.com/repos/${repository}/releases/latest`, {
  headers: { accept: "application/vnd.github+json" },
});
if (!response.ok) {
  console.error(`API GitHub : ${response.status}`);
  process.exit(1);
}
const release = await response.json();
const names = release.assets.map((asset) => asset.name);
console.log(`Dernière release : ${release.tag_name}`);
let failed = false;
for (const [label, pattern] of [["paquet", /_amd64\.deb$/], ["empreintes", /^SHA256SUMS/]]) {
  const count = names.filter((name) => pattern.test(name)).length;
  console.log(`${count === 1 ? "ok    " : "ERREUR"} ${label} (${count} fichier)`);
  failed ||= count !== 1;
}
if (release.tag_name !== `v${VERSION}`) {
  console.log(`À savoir : captures et audit du site issus de v${VERSION}. Le téléchargement n'est pas concerné.`);
}
process.exitCode = failed ? 1 : 0;
