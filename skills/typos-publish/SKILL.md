---
name: typos-publish
description: Complete a Markdown article's frontmatter (title, slug, description, category, cover, date) and publish it to a Typos blog via its API. Use this whenever the user wants to upload, publish, or post a Markdown file to their Typos site (e.g. typos.hopesy.cc), asks to "发布文章", "上传到博客", "publish to Typos", or points at a .md file and says to put it online. Also use it when the user wants to batch-publish several Markdown files.
license: MIT
metadata:
  author: hopesy
  version: "1.0.0"
---

# Typos Publish

Turn a raw Markdown file into a properly-formatted Typos post and publish it through the `/api/v1/posts` API.

## Overview

A Typos post stores these frontmatter fields: `title`, `date`, `slug`, `description`, `category`, `cover`. Raw articles often have none of them. This skill fills the gaps, shows the result for confirmation, then uploads.

The upload itself is done by `scripts/upload.mjs`, which reads credentials from `config.json` and POSTs the Markdown to the site. The server parses the frontmatter, so the heavy lifting is just producing good frontmatter.

## Prerequisites

Credentials live in `config.json` next to this skill (`baseUrl` + `token`). It is git-ignored / local-only. If it is missing, tell the user to copy `config.example.json` to `config.json` and fill in their site URL and an API token generated at `/admin` → 密钥.

## Workflow

Follow these steps in order.

### 1. Read the article

Read the target Markdown file. If the user gave a path, use it. If they referenced "this file" or a file open in context, resolve that. If multiple files, process each through steps 2–4 (see Batch mode).

### 2. Generate frontmatter

Inspect the existing content and produce each field. If the file already has frontmatter, treat existing values as defaults and only fill what is missing or clearly wrong.

- **title**: Use existing `# H1` heading or an explicit title. Keep it concise; strip noise. If the H1 is very long, write a shorter title and leave the long H1 in the body.
- **date**: Use existing date in frontmatter, else any date evident in the content, else today's date (format `YYYY-MM-DD`).
- **slug**: An English, semantic, kebab-case slug derived from the title's meaning — e.g. `ai-api-paths`, not a date or pinyin. Lowercase, words joined by `-`, ASCII only, no trailing punctuation. Translate Chinese titles to a short meaningful English phrase. Keep it short (2–5 words).
- **description**: One sentence (≈15–40 chars zh / ≈10–20 words en) summarizing the article, in the article's own language.
- **category**: 1–3 topical tags as a YAML list. Reuse the article's domain (e.g. `技术`, `AI`, `教程`). Default to `随笔` only if nothing fits.
- **cover**: Leave empty (`""`) unless the article clearly references a cover image URL.

### 3. Show for confirmation

Present the generated frontmatter to the user as a YAML block plus the resulting post URL (`<baseUrl>/posts/<slug>`). Ask them to confirm or adjust. Apply any edits they request. Do not upload until they approve.

### 4. Build the final Markdown and upload

Write the approved frontmatter + body to a temporary file (do NOT modify the user's original file unless they ask), then run the upload script:

```bash
node <skill-dir>/scripts/upload.mjs <path-to-final-markdown>
```

The script prints JSON: `{"ok":true,"slug":"...","url":"..."}` on success, or `{"ok":false,...}` on failure. Report the result and the live URL. Clean up the temporary file afterward.

If the script reports `ok:false`:
- `status:401` → token invalid/expired. Tell the user to generate a new token at `/admin` → 密钥 and update `config.json`.
- `status:503` → the site's D1 database isn't reachable; the API needs D1.
- network error → check the `baseUrl` and connectivity.

## Frontmatter format

The body sent to the API looks like:

```markdown
---
title: AI API 路径深度解析
date: 2026-06-15
slug: ai-api-paths
description: 解析常见 AI API 接口后缀的设计与区别
category:
  - 技术
  - AI
cover: ""
---

# 原文正文标题...

正文内容...
```

Notes:
- `category` may be a YAML list (preferred) or a comma-separated string; the server accepts both.
- Keep the original body intact below the frontmatter — don't rewrite the article content.
- Quote values containing `:` or special characters.

## Batch mode

When several files are given, run steps 2–3 for all of them first and present a combined table (file → title / slug / category) for one confirmation, then upload each in step 4. Report a summary of successes and failures at the end.

## JSON alternative

The script sends Markdown, which is simplest. If a user specifically needs structured JSON upload (e.g. no frontmatter, fields passed directly), the same endpoint accepts `Content-Type: application/json` with `{title, date, slug, description, category, cover, content}`. Prefer the Markdown path unless asked.
