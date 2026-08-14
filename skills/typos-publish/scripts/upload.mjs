#!/usr/bin/env node
/**
 * Upload a post to a Typos site via the /api/v1/posts API.
 *
 * Usage:
 *   node upload.mjs <markdown-file>
 *
 * Reads credentials from config.json next to this script (baseUrl + token).
 * The markdown file should already contain YAML frontmatter (title, date,
 * slug, description, category, cover). The script sends the raw markdown with
 * Content-Type: text/markdown so the server parses the frontmatter.
 *
 * Prints a JSON result to stdout:
 *   { "ok": true, "slug": "...", "url": "..." }
 *   { "ok": false, "status": 401, "error": "..." }
 */

import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join, resolve } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));

function fail(message, extra = {}) {
  console.log(JSON.stringify({ ok: false, error: message, ...extra }));
  process.exit(1);
}

async function loadConfig() {
  const configPath = join(__dirname, "..", "config.json");
  let raw;
  try {
    raw = await readFile(configPath, "utf8");
  } catch {
    fail(
      `Config not found at ${configPath}. Copy config.example.json to config.json and fill in baseUrl + token.`,
    );
  }
  let config;
  try {
    config = JSON.parse(raw);
  } catch (error) {
    fail(`Config is not valid JSON: ${error.message}`);
  }
  if (!config.baseUrl || !config.token) {
    fail("Config must contain both baseUrl and token.");
  }
  return config;
}

async function main() {
  const fileArg = process.argv[2];
  if (!fileArg) {
    fail("Usage: node upload.mjs <markdown-file>");
  }

  const config = await loadConfig();
  const filePath = resolve(process.cwd(), fileArg);

  let markdown;
  try {
    markdown = await readFile(filePath, "utf8");
  } catch (error) {
    fail(`Cannot read markdown file: ${error.message}`);
  }

  if (!markdown.trim()) {
    fail("Markdown file is empty.");
  }

  const endpoint = `${config.baseUrl.replace(/\/$/, "")}/api/v1/posts`;

  let response;
  try {
    response = await fetch(endpoint, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${config.token}`,
        "Content-Type": "text/markdown",
      },
      body: markdown,
    });
  } catch (error) {
    fail(`Network error: ${error.message}`, { endpoint });
  }

  let body;
  const text = await response.text();
  try {
    body = JSON.parse(text);
  } catch {
    body = { raw: text };
  }

  if (!response.ok) {
    fail(body.error || `HTTP ${response.status}`, { status: response.status });
  }

  const slug = body.slug || "";
  const url = slug ? `${config.baseUrl.replace(/\/$/, "")}/posts/${slug}` : "";
  console.log(JSON.stringify({ ok: true, slug, url }));
}

main();
