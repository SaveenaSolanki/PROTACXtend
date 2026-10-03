// ensure-dist.mjs — rebuild the compiled TUI bundle whenever any source file
// is newer than dist/app.js, so src and dist cannot silently diverge.
import { execSync } from "node:child_process";
import { statSync, existsSync, readdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(fileURLToPath(import.meta.url)) + "/..";
const dist = join(root, "dist", "app.js");
const srcDir = join(root, "src");
const srcs = readdirSync(srcDir).filter((f) => f.endsWith(".ts"));
if (!existsSync(dist) || srcs.some((f) => statSync(join(srcDir, f)).mtimeMs > statSync(dist).mtimeMs)) {
  console.log("ensure-dist: rebuilding TUI bundle (src newer than dist)");
  execSync("npx tsc", { cwd: root, stdio: "inherit" });
} else {
  console.log("ensure-dist: dist is current");
}
