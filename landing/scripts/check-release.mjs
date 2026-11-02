// Vérifie en ligne que les fichiers cités par les commandes curl du site existent,
// et signale si une release plus récente que VERSION a été publiée.
import { VERSION } from "../site.config.mjs";

const repository = "nouhailler/Pm2or";
const base = `https://github.com/${repository}/releases/download/v${VERSION}`;
let failed = false;

for (const name of [`pm2-desktop_${VERSION}_amd64.deb`, `SHA256SUMS-${VERSION}`]) {
  const response = await fetch(`${base}/${name}`, { method: "HEAD", redirect: "follow" });
  console.log(`${response.ok ? "ok    " : "ABSENT"} ${name} (${response.status})`);
  failed ||= !response.ok;
}

const latest = await fetch(`https://api.github.com/repos/${repository}/releases/latest`, {
  headers: { accept: "application/vnd.github+json" },
});
if (latest.ok) {
  const tag = (await latest.json()).tag_name;
  if (tag === `v${VERSION}`) {
    console.log(`ok     ${tag} est la dernière release`);
  } else {
    console.log(`ÉCART  dernière release : ${tag}, site : v${VERSION}`);
    failed = true;
  }
} else {
  console.log(`?      dernière release non vérifiée (API GitHub : ${latest.status})`);
}
process.exitCode = failed ? 1 : 0;
