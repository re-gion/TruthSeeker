import { createRequire } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";
import { existsSync } from "node:fs";
import fs from "node:fs/promises";
import path from "node:path";
import { spawn } from "node:child_process";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const dependencyPackage = path.join(__dirname, "promo-video", "package.json");
const require = createRequire(dependencyPackage);

const { chromium } = require("playwright");
const ffmpegPath = require("ffmpeg-static");

const htmlPath = path.join(__dirname, "truthseeker-promo.html");
const distDir = path.join(__dirname, "dist");
const webmPath = path.join(distDir, "truthseeker-promo.webm");
const mp4Path = path.join(distDir, "truthseeker-promo.mp4");

const chromeCandidates = [
  process.env.CHROME_PATH,
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
].filter(Boolean);

function findBrowser() {
  const found = chromeCandidates.find((candidate) => existsSync(candidate));
  if (!found) {
    throw new Error("未找到 Chrome/Edge。可设置 CHROME_PATH 指向浏览器 exe。");
  }
  return found;
}

function run(command, args, allowedExitCodes = [0]) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { stdio: ["ignore", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => { stdout += chunk.toString(); });
    child.stderr.on("data", (chunk) => { stderr += chunk.toString(); });
    child.on("error", reject);
    child.on("close", (code) => {
      if (allowedExitCodes.includes(code)) resolve({ stdout, stderr });
      else reject(new Error(`${path.basename(command)} exited ${code}\n${stderr || stdout}`));
    });
  });
}

async function fileSize(file) {
  const stat = await fs.stat(file);
  return stat.size;
}

async function main() {
  await fs.mkdir(distDir, { recursive: true });
  await Promise.all([
    fs.rm(webmPath, { force: true }),
    fs.rm(mp4Path, { force: true }),
  ]);

  const executablePath = findBrowser();
  console.log(`[export] browser: ${executablePath}`);
  console.log(`[export] ffmpeg: ${ffmpegPath}`);

  const browser = await chromium.launch({
    headless: true,
    executablePath,
    args: [
      "--autoplay-policy=no-user-gesture-required",
      "--allow-file-access-from-files",
      "--disable-background-timer-throttling",
      "--disable-renderer-backgrounding",
    ],
  });

  try {
    const context = await browser.newContext({
      acceptDownloads: true,
      viewport: { width: 1920, height: 1080 },
      deviceScaleFactor: 1,
    });
    const page = await context.newPage();
    page.on("console", (message) => {
      if (["error", "warning"].includes(message.type())) {
        console.log(`[browser:${message.type()}] ${message.text()}`);
      }
    });
    page.on("pageerror", (error) => {
      console.log(`[browser:pageerror] ${error.message}`);
    });

    const url = `${pathToFileURL(htmlPath).href}?record=1`;
    console.log("[export] recording webm...");
    await page.goto(url, { waitUntil: "load" });
    await page.waitForFunction(() => window.__truthseekerReady === true, null, { timeout: 10000 });

    const downloadLink = page.locator("#download");
    await downloadLink.waitFor({ state: "visible", timeout: 75000 });
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      downloadLink.click(),
    ]);
    await download.saveAs(webmPath);
  } finally {
    await browser.close();
  }

  const webmSize = await fileSize(webmPath);
  if (webmSize < 1024 * 1024) {
    throw new Error(`WebM 文件过小，疑似录制失败：${webmSize} bytes`);
  }
  console.log(`[export] webm: ${webmPath} (${(webmSize / 1024 / 1024).toFixed(2)} MB)`);

  console.log("[export] transcoding mp4...");
  await run(ffmpegPath, [
    "-y",
    "-i", webmPath,
    "-vf", "fps=60,format=yuv420p",
    "-c:v", "libx264",
    "-profile:v", "high",
    "-level", "4.2",
    "-crf", "18",
    "-preset", "veryfast",
    "-movflags", "+faststart",
    "-c:a", "aac",
    "-b:a", "192k",
    mp4Path,
  ]);

  const mp4Size = await fileSize(mp4Path);
  if (mp4Size < 1024 * 1024) {
    throw new Error(`MP4 文件过小，疑似转码失败：${mp4Size} bytes`);
  }

  const probe = await run(ffmpegPath, ["-hide_banner", "-i", mp4Path], [0, 1]);
  console.log(`[export] mp4: ${mp4Path} (${(mp4Size / 1024 / 1024).toFixed(2)} MB)`);
  console.log(probe.stderr.split(/\r?\n/).filter((line) => /Duration|Video:|Audio:/.test(line)).join("\n"));
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
