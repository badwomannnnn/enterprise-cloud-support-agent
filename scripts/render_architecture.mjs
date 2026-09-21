import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

const runtimeModules = process.env.RUNTIME_NODE_MODULES;
if (!runtimeModules) throw new Error("Set RUNTIME_NODE_MODULES");
const { default: sharp } = await import(pathToFileURL(path.join(runtimeModules, "sharp/lib/index.js")).href);

const input = new URL("../docs/system_architecture.svg", import.meta.url);
const output = new URL("../docs/system_architecture.png", import.meta.url);
await sharp(await fs.readFile(input), { density: 180 }).png().toFile(output);
console.log(output.pathname);
