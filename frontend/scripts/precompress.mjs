// 构建后预压缩静态资源，配合 nginx gzip_static 使用：
// 磁盘上存一份 .gz，运行时 nginx 直接发送，不再每请求动态 gzip 占 CPU。
import { readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { extname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { gzipSync } from "node:zlib";

const distRoot = fileURLToPath(new URL("../dist", import.meta.url));
const COMPRESSIBLE = new Set([
  ".html",
  ".js",
  ".css",
  ".svg",
  ".json",
  ".txt",
  ".xml",
  ".webmanifest",
]);
const MIN_BYTES = 1024;

let compressed = 0;
let skipped = 0;

function walk(dir) {
  for (const entry of readdirSync(dir)) {
    const path = join(dir, entry);
    const stat = statSync(path);
    if (stat.isDirectory()) {
      walk(path);
      continue;
    }
    if (!COMPRESSIBLE.has(extname(path)) || path.endsWith(".gz")) {
      skipped += 1;
      continue;
    }
    const content = readFileSync(path);
    if (content.length < MIN_BYTES) {
      skipped += 1;
      continue;
    }
    writeFileSync(`${path}.gz`, gzipSync(content, { level: 9 }));
    compressed += 1;
  }
}

walk(distRoot);
console.log(
  `precompress: ${compressed} file(s) gzipped, ${skipped} skipped (${distRoot})`
);
