// Teste scripts/install.sh sans réseau ni installation : curl, sudo, apt-get et dpkg sont simulés.
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { chmodSync, existsSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const repository = join(dirname(fileURLToPath(import.meta.url)), "../..");
const script = readFileSync(join(repository, "scripts/install.sh"), "utf8");
const PREFIX = "https://github.com/nouhailler/Pm2or/releases/download";
const PACKAGE = "paquet de test";
const sha = (text) => createHash("sha256").update(text).digest("hex");
const release = (tag, urls) => JSON.stringify({ tag_name: tag, assets: urls.map((browser_download_url) => ({ browser_download_url })) });

function stubs({ api, files = {}, packageName = "pm2-desktop" }) {
  const dir = mkdtempSync(join(tmpdir(), "pm2-install-"));
  const fixtures = join(dir, "fixtures");
  writeFileSync(join(dir, "api.json"), api ?? "");
  const write = (name, body) => {
    writeFileSync(join(dir, name), `#!/bin/bash\n${body}\n`);
    chmodSync(join(dir, name), 0o755);
  };
  const cases = Object.entries(files).map(([url, content]) => {
    const file = join(dir, sha(url));
    writeFileSync(file, content);
    return `"${url}") cp "${file}" "$out" ;;`;
  });
  write("curl", `out=""; url=""
while [ $# -gt 0 ]; do case "$1" in -o) out="$2"; shift 2;; --proto|-H|--retry) shift 2;; -*) shift;; *) url="$1"; shift;; esac; done
echo "$url" >> "${dir}/requests.log"
case "$url" in
  https://api.github.com/*) ${api === undefined ? "exit 22" : `cat "${dir}/api.json"`} ;;
  ${cases.join("\n  ")}
  *) exit 22 ;;
esac`);
  write("dpkg", 'echo "${FAKE_ARCH:-amd64}"');
  write("dpkg-deb", `echo "${packageName}"`);
  write("apt-get", `echo "apt-get $*" >> "${dir}/apt.log"`);
  write("sudo", `echo "sudo $*" >> "${dir}/apt.log"; "$@"`);
  return { dir, fixtures };
}

function run(context, args = [], env = {}) {
  const result = spawnSync("bash", ["-s", "--", ...args], {
    input: script,
    encoding: "utf8",
    env: { PATH: `${context.dir}:${process.env.PATH}`, ...env },
    detached: true, // sans terminal de contrôle
  });
  const log = join(context.dir, "apt.log");
  return { ...result, apt: existsSync(log) ? readFileSync(log, "utf8") : "" };
}

function valid(version = "1.2.3", overrides = {}) {
  const deb = `pm2-desktop_${version}_amd64.deb`;
  const sums = `SHA256SUMS-${version}`;
  const debUrl = `${PREFIX}/v${version}/${deb}`;
  const sumsUrl = `${PREFIX}/v${version}/${sums}`;
  return {
    api: release(`v${version}`, [debUrl, sumsUrl, `${PREFIX}/v${version}/sbom.json`]),
    files: {
      [debUrl]: PACKAGE,
      [sumsUrl]: `${sha(PACKAGE)}  ${deb}\n${"0".repeat(64)}  sbom.json\n`,
    },
    ...overrides,
  };
}

test("une nouvelle version est détectée sans modifier le script, puis installée", () => {
  for (const version of ["1.2.3", "2.0.0"]) {
    const result = run(stubs(valid(version)));
    assert.equal(result.status, 0, result.stderr);
    assert.match(result.stdout, new RegExp(`v${version.replaceAll(".", "\\.")}`));
    assert.match(result.apt, new RegExp(`apt-get install /.*pm2-desktop_${version.replaceAll(".", "\\.")}_amd64\\.deb`));
  }
});

test("--dry-run vérifie mais n'installe rien", () => {
  const result = run(stubs(valid()), ["--dry-run"]);
  assert.equal(result.status, 0, result.stderr);
  assert.equal(result.apt, "");
});

test("--version interroge le tag demandé", () => {
  const context = stubs(valid("1.2.3"));
  assert.equal(run(context, ["--version", "1.2.3", "--dry-run"]).status, 0);
  assert.match(readFileSync(join(context.dir, "requests.log"), "utf8"), /releases\/tags\/v1\.2\.3/);
});

test("paquet altéré : rien n'est installé", () => {
  const fixture = valid();
  const url = Object.keys(fixture.files)[0];
  fixture.files[url] = "paquet modifié";
  const result = run(stubs(fixture));
  assert.equal(result.status, 1);
  assert.match(result.stderr, /empreinte SHA-256 incorrecte/);
  assert.equal(result.apt, "");
});

test("aucune empreinte pour ce paquet : rien n'est installé", () => {
  const fixture = valid();
  const url = Object.keys(fixture.files)[1];
  fixture.files[url] = `${"0".repeat(64)}  autre-fichier.deb\n`;
  const result = run(stubs(fixture));
  assert.equal(result.status, 1);
  assert.match(result.stderr, /aucune empreinte/);
  assert.equal(result.apt, "");
});

test("fichier d'un autre dépôt : refusé", () => {
  const foreign = "https://github.com/quelquun/autre/releases/download/v1/pm2-desktop_1_amd64.deb";
  const result = run(stubs({ api: release("v1", [foreign, `${PREFIX}/v1/SHA256SUMS-1`]) }));
  assert.equal(result.status, 1);
  assert.match(result.stderr, /Paquet Debian amd64 introuvable/);
  assert.equal(result.apt, "");
});

test("release sans paquet, API indisponible, mauvaise architecture : message clair", () => {
  const empty = run(stubs({ api: release("v1", [`${PREFIX}/v1/SHA256SUMS-1`]) }));
  assert.match(empty.stderr, /Paquet Debian amd64 introuvable/);
  const down = run(stubs({}));
  assert.equal(down.status, 1);
  assert.match(down.stderr, /GitHub ne répond pas/);
  const arch = run(stubs(valid()), [], { FAKE_ARCH: "arm64" });
  assert.equal(arch.status, 1);
  assert.match(arch.stderr, /amd64/);
  for (const result of [empty, down, arch]) assert.equal(result.apt, "");
});

test("paquet au nom inattendu : refusé", () => {
  const result = run(stubs({ ...valid(), packageName: "autre-paquet" }));
  assert.equal(result.status, 1);
  assert.match(result.stderr, /pas le paquet attendu/);
  assert.equal(result.apt, "");
});

test("script tronqué : rien n'est exécuté", () => {
  const context = stubs(valid());
  const cut = script.slice(0, script.lastIndexOf('main "$@"'));
  for (const partial of [cut, cut.slice(0, Math.floor(cut.length / 2))]) {
    const result = spawnSync("bash", ["-s"], { input: partial, encoding: "utf8", env: { PATH: `${context.dir}:${process.env.PATH}` } });
    assert.ok(!existsSync(join(context.dir, "requests.log")), result.stdout);
  }
});
