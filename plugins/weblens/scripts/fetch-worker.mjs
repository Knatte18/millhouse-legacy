import { Readability } from "@mozilla/readability";
import { parseHTML } from "linkedom";
import { fileURLToPath } from "url";

const HEADERS = {
  "User-Agent":
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
  Accept:
    "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
  "Accept-Language": "en-US,en;q=0.9,nb;q=0.8",
  "Accept-Encoding": "gzip, deflate, br",
  "Cache-Control": "no-cache",
  DNT: "1",
};

const REDDIT_RE = /^https?:\/\/(www\.|old\.)?reddit\.com/;

function isRedditUrl(url) {
  return REDDIT_RE.test(url);
}

function toRedditJsonUrl(url) {
  const clean = url.replace(/\/$/, "");
  return clean + ".json";
}

function formatRedditPost(data) {
  const post = data[0]?.data?.children?.[0]?.data;
  if (!post) return null;

  let out = `# ${post.title}\n\n`;
  out += `r/${post.subreddit} | ${post.score} points | ${post.num_comments} comments\n\n`;

  if (post.selftext) {
    out += post.selftext + "\n";
  } else if (post.url) {
    out += `Link: ${post.url}\n`;
  }

  const comments = data[1]?.data?.children || [];
  const topComments = comments
    .filter((c) => c.kind === "t1")
    .slice(0, 20);

  if (topComments.length > 0) {
    out += "\n## Top Comments\n\n";
    for (const c of topComments) {
      const d = c.data;
      out += `**${d.author}** (${d.score} pts):\n${d.body}\n\n`;
    }
  }

  return out;
}

function formatRedditSubreddit(data) {
  const posts = data?.data?.children || [];
  if (posts.length === 0) return null;

  const sub = posts[0]?.data?.subreddit || "unknown";
  let out = `# r/${sub}\n\n`;

  for (const p of posts) {
    const d = p.data;
    out += `- **${d.title}** (${d.score} pts, ${d.num_comments} comments)\n`;
    if (d.selftext) {
      const snippet = d.selftext.slice(0, 200).replace(/\n/g, " ");
      out += `  ${snippet}${d.selftext.length > 200 ? "..." : ""}\n`;
    }
    out += "\n";
  }

  return out;
}

async function fetchReddit(url) {
  const jsonUrl = toRedditJsonUrl(url);
  const response = await fetch(jsonUrl, {
    headers: { "User-Agent": "millhouse-reader/1.0" },
    redirect: "follow",
  });

  if (!response.ok) {
    return `# Error fetching ${url}\n\nHTTP ${response.status} ${response.statusText}`;
  }

  const json = await response.json();

  if (Array.isArray(json)) {
    const result = formatRedditPost(json);
    return result || `# ${url}\n\nCould not parse Reddit post.`;
  } else {
    const result = formatRedditSubreddit(json);
    return result || `# ${url}\n\nCould not parse Reddit listing.`;
  }
}

function htmlToText(html) {
  const { document } = parseHTML(`<div>${html}</div>`);
  const root = document.querySelector("div");

  for (const tag of root.querySelectorAll("script, style, noscript")) {
    tag.remove();
  }

  let text = root.textContent || "";
  text = text
    .replace(/[ \t]+/g, " ")
    .replace(/\n[ \t]+/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();

  return text;
}

async function fetchPage(url) {
  if (isRedditUrl(url)) {
    return fetchReddit(url);
  }

  let response;
  try {
    response = await fetch(url, {
      headers: HEADERS,
      redirect: "follow",
    });
  } catch (e) {
    return `# Error fetching ${url}\n\n${e.cause?.message || e.message}`;
  }

  if (!response.ok) {
    return `# Error fetching ${url}\n\nHTTP ${response.status} ${response.statusText}`;
  }

  let html = await response.text();

  html = html
    .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, "")
    .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, "")
    .replace(/<noscript[^>]*>[\s\S]*?<\/noscript>/gi, "");

  const { document } = parseHTML(html);

  const reader = new Readability(document);
  const article = reader.parse();

  if (!article) {
    const { document: fallbackDoc } = parseHTML(html);
    for (const tag of fallbackDoc.querySelectorAll("script, style, noscript, nav, header, footer")) {
      tag.remove();
    }
    const fallbackText = htmlToText(fallbackDoc.body?.innerHTML || "");
    if (fallbackText.length > 100) {
      return `# ${url}\n\n${fallbackText}`;
    }
    return `# ${url}\n\nCould not extract readable content from this page.`;
  }

  const text = htmlToText(article.content);
  return `# ${article.title}\n\nSource: ${url}\n\n${text}`;
}

export async function run() {
  const urls = process.argv.slice(2);

  if (urls.length === 0) {
    console.error("Usage: node fetch.mjs <url> [url2] [url3]...");
    process.exit(1);
  }

  const results = await Promise.all(urls.map(fetchPage));
  console.log(results.join("\n\n---\n\n"));
}

// Run directly if this is the entry point
const entryUrl = fileURLToPath(import.meta.url);
if (process.argv[1] === entryUrl || process.argv[1]?.endsWith("fetch-worker.mjs")) {
  await run();
}
