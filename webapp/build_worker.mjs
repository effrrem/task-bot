// Собирает worker.js из webapp-ассетов + шаблона:
//   node webapp/build_worker.mjs > webapp/worker.js
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const read = (f) =>
  readFileSync(join(here, f), "utf8").replace(/\`/g, "\\\`").replace(/\$\{/g, "\\${");

const assets = [
  `const INDEX_HTML = \`${read("index.html")}\`;`,
  `const STYLE_CSS = \`${read("style.css")}\`;`,
  `const APP_JS = \`${read("app.js")}\`;`,
].join("\n");

const tmpl = readFileSync(join(here, "worker.template.js"), "utf8");
writeFileSync(join(here, "worker.js"), tmpl.replace("/*ASSETS*/", assets));
console.log("webapp/worker.js built");
