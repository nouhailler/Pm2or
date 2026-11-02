import assert from "node:assert/strict";
import { cpSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import { dirname, extname, join, normalize } from "node:path";
import { after, before, test } from "node:test";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const axeSource = readFileSync(join(root, "node_modules/axe-core/axe.min.js"), "utf8");
const csp = readFileSync(join(root, "dist/_headers"), "utf8").match(/Content-Security-Policy: (.+)/)[1];
const TYPES = { ".html": "text/html; charset=utf-8", ".css": "text/css", ".js": "text/javascript", ".webp": "image/webp", ".png": "image/png", ".woff2": "font/woff2", ".webmanifest": "application/manifest+json" };

let served = join(root, "dist");
let server, browser, base;

before(async () => {
  // Reproduit la politique CSP de production : toute violation apparaît en console.
  server = createServer((request, response) => {
    let path = normalize(new URL(request.url, "http://x").pathname);
    if (path.endsWith("/")) path += "index.html";
    if (!extname(path)) path += ".html";
    try {
      const body = readFileSync(join(served, path));
      response.writeHead(200, { "content-type": TYPES[extname(path)] ?? "text/plain", "content-security-policy": csp, "cache-control": "no-cache" });
      response.end(body);
    } catch {
      response.writeHead(404, { "content-type": TYPES[".html"], "content-security-policy": csp });
      response.end(readFileSync(join(served, "404.html")));
    }
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  base = `http://localhost:${server.address().port}`;
  browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
});

after(async () => {
  await browser?.close();
  server?.close();
});

// Le site ne doit contacter aucune origine tierce au chargement.
async function open(viewport, options = {}) {
  const context = await browser.newContext({ viewport, serviceWorkers: "block", ...options });
  const page = await context.newPage();
  const problems = [];
  page.on("console", (message) => { if (message.type() === "error") problems.push(message.text()); });
  page.on("pageerror", (error) => problems.push(String(error)));
  page.on("response", (response) => { if (response.status() >= 400) problems.push(`${response.status()} ${response.url()}`); });
  page.on("request", (request) => { if (!request.url().startsWith(base) && !request.url().startsWith("data:")) problems.push(`tiers : ${request.url()}`); });
  await page.goto(base, { waitUntil: "load" });
  return { context, page, problems };
}

for (const [name, width, height] of [["mobile étroit", 320, 640], ["mobile", 390, 844], ["tablette", 768, 1024], ["portable", 1280, 800], ["large", 1920, 1080]]) {
  test(`${name} (${width} px) : aucun débordement, aucune erreur`, async () => {
    const { context, page, problems } = await open({ width, height });
    await page.evaluate(async () => {
      for (const img of document.images) img.loading = "eager";
      await Promise.all([...document.images].filter((i) => !i.complete).map((i) => new Promise((r) => { i.onload = i.onerror = r; })));
    });
    const overflow = await page.evaluate(() => {
      const limit = document.documentElement.clientWidth;
      return {
        scroll: document.documentElement.scrollWidth - limit,
        culprits: [...document.querySelectorAll("body *")].filter((el) => {
          if (el.closest("pre, .sr-only, .sprite, dialog")) return false;
          const box = el.getBoundingClientRect();
          return box.width > 0 && box.right > limit + 1;
        }).slice(0, 5).map((el) => el.tagName + "." + el.className),
      };
    });
    assert.ok(overflow.scroll <= 0, `débordement ${overflow.scroll}px : ${overflow.culprits}`);
    assert.deepEqual(overflow.culprits, []);
    assert.deepEqual(problems, []);
    assert.ok(await page.evaluate(() => [...document.images].every((i) => i.naturalWidth > 0)), "image non chargée");
    await context.close();
  });
}

test("accessibilité : axe-core sans violation, fermé puis FAQ ouverte", async () => {
  for (const viewport of [{ width: 1280, height: 800 }, { width: 390, height: 844 }]) {
    const { context, page } = await open(viewport, { reducedMotion: "reduce" });
    await page.addScriptTag({ content: axeSource }).catch(() => {});
    if (!(await page.evaluate(() => Boolean(window.axe)))) {
      await page.evaluate(axeSource);
    }
    await page.evaluate(() => document.querySelectorAll("details").forEach((d) => { d.open = true; }));
    const results = await page.evaluate(() => window.axe.run(document, { runOnly: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "best-practice"] }));
    const summary = results.violations.map((v) => `${v.id} (${v.impact}) : ${v.nodes.slice(0, 3).map((n) => n.target).join(" | ")}`);
    assert.deepEqual(summary, []);
    await context.close();
  }
});

test("menu mobile : clavier, état annoncé, Échap et retour du focus", async () => {
  const { context, page } = await open({ width: 390, height: 844 });
  const toggle = page.locator(".nav-toggle");
  assert.equal(await page.locator(".site-nav").isVisible(), false);
  await toggle.focus();
  await page.keyboard.press("Enter");
  assert.equal(await toggle.getAttribute("aria-expanded"), "true");
  assert.equal(await page.locator(".site-nav").isVisible(), true);
  await page.keyboard.press("Tab");
  assert.equal(await page.evaluate(() => document.activeElement.getAttribute("href")), "#fonctionnalites");
  await page.keyboard.press("Escape");
  assert.equal(await toggle.getAttribute("aria-expanded"), "false");
  assert.equal(await page.evaluate(() => document.activeElement.className), "nav-toggle");
  await toggle.click();
  await page.locator('.site-nav a[href="#faq"]').click();
  assert.equal(await page.locator(".site-nav").isVisible(), false);
  assert.ok(await page.evaluate(() => location.hash === "#faq"));
  await context.close();
});

test("sans JavaScript : la navigation et le contenu restent accessibles", async () => {
  const { context, page, problems } = await open({ width: 390, height: 844 }, { javaScriptEnabled: false });
  assert.equal(await page.locator(".site-nav").isVisible(), true);
  assert.equal(await page.locator(".nav-toggle").isVisible(), false);
  assert.deepEqual(problems, []);
  await context.close();
});

test("agrandissement d'une capture : ouverture, focus, Échap", async () => {
  const { context, page } = await open({ width: 1280, height: 800 });
  await page.locator(".shots [data-lightbox]").first().click();
  assert.equal(await page.locator("dialog.lightbox").isVisible(), true);
  await page.waitForFunction(() => document.querySelector("dialog img").naturalWidth > 100);
  await page.keyboard.press("Escape");
  assert.equal(await page.locator("dialog.lightbox").isVisible(), false);
  await context.close();
});

test("mouvement réduit : aucune animation active", async () => {
  const { context, page } = await open({ width: 1280, height: 800 }, { reducedMotion: "reduce" });
  assert.equal(await page.evaluate(() => document.getAnimations().length), 0);
  assert.equal(await page.evaluate(() => getComputedStyle(document.documentElement).scrollBehavior), "auto");
  await context.close();
});

test("le manifeste est lié et lisible par le navigateur", async () => {
  const { context, page } = await open({ width: 1280, height: 800 });
  const manifest = await page.evaluate(async () => (await fetch(document.querySelector('link[rel="manifest"]').href)).json());
  assert.equal(manifest.short_name, "PM² Site");
  await context.close();
});

test("PWA : hors ligne, page de repli, GitHub hors du cache, mise à jour contrôlée", async () => {
  served = join(root, "dist");
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (error) => errors.push(String(error)));
  await page.goto(base);
  await page.evaluate(() => navigator.serviceWorker.ready);
  await page.waitForFunction(() => navigator.serviceWorker.controller);

  // Hors ligne : l'accueil reste disponible, une autre adresse montre le repli.
  await context.setOffline(true);
  await page.goto(base);
  assert.match(await page.locator("h1").innerText(), /Pilotez vos projets/);
  await page.goto(`${base}/page-inconnue`);
  assert.match(await page.locator("h1").innerText(), /hors ligne/);
  await context.setOffline(false);

  // Aucun contenu externe dans les caches.
  await page.goto(base);
  const cached = await page.evaluate(async () => {
    const urls = [];
    for (const name of await caches.keys()) for (const request of await (await caches.open(name)).keys()) urls.push(request.url);
    return urls;
  });
  assert.ok(cached.length > 0 && cached.every((url) => url.startsWith(base)), cached.join());

  // Nouvelle publication : proposition de rechargement, ancien cache supprimé.
  const before = await page.evaluate(() => caches.keys());
  const next = mkdtempSync(join(tmpdir(), "pm2-site-next-"));
  cpSync(join(root, "dist"), next, { recursive: true });
  const worker = readFileSync(join(next, "sw.js"), "utf8").replace(/const VERSION = "[^"]+"/, 'const VERSION = "test-next"');
  writeFileSync(join(next, "sw.js"), worker);
  served = next;
  await page.evaluate(async () => (await navigator.serviceWorker.getRegistration()).update());
  await page.goto(base);
  const toast = page.locator(".update-toast");
  await toast.waitFor({ state: "visible", timeout: 15000 });
  await Promise.all([page.waitForEvent("load"), toast.locator("button").click()]);
  await page.waitForFunction(() => caches.keys().then((keys) => keys.includes("pm2-site-core-test-next")));
  await page.waitForFunction((old) => caches.keys().then((keys) => old.filter((k) => k.includes("core")).every((k) => !keys.includes(k))), before);
  served = join(root, "dist");
  assert.deepEqual(errors, []);
  await context.close();
});
