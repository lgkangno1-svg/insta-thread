(() => {
  const form = document.querySelector('[data-downloader-form]');
  if (!form) return;

  const input = form.querySelector('input[name="url"]');
  const button = form.querySelector('button[type="submit"]');
  const status = document.querySelector('[data-status]');
  const detection = document.querySelector('[data-detected]');
  const result = document.querySelector('[data-result]');
  const resultImg = document.querySelector('[data-result-img]');
  const resultTitle = document.querySelector('[data-result-title]');
  const resultMeta = document.querySelector('[data-result-meta]');
  const assets = document.querySelector('[data-assets]');

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

  const setDetection = (text, active = false) => {
    if (!detection) return;
    detection.textContent = text;
    detection.className = 'detected' + (active ? ' active' : '');
  };

  const detectFromUrl = raw => {
    try {
      const host = new URL(raw).hostname.toLowerCase().replace(/^www\./, '');
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

  const kindLabel = kind => kind === 'video' ? 'Video' : (kind === 'thumbnail' ? 'Thumbnail' : 'Image');

  input.addEventListener('input', () => {
    const value = input.value.trim();
    if (!value) {
      setDetection('Paste any supported public link — the platform is detected automatically.');
      return;
    }
    const platform = detectFromUrl(value);
    if (platform) {
      setDetection(`${platformLabels[platform]} link detected`, true);
    } else {
      setDetection('Paste a YouTube, Instagram, Threads, Douyin or Xiaohongshu link.');
    }
  });

  async function startDownload(url, assetId, analysisToken, gate, btn) {
    const old = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Queued…';
    setStatus('Preparing your file on the download server…');
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
        if (!statusRes.ok) throw new Error(job.detail || 'Download job disappeared');
        if (job.status === 'error') throw new Error(job.error || 'Download preparation failed');
        if (job.status === 'ready') {
          const a = document.createElement('a');
          a.href = job.download_url;
          a.rel = 'nofollow';
          document.body.appendChild(a);
          a.click();
          a.remove();
          setStatus('Download ready. The temporary server copy is deleted after delivery.');
          return;
        }
        btn.textContent = job.status === 'processing' ? 'Preparing…' : 'Queued…';
      }
      throw new Error('The download preparation timed out. Try a smaller quality or retry later.');
    } catch (err) {
      setStatus(err.message || 'Download failed.', true);
    } finally {
      btn.disabled = false;
      btn.textContent = old;
    }
  }

  form.addEventListener('submit', async e => {
    e.preventDefault();
    const url = input.value.trim();
    if (!url) return;

    button.disabled = true;
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

      const label = platformLabels[data.platform] || data.platform;
      setDetection(`${label} detected`, true);
      setStatus(`Ready — choose the exact ${label} file you want.`);

      resultImg.src = data.preview_url || '';
      resultImg.style.display = data.preview_url ? 'block' : 'none';
      resultTitle.textContent = data.title || 'Public media';
      resultMeta.textContent = [data.author, label].filter(Boolean).join(' · ');

      const gate = {enabled: data.sponsor_gate_enabled, seconds: data.gate_seconds};
      for (const item of data.assets) {
        const row = document.createElement('div');
        row.className = 'asset';
        if (item.preview_url) {
          const img = document.createElement('img');
          img.className = 'asset-thumb';
          img.src = item.preview_url;
          img.alt = '';
          img.loading = 'lazy';
          row.appendChild(img);
        }
        const main = document.createElement('div');
        main.className = 'asset-main';
        const labelEl = document.createElement('div');
        labelEl.className = 'asset-label';
        labelEl.textContent = item.label;
        const sub = document.createElement('div');
        sub.className = 'asset-sub';
        sub.textContent = `${kindLabel(item.kind)}${item.ext ? ' · ' + item.ext.toUpperCase() : ''}`;
        main.append(labelEl, sub);
        row.appendChild(main);
        const dl = document.createElement('button');
        dl.className = 'download';
        dl.type = 'button';
        dl.textContent = 'Download';
        dl.addEventListener('click', () => startDownload(url, item.id, data.analysis_token, gate, dl));
        row.appendChild(dl);
        assets.appendChild(row);
      }
      result.classList.add('show');
      result.scrollIntoView({behavior: 'smooth', block: 'nearest'});
    } catch (err) {
      setStatus(err.message || 'Could not analyze this link.', true);
    } finally {
      button.disabled = false;
    }
  });

  setDetection('Paste any supported public link — the platform is detected automatically.');
})();
