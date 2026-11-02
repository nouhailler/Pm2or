// Petit serveur statique local, sans dépendance. --dev reconstruit à chaque modification.
import { spawnSync } from "node:child_process";
import { watch } from "node:fs";
import { readFile, stat } from "node:fs/promises";
import { createServer } from "node:http";
import { dirname, extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const dist = process.env.LANDING_OUT_DIR || join(root, "dist");
const port = Number(process.env.PORT || 4391);
const types = {
  ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8",
  ".webp": "image/webp", ".png": "image/png", ".woff2": "font/woff2", ".txt": "text/plain; charset=utf-8",
  ".xml": "application/xml", ".webmanifest": "application/manifest+json",
};
const build = () => spawnSync(process.execPath, [join(root, "scripts/build.mjs")], { stdio: "inherit" });

if (process.argv.includes("--dev")) {
  build();
  let timer;
  for (const folder of ["src", "public"]) {
    watch(join(root, folder), { recursive: true }, () => {
      clearTimeout(timer);
      timer = setTimeout(build, 150);
    });
  }
}

createServer(async (request, response) => {
  let path = normalize(decodeURIComponent(new URL(request.url, "http://x").pathname));
  if (path.endsWith("/")) path += "index.html";
  if (!extname(path)) path += ".html"; // comme Cloudflare Pages
  const file = join(dist, path);
  try {
    if (!file.startsWith(dist) || !(await stat(file)).isFile()) throw new Error("absent");
    response.writeHead(200, { "content-type": types[extname(file)] ?? "application/octet-stream" });
    response.end(await readFile(file));
  } catch {
    response.writeHead(404, { "content-type": types[".html"] });
    response.end(await readFile(join(dist, "404.html")));
  }
}).listen(port, "127.0.0.1", () => console.log(`http://localhost:${port}/`));
