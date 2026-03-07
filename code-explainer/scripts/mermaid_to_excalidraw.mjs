#!/usr/bin/env node
import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";

import { parseMermaidToExcalidraw } from "@excalidraw/mermaid-to-excalidraw";

function usage() {
  console.log(
    "Usage: node scripts/mermaid_to_excalidraw.mjs --input <file.mmd> --output <scene.excalidraw.json> [--title <title>]"
  );
}

function parseArgs(argv) {
  const args = {};
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (!token.startsWith("--")) {
      continue;
    }
    const key = token.slice(2);
    const value = argv[index + 1];
    if (!value || value.startsWith("--")) {
      args[key] = "true";
      continue;
    }
    args[key] = value;
    index += 1;
  }
  return args;
}

function buildScene(title, elements, files) {
  return {
    type: "excalidraw",
    version: 2,
    source: "https://github.com/excalidraw/mermaid-to-excalidraw",
    elements,
    appState: {
      viewBackgroundColor: "#ffffff",
      gridSize: null,
      theme: "light",
      name: title || "Code Explainer Diagram"
    },
    files
  };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help === "true" || !args.input || !args.output) {
    usage();
    process.exit(args.help === "true" ? 0 : 2);
  }

  const inputPath = path.resolve(args.input);
  const outputPath = path.resolve(args.output);
  const title = args.title || path.basename(inputPath, path.extname(inputPath));
  const definition = await fs.readFile(inputPath, "utf8");
  const result = await parseMermaidToExcalidraw(definition, {
    themeVariables: {
      fontSize: "20px"
    },
    flowchart: {
      curve: "linear"
    }
  });

  const scene = buildScene(title, result.elements || [], result.files || {});
  await fs.mkdir(path.dirname(outputPath), { recursive: true });
  await fs.writeFile(outputPath, `${JSON.stringify(scene, null, 2)}\n`, "utf8");
  console.log(
    JSON.stringify(
      {
        ok: true,
        output: outputPath,
        elementCount: Array.isArray(scene.elements) ? scene.elements.length : 0,
        fileCount: scene.files ? Object.keys(scene.files).length : 0
      },
      null,
      2
    )
  );
}

main().catch((error) => {
  console.error(error && error.stack ? error.stack : String(error));
  process.exit(1);
});
