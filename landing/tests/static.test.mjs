import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { VERSION } from "../site.config.mjs";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const dist = join(root, "dist");
const html = readFileSync(join(dist, "index.html"), "utf8");
const RELEASES = "https://github.com/nouhailler/Pm2or/releases";
const attr = (name) => [...html.matchAll(new RegExp(`\\s${name}="([^"]*)"`, "g"))].map((match) => match[1]);
const anchors = [...html.matchAll(/<a\b[^>]*>[\s\S]*?<\/a>/g)].map((match) => match[0]);

test("la version affichée correspond à l'application", () => {
  const pyproject = readFileSync(join(root, "..", "pyproject.toml"), "utf8");
  assert.equal(pyproject.match(/^version = "(.+)"$/m)[1], VERSION);
  assert.ok(html.includes(`pm2-desktop_${VERSION}_amd64.deb`));
  assert.ok(!html.includes("{{"), "espace réservé non remplacé");
});

test("les boutons de téléchargement pointent tous vers les releases", () => {
  const buttons = anchors.filter((a) => /T.l.charger/.test(a.replace(/<[^>]+>/g, "")) && !/^<a\b[^>]*href="#/.test(a));
  assert.ok(buttons.length >= 3);
  for (const button of buttons) assert.ok(button.includes(`href="${RELEASES}"`), button);
  assert.ok(!/href="[^"]*\.(deb|AppImage|exe|dmg|msi)"/.test(html), "lien direct vers un binaire");
});

test("l'installation curl vise la version et s'arrête si l'empreinte échoue", () => {
  const block = html.match(/<pre[^>]*aria-labelledby="installer-curl"[^>]*>([\s\S]*?)<\/pre>/)[1].replace(/<[^>]+>/g, "").replaceAll("&amp;", "&");
  const base = `https://github.com/nouhailler/Pm2or/releases/download/v${VERSION}`;
  assert.ok(block.includes(`curl -fLO ${base}/pm2-desktop_${VERSION}_amd64.deb`));
  assert.ok(block.includes(`curl -fLO ${base}/SHA256SUMS-${VERSION}`));
  assert.ok(block.includes(`&& sha256sum -c --ignore-missing SHA256SUMS-${VERSION} \\\n  && sudo apt install ./pm2-desktop_${VERSION}_amd64.deb`));
  assert.ok(!/releases\/latest|\|\s*(sudo\s+)?(ba)?sh/.test(block));
});

test("les ancres internes et les ressources locales existent", () => {
  const ids = new Set(attr("id"));
  for (const href of attr("href")) {
    if (href.startsWith("#")) {
      if (!href.startsWith("#i-")) assert.ok(ids.has(href.slice(1)), `ancre absente : ${href}`);
    } else if (href.startsWith("/") && href !== "/") {
      assert.ok(existsSync(join(dist, href)), `ressource absente : ${href}`);
    }
  }
  const sources = [...attr("src"), ...attr("srcset").flatMap((set) => set.split(",").map((item) => item.trim().split(" ")[0]))];
  for (const src of sources) if (src.startsWith("/")) assert.ok(existsSync(join(dist, src)), `image absente : ${src}`);
});

test("chaque image a un texte alternatif et des dimensions", () => {
  for (const [tag] of html.matchAll(/<img\b[^>]*>/g)) {
    assert.match(tag, /\salt="/, tag);
    if (!tag.includes("data:image")) assert.match(tag, /\swidth="\d+"[^>]*\sheight="\d+"/, tag);
  }
});

test("aucune ressource tierce ni mesure d'audience", () => {
  const css = readFileSync(join(dist, "assets", readdirSync(join(dist, "assets")).find((f) => f.startsWith("styles."))), "utf8");
  for (const value of [...attr("src"), ...html.matchAll(/<link\b[^>]*href="([^"]+)"/g)].map((v) => (typeof v === "string" ? v : v[1]))) {
    assert.ok(!/^https?:|^\/\//.test(value), `ressource externe : ${value}`);
  }
  assert.ok(!/url\(["']?https?:/.test(css));
  assert.ok(!/google-analytics|googletagmanager|plausible|matomo|cloudflareinsights|<form(?![^>]*method="dialog")/.test(html));
});

test("les liens externes s'annoncent comme tels", () => {
  for (const anchor of anchors.filter((a) => /href="https?:/.test(a))) {
    assert.match(anchor, /target="_blank" rel="noopener"/, anchor);
    assert.match(anchor, /nouvel onglet/, anchor);
  }
});

test("le manifeste est complet et ses icônes existent", () => {
  const manifest = JSON.parse(readFileSync(join(dist, "manifest.webmanifest"), "utf8"));
  for (const key of ["name", "short_name", "start_url", "scope", "display", "theme_color", "background_color", "lang"]) assert.ok(manifest[key], key);
  assert.ok(manifest.icons.some((icon) => icon.sizes === "192x192"));
  assert.ok(manifest.icons.some((icon) => icon.sizes === "512x512" && icon.purpose === "maskable"));
  for (const icon of manifest.icons) assert.ok(statSync(join(dist, icon.src)).size > 0);
  assert.match(manifest.description, /ne remplace pas/);
});

test("le service worker est versionné et ignore les autres origines", () => {
  const worker = readFileSync(join(dist, "sw.js"), "utf8");
  assert.ok(!worker.includes("__VERSION__") && !worker.includes("__PRECACHE__"));
  assert.match(worker, /url\.origin !== self\.location\.origin\) return/);
  assert.ok(!worker.includes("github.com"));
  const list = JSON.parse(worker.match(/const PRECACHE = (\[.*\]);/)[1]);
  for (const path of list) assert.ok(path === "/" || existsSync(join(dist, path)) || existsSync(join(dist, `${path}.html`)), path);
});

test("le contenu reste honnête sur les limites", () => {
  const text = html.replace(/<[^>]+>/g, " ").replace(/&nbsp;/g, " ").replace(/\s+/g, " ");
  for (const needle of ["activée par défaut", "Pas de chiffrement intégré", "Pas de collaboration en temps réel", "sans lien officiel", "Debian 13 amd64", "Aucun paquet n'est publié pour Windows"]) {
    assert.ok(text.includes(needle), needle);
  }
  for (const forbidden of ["certifié", "témoignage", "chiffrement de bout", "100 % sécurisé", "version officielle"]) {
    assert.ok(!text.toLowerCase().includes(forbidden), forbidden);
  }
});

test("SEO : titre, description, Open Graph et fichiers de robots", () => {
  assert.match(html, /<title>PM² Desktop — Gestion de projets avec la méthodologie PM²<\/title>/);
  assert.match(html, /<meta name="description" content="[^"]{80,}"/);
  assert.match(html, /property="og:image" content="[^"]*og-image\.[0-9a-f]+\.png"/);
  assert.equal([...html.matchAll(/<h1\b/g)].length, 1);
  assert.ok(existsSync(join(dist, "robots.txt")));
});
