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
    xiaohongshu: 'Xiaohongshu'
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

  const detectFromUrl = raw => {
    try {
      const parsed = new URL(raw);
      if (!['http:', 'https:'].includes(parsed.protocol)) return '';
      const host = parsed.hostname.toLowerCase().replace(/^www\./, '');
      if (host === 'youtu.be' || host.endsWith('youtube.com')) return 'youtube';
      if (host.endsWith('instagram.com')) return 'instagram';
      if (host.endsWith('threads.com') || host.endsWith('threads.net')) return 'threads';
      if (host.endsWith('douyin.com')) return 'douyin';
      if (host.endsWith('xiaohongshu.com') || host.endsWith('xhslink.com') || host.endsWith('xhslink.cn')) return 'xiaohongshu';
    } catch (_) {
      return '';
    }
    return '';
  };

  const updateDetection = () => {
    const value = input.value.trim();
    if (!value) {
      setDetection('Paste any supported public link — platform selection is automatic.');
      return;
    }
    const platform = detectFromUrl(value);
    if (platform) {
      setDetection(`${platformLabels[platform]} detected automatically`, platform);
    } else {
      setDetection('Supported: YouTube, Instagram, Threads, Douyin and Xiaohongshu.');
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
    try {
      if (window.runSponsorGate) {
        await window.runSponsorGate({
          force: Boolean(gate && gate.enabled),
          requiredSeconds: Number(gate && gate.seconds || 0)
        });
      }

      const res = await fetch('/api/v1/jobs', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({url, asset_id: assetId, analysis_token: analysisToken})
      });
      const created = await res.json();
      if (!res.ok) throw new Error(created.detail || `Could not start download (${res.status})`);

      const started = Date.now();
      while (Date.now() - started < 12 * 60 * 1000) {
        await new Promise(resolve => setTimeout(resolve, 1500));
        const statusRes = await fetch(`/api/v1/jobs/${created.id}`, {cache: 'no-store'});
        const job = await statusRes.json();
        if (!statusRes.ok) throw new Error(job.detail || 'Download job is no longer available');
        if (job.status === 'error') throw new Error(job.error || 'Download preparation failed');
        if (job.status === 'ready') {
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
    const url = input.value.trim();
    if (!url) return;

    const detected = detectFromUrl(url);
    if (!detected) {
      setStatus('This does not look like a supported public URL.', true);
      input.focus();
      return;
    }

    button.disabled = true;
    button.textContent = 'Analyzing…';
    result.classList.remove('show');
    assets.innerHTML = '';
    setStatus('Analyzing the public link…');

    try {
      const res = await fetch('/api/v1/analyze', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({url})
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `Analyze failed (${res.status})`);
      if (!data.analysis_token) throw new Error('The server did not issue a download ticket. Analyze again.');
      if (!Array.isArray(data.assets) || !data.assets.length) throw new Error('No downloadable public media was found.');

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
      renderAssets(data, url);
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
