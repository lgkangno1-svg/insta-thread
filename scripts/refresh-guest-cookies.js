#!/usr/bin/env node
'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');

const browserHome = process.env.GUEST_BROWSER_HOME || path.join(os.homedir(), 'services', 'insta-thread', 'browser');
const output = process.argv[2] || process.env.YTDLP_COOKIE_FILE || path.join(os.homedir(), 'services', 'insta-thread', 'config', 'guest.cookies.txt');
const playwrightPath = path.join(browserHome, 'node_modules', 'playwright');
const browsersPath = process.env.PLAYWRIGHT_BROWSERS_PATH || path.join(browserHome, 'browsers');
process.env.PLAYWRIGHT_BROWSERS_PATH = browsersPath;

const { chromium } = require(playwrightPath);

const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36';
const DOUYIN_BOOTSTRAP = process.env.GUEST_DOUYIN_BOOTSTRAP_URL || 'https://www.douyin.com/video/7674195694563572712';
const XHS_BOOTSTRAP = process.env.GUEST_XHS_BOOTSTRAP_URL || 'https://www.xiaohongshu.com/';

function netscapeLine(cookie) {
  const domain = cookie.domain || '';
  const httpOnly = cookie.httpOnly ? '#HttpOnly_' : '';
  const includeSubdomains = domain.startsWith('.') ? 'TRUE' : 'FALSE';
  const secure = cookie.secure ? 'TRUE' : 'FALSE';
  const expires = cookie.expires && cookie.expires > 0 ? Math.floor(cookie.expires) : 2147483647;
  return `${httpOnly}${domain}\t${includeSubdomains}\t${cookie.path || '/'}\t${secure}\t${expires}\t${cookie.name}\t${cookie.value}`;
}

async function visit(browser, url, requiredCookie) {
  const context = await browser.newContext({
    locale: 'zh-CN',
    userAgent: UA,
    viewport: { width: 1365, height: 900 },
  });
  const page = await context.newPage();
  try {
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
  } catch (_) {
    // A navigation timeout is acceptable if the page already executed enough JS
    // to establish the anonymous anti-bot/session cookies.
  }
  await page.waitForTimeout(8000);
  const cookies = await context.cookies();
  await context.close();
  if (!cookies.some(c => c.name === requiredCookie)) {
    throw new Error(`Guest session cookie ${requiredCookie} was not created for ${new URL(url).hostname}`);
  }
  return cookies;
}

(async () => {
  fs.mkdirSync(path.dirname(output), { recursive: true, mode: 0o700 });
  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });
  try {
    const xhs = await visit(browser, XHS_BOOTSTRAP, 'web_session');
    const douyin = await visit(browser, DOUYIN_BOOTSTRAP, 's_v_web_id');
    const all = [...xhs, ...douyin];
    const seen = new Set();
    const unique = [];
    for (const cookie of all) {
      const key = `${cookie.domain}|${cookie.path}|${cookie.name}`;
      if (seen.has(key)) continue;
      seen.add(key);
      unique.push(cookie);
    }

    const temp = `${output}.tmp-${process.pid}`;
    fs.writeFileSync(temp, '# Netscape HTTP Cookie File\n' + unique.map(netscapeLine).join('\n') + '\n', { mode: 0o600 });
    fs.renameSync(temp, output);
    fs.chmodSync(output, 0o600);
    console.log(`guest_cookie_refresh=ok entries=${unique.length}`);
  } finally {
    await browser.close();
  }
})().catch(err => {
  console.error(`guest_cookie_refresh=failed ${String(err && err.message || err).split('\n')[0]}`);
  process.exit(1);
});
