(() => {
  const form = document.querySelector('[data-downloader-form]');
  if (!form) return;

  const input = form.querySelector('input[name="url"]');
  const button = form.querySelector('button[type="submit"]');
  const pasteButton = form.querySelector('[data-paste]');
  const clearButton = form.querySelector('[data-clear]');
  const status = document.querySelector('[data-status]');
  const detection = document.querySelector('[data-detected]');
  const result = document.querySelector('[data-result]');
  const resultImg = document.querySelector('[data-result-img]');
  const resultTitle = document.querySelector('[data-result-title]');
  const resultMeta = document.querySelector('[data-result-meta]');
  const assets = document.querySelector('[data-assets]');
  const count = document.querySelector('[data-asset-count]');
  const platformChips = [...document.querySelectorAll('[data-platform-chip]')];

  const platformLabels = {
    youtube: 'YouTube',
    instagram: 'Instagram',
    threads: 'Threads',
    douyin: 'Douyin',
    xiaohongshu: 'Xiaohongshu / RedNote'
  };
  const transientStatuses = new Set([429, 502, 503, 504]);
  const trailingSharePunctuation = /[.,;:!?，。；：！？、)\]}>】》」』）”’"]+$/u;
  const zeroWidth = /[\u200B-\u200D\u2060\uFEFF]/g;
  const explicitUrlPattern = /https?:\/\/[^\s<>"'`]+/gi;
  const bareUrlPattern = /(?<![\w@])(?:(?:www|m|music|v)\.)?(?:youtube\.com|instagram\.com|instagr\.am|xiaohongshu\.com|rednote\.com|xhslink\.com|xhslink\.cn|threads\.com|threads\.net|douyin\.com|iesdouyin\.com)\/[^\s<>"'`]+/gi;

  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

  const parseJson = async response => {
    try {
      return await response.json();
    } catch (_) {
      return {};
    }
  };

  async function requestJson(url, options = {}, {timeoutMs = 70000, retries = 0} = {}) {
    let lastError;
    for (let attempt = 0; attempt <= retries; attempt += 1) {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), timeoutMs);
      try {
        const response = await fetch(url, {...options, signal: controller.signal});
        const data = await parseJson(response);
        if (!response.ok) {
          const error = new Error(data.detail || `Request failed (${response.status})`);
          error.status = response.status;
          if (attempt < retries && transientStatuses.has(response.status)) {
            await sleep(700 * (attempt + 1));
            lastError = error;
            continue;
          }
          throw error;
        }
        return {response, data};
      } catch (error) {
        const normalized = error && error.name === 'AbortError'
          ? new Error('The server took too long to respond. Please try again.')
          : error;
        lastError = normalized;
        if (attempt < retries && (!error.status || transientStatuses.has(error.status))) {
          await sleep(700 * (attempt + 1));
          continue;
        }
        throw normalized;
      } finally {
        clearTimeout(timer);
      }
    }
    throw lastError || new Error('Request failed.');
  }

  const track = eventName => {
    if (window.trackMonetizationEvent) window.trackMonetizationEvent(eventName);
  };

  const setStatus = (text, error = false) => {
    if (!status) return;
    status.textContent = text || '';
    status.className = 'status' + (error ? ' error' : '');
  };

  const setDetection = (text, platform = '') => {
    if (detection) {
      detection.textContent = text;
      detection.className = 'detected' + (platform ? ' active' : '');
    }
    platformChips.forEach(chip => {
      chip.classList.toggle('active', Boolean(platform) && chip.dataset.platformChip === platform);
    });
  };

  const platformFromCandidate = candidate => {
    try {
      const parsed = new URL(candidate);
      if (!['http:', 'https:'].includes(parsed.protocol)) return '';
      const host = parsed.hostname.toLowerCase().replace(/^www\./, '');
      if (host === 'youtu.be' || host === 'youtube.com' || host.endsWith('.youtube.com')) return 'youtube';
      if (host === 'instagr.am' || host === 'instagram.com' || host.endsWith('.instagram.com')) return 'instagram';
      if (host === 'threads.com' || host === 'threads.net' || host.endsWith('.threads.com') || host.endsWith('.threads.net')) return 'threads';
      if (host === 'iesdouyin.com' || host === 'douyin.com' || host.endsWith('.douyin.com')) return 'douyin';
      if (host === 'xhslink.com' || host === 'xhslink.cn' || host === 'xiaohongshu.com' || host.endsWith('.xiaohongshu.com') || host === 'rednote.com' || host.endsWith('.rednote.com')) return 'xiaohongshu';
    } catch (_) {}
    return '';
  };

  const cleanCandidate = candidate => candidate.trim().replace(trailingSharePunctuation, '');

  const extractSupportedUrl = raw => {
    const text = String(raw || '').replace(zeroWidth, '').trim();
    if (!text) return '';

    explicitUrlPattern.lastIndex = 0;
    let match;
    while ((match = explicitUrlPattern.exec(text))) {
      const candidate = cleanCandidate(match[0]);
      if (platformFromCandidate(candidate)) return candidate;
    }

    bareUrlPattern.lastIndex = 0;
    while ((match = bareUrlPattern.exec(text))) {
      const candidate = `https://${cleanCandidate(match[0])}`;
      if (platformFromCandidate(candidate)) return candidate;
    }

    if (/^[0-9a-f]{24}$/i.test(text)) {
      return `https://www.xiaohongshu.com/explore/${text.toLowerCase()}`;
    }
    return '';
  };

  const detectFromUrl = raw => {
    const candidate = extractSupportedUrl(raw);
    return candidate ? platformFromCandidate(candidate) : '';
  };

  const updateDetection = () => {
    const value = input.value.trim();
    if (!value) {
      setDetection('Paste a link or the full copied share message — platform selection is automatic.');
      return;
    }
    const platform = detectFromUrl(value);
    if (platform) {
      const extracted = extractSupportedUrl(value);
      const fromMessage = extracted && extracted !== value;
      setDetection(`${platformLabels[platform]} detected${fromMessage ? ' inside copied share text' : ' automatically'}`, platform);
    } else {
      setDetection('Supported: YouTube, Instagram, Threads, Douyin and Xiaohongshu/RedNote public share links.');
    }
  };

  const kindLabel = kind => ({
    video: 'Video',
    thumbnail: 'Thumbnail',
    image: 'Image',
    archive: 'Archive'
  }[kind] || 'Media');

  async function startDownload(url, assetId, analysisToken, gate, btn) {
    const old = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Queued…';
    setStatus('Preparing your file securely…');
    let started = false;
    try {
      if (window.runSponsorGate) {
        await window.runSponsorGate({
          force: Boolean(gate && gate.enabled),
          requiredSeconds: Number(gate && gate.seconds || 0)
        });
      }

      track('download_started');
      started = true;
      const {data: created} = await requestJson('/api/v1/jobs', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({url, asset_id: assetId, analysis_token: analysisToken})
      }, {timeoutMs: 25000, retries: 0});

      const pollStarted = Date.now();
      let transientFailures = 0;
      while (Date.now() - pollStarted < 12 * 60 * 1000) {
        await sleep(1500);
        let statusRes;
        try {
          statusRes = await fetch(`/api/v1/jobs/${created.id}`, {cache: 'no-store'});
        } catch (_) {
          transientFailures += 1;
          if (transientFailures <= 8) continue;
          throw new Error('Network connection was interrupted while preparing the download.');
        }

        if (transientStatuses.has(statusRes.status)) {
          transientFailures += 1;
          if (transientFailures <= 8) continue;
        } else {
          transientFailures = 0;
        }

        const job = await parseJson(statusRes);
        if (!statusRes.ok) throw new Error(job.detail || 'Download job is no longer available');
        if (job.status === 'error') throw new Error(job.error || 'Download preparation failed');
        if (job.status === 'ready') {
          track('download_ready');
          const a = document.createElement('a');
          a.href = job.download_url;
          a.rel = 'nofollow';
          document.body.appendChild(a);
          a.click();
          a.remove();
          setStatus('Download started. The temporary server copy is removed after delivery.');
          return;
        }
        btn.textContent = job.status === 'processing' ? 'Preparing…' : 'Queued…';
      }
      throw new Error('Preparation timed out. Retry the link or choose a smaller video quality.');
    } catch (err) {
      if (started) track('download_error');
      setStatus(err.message || 'Download failed.', true);
    } finally {
      btn.disabled = false;
      btn.textContent = old;
    }
  }

  const renderAssets = (data, url) => {
    assets.innerHTML = '';
    const items = Array.isArray(data.assets) ? data.assets : [];
    if (count) count.textContent = `${items.length} file option${items.length === 1 ? '' : 's'}`;

    const gate = {enabled: data.sponsor_gate_enabled, seconds: data.gate_seconds};
    for (const item of items) {
      const row = document.createElement('article');
      row.className = 'asset';

      if (item.preview_url) {
        const img = document.createElement('img');
        img.className = 'asset-thumb';
        img.src = item.preview_url;
        img.alt = '';
        img.loading = 'lazy';
        img.referrerPolicy = 'no-referrer';
        row.appendChild(img);
      } else {
        const placeholder = document.createElement('div');
        placeholder.className = 'asset-placeholder';
        placeholder.textContent = kindLabel(item.kind).slice(0, 1);
        row.appendChild(placeholder);
      }

      const main = document.createElement('div');
      main.className = 'asset-main';
      const label = document.createElement('div');
      label.className = 'asset-label';
      label.textContent = item.label || kindLabel(item.kind);
      const sub = document.createElement('div');
      sub.className = 'asset-sub';
      const dimensions = item.width && item.height ? ` · ${item.width}×${item.height}` : '';
      sub.textContent = `${kindLabel(item.kind)}${item.ext ? ' · ' + item.ext.toUpperCase() : ''}${dimensions}`;
      main.append(label, sub);
      row.appendChild(main);

      const dl = document.createElement('button');
      dl.className = 'download';
      dl.type = 'button';
      dl.textContent = 'Download';
      dl.addEventListener('click', () => startDownload(url, item.id, data.analysis_token, gate, dl));
      row.appendChild(dl);
      assets.appendChild(row);
    }
  };

  form.addEventListener('submit', async e => {
    e.preventDefault();
    const raw = input.value.trim();
    if (!raw) return;

    const url = extractSupportedUrl(raw);
    const detected = url ? platformFromCandidate(url) : '';
    if (!detected) {
      setStatus('No supported public-media link was found in the pasted text.', true);
      input.focus();
      return;
    }

    if (raw !== url) input.value = url;
    button.disabled = true;
    button.textContent = 'Analyzing…';
    result.classList.remove('show');
    assets.innerHTML = '';
    setStatus('Analyzing the public share link…');

    try {
      const {data} = await requestJson('/api/v1/analyze', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({url})
      }, {timeoutMs: 70000, retries: 1});
      if (!data.analysis_token) throw new Error('The server did not issue a download ticket. Analyze again.');
      if (!Array.isArray(data.assets) || !data.assets.length) throw new Error('No downloadable public media was found.');

      const sourceUrl = data.source_url || url;
      const label = platformLabels[data.platform] || data.platform;
      setDetection(`${label} detected automatically`, data.platform);
      setStatus(`Ready — choose the exact ${label} file you want.`);

      if (resultImg) {
        resultImg.src = data.preview_url || '';
        resultImg.style.display = data.preview_url ? 'block' : 'none';
        resultImg.referrerPolicy = 'no-referrer';
      }
      resultTitle.textContent = data.title || 'Public media';
      resultMeta.textContent = [data.author, label].filter(Boolean).join(' · ');
      renderAssets(data, sourceUrl);
      result.classList.add('show');
      result.scrollIntoView({behavior: 'smooth', block: 'nearest'});
    } catch (err) {
      setStatus(err.message || 'Could not analyze this link.', true);
    } finally {
      button.disabled = false;
      button.textContent = 'Analyze link';
    }
  });

  input.addEventListener('input', updateDetection);

  if (pasteButton) {
    pasteButton.addEventListener('click', async () => {
      try {
        const text = await navigator.clipboard.readText();
        if (text) {
          input.value = text.trim();
          updateDetection();
          input.focus();
        }
      } catch (_) {
        setStatus('Clipboard access is blocked by the browser. Paste with Ctrl/Cmd+V instead.', true);
        input.focus();
      }
    });
  }

  if (clearButton) {
    clearButton.addEventListener('click', () => {
      input.value = '';
      result.classList.remove('show');
      assets.innerHTML = '';
      setStatus('');
      updateDetection();
      input.focus();
    });
  }

  updateDetection();
})();
