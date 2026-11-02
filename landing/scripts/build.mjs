// Construit dist/ sans dépendance : empreintes de fichiers, sprite d'icônes,
// galerie, précache du service worker et fichiers de référencement.
import { createHash } from "node:crypto";
import { cp, mkdir, readdir, readFile, rm, writeFile } from "node:fs/promises";
import { basename, dirname, extname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { DEB_SIZE, GALLERY, RELEASE_DATE, VERSION } from "../site.config.mjs";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const src = join(root, "src");
const out = process.env.LANDING_OUT_DIR || join(root, "dist");
const siteUrl = (process.env.SITE_URL || "").replace(/\/+$/, "");

async function walk(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = await Promise.all(
    entries.map((entry) => {
      const path = join(directory, entry.name);
      return entry.isDirectory() ? walk(path) : [path];
    }),
  );
  return files.flat();
}

const sha = (data) => createHash("sha256").update(data).digest("hex").slice(0, 10);

function iconSprite(files) {
  const symbols = files.map(([name, svg]) => {
    const body = svg.replace(/<!--.*?-->/gs, "").replace(/<svg[^>]*>/s, "").replace("</svg>", "");
    const compact = body.replace(/\s+/g, " ").trim();
    return `<symbol id="i-${name}" viewBox="0 0 24 24">${compact}</symbol>`;
  });
  return `<svg class="sprite" aria-hidden="true" xmlns="http://www.w3.org/2000/svg">${symbols.join("")}</svg>`;
}

function galleryHtml() {
  return GALLERY.map(
    ([file, title, caption, alt]) => `<li><figure>
          <a class="shot" href="/assets/img/${file}-1500.webp" data-lightbox data-caption="${title} : ${caption}">
            <img src="/assets/img/${file}-800.webp" width="1500" height="950" loading="lazy" decoding="async" alt="${alt}">
          </a>
          <figcaption><strong>${title}</strong> ${caption}</figcaption>
        </figure></li>`,
  ).join("\n        ");
}

await rm(out, { recursive: true, force: true });
await mkdir(out, { recursive: true });
await cp(join(root, "public"), out, { recursive: true });

// 1. Ressources statiques : copiées sous un nom contenant leur empreinte.
const rename = new Map();
const assetFiles = (await walk(join(src, "assets"))).filter((file) => !file.endsWith(".css") && !file.endsWith(".js"));
for (const file of assetFiles) {
  const data = await readFile(file);
  const web = "/" + relative(src, file).replaceAll("\\", "/");
  const isLicense = extname(file) === ".txt";
  const target = isLicense ? web : web.replace(/(\.[^./]+)$/, `.${sha(data)}$1`);
  rename.set(web, target);
  await mkdir(dirname(join(out, target)), { recursive: true });
  await writeFile(join(out, target), data);
}

const rewrite = (text) =>
  text.replace(/\/assets\/[\w./-]+\.(?:webp|png|woff2|css|js)/g, (match) => rename.get(match) ?? match);

// 2. Feuilles de style, puis script (les références sont réécrites d'abord).
for (const name of ["styles.css", "noscript.css", "main.js"]) {
  const content = rewrite(await readFile(join(src, "assets", name), "utf8"));
  const target = `/assets/${name.replace(/(\.[^.]+)$/, `.${sha(content)}$1`)}`;
  rename.set(`/assets/${name}`, target);
  await writeFile(join(out, target), content);
}

// 3. Pages HTML.
const iconFiles = (await walk(join(src, "icons"))).filter((file) => file.endsWith(".svg"));
const icons = await Promise.all(iconFiles.map(async (file) => [basename(file, ".svg"), await readFile(file, "utf8")]));
const seoLinks = siteUrl ? `<link rel="canonical" href="${siteUrl}/">\n  <meta property="og:url" content="${siteUrl}/">` : "";
for (const page of ["index.html", "offline.html", "404.html"]) {
  const html = (await readFile(join(src, page), "utf8"))
    .replace("<!--ICONS-->", iconSprite(icons))
    .replace("<!--GALLERY-->", galleryHtml())
    .replace("<!--SEO_LINKS-->", seoLinks)
    .replaceAll("{{ORIGIN}}", siteUrl)
    .replaceAll("{{VERSION}}", VERSION)
    .replaceAll("{{RELEASE_DATE}}", RELEASE_DATE)
    .replaceAll("{{DEB_SIZE}}", DEB_SIZE);
  await writeFile(join(out, page), rewrite(html));
}

// 4. Service worker : cœur du site en précache, version dérivée du contenu.
// "/offline" sans extension : Cloudflare Pages redirige /offline.html vers /offline.
const precache = [
  "/",
  "/offline",
  rename.get("/assets/styles.css"),
  rename.get("/assets/main.js"),
  rename.get("/assets/img/logo-96.png"),
  rename.get("/assets/fonts/bricolage-grotesque-latin-wght-normal.woff2"),
  rename.get("/assets/fonts/source-sans-3-latin-wght-normal.woff2"),
  rename.get("/assets/img/cockpit-800.webp"),
  "/icons/icon-192.png",
  "/icons/favicon-32.png",
];
const hashed = await Promise.all((await walk(out)).map((file) => readFile(file)));
const version = sha(Buffer.concat(hashed));
const worker = (await readFile(join(src, "sw.js"), "utf8"))
  .replace('"__VERSION__"', JSON.stringify(version))
  .replace('["__PRECACHE__"]', JSON.stringify(precache));
await writeFile(join(out, "sw.js"), worker);

// 5. Référencement : le sitemap exige une adresse absolue, donc SITE_URL.
const robots = ["User-agent: *", "Allow: /"];
if (siteUrl) {
  robots.push(`Sitemap: ${siteUrl}/sitemap.xml`);
  await writeFile(
    join(out, "sitemap.xml"),
    `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>${siteUrl}/</loc></url></urlset>\n`,
  );
}
await writeFile(join(out, "robots.txt"), robots.join("\n") + "\n");

console.log(`Site construit dans ${relative(process.cwd(), out) || "."} (version ${version}${siteUrl ? `, ${siteUrl}` : ", sans SITE_URL"})`);
