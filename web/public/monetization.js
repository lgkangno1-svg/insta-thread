/*
  Direct sponsor / affiliate gate.
  Campaign presentation is loaded from the first-party API so campaigns can be
  changed without rebuilding the frontend. Never require a normal ad click to
  unlock a download and never style sponsor links as fake download buttons.
*/
window.AVOCADOSS_MONETIZATION = {
  enabled: false,
  delaySeconds: 4,
  frequency: 1,
  campaignId: '',
  sponsorLabel: 'Sponsored message',
  sponsorTitle: 'A short message from our sponsor',
  sponsorText: '',
  sponsorUrl: '',
  sponsorCta: 'Visit sponsor',
  affiliateDisclosure: 'Some links may be affiliate links. A purchase may generate a commission at no extra cost to you.'
};

function safeSponsorUrl(value) {
  if (!value) return '';
  try {
    const url = new URL(value, window.location.href);
    if (url.protocol !== 'https:') return '';
    return url.href;
  } catch (_) {
    return '';
  }
}

function monetizationPlatform() {
  const host = String(window.location.hostname || '').toLowerCase();
  if (host.startsWith('youtube.')) return 'youtube';
  if (host.startsWith('insta.')) return 'instagram';
  if (host.startsWith('thread.')) return 'threads';
  if (host.startsWith('douyin.')) return 'douyin';
  if (host.startsWith('xiaohongshu.')) return 'xiaohongshu';

  const path = String(window.location.pathname || '').toLowerCase();
  if (path.includes('youtube')) return 'youtube';
  if (path.includes('instagram')) return 'instagram';
  if (path.includes('threads')) return 'threads';
  if (path.includes('douyin')) return 'douyin';
  if (path.includes('xiaohongshu')) return 'xiaohongshu';
  return 'download';
}

let monetizationConfigPromise;
window.loadMonetizationConfig = function loadMonetizationConfig() {
  if (monetizationConfigPromise) return monetizationConfigPromise;
  monetizationConfigPromise = fetch('/api/v1/monetization/config', {cache: 'no-store'})
    .then(async response => {
      if (!response.ok) throw new Error('campaign config unavailable');
      const remote = await response.json();
      const sponsorUrl = safeSponsorUrl(remote.sponsorUrl || '');
      window.AVOCADOSS_MONETIZATION = {
        ...window.AVOCADOSS_MONETIZATION,
        ...remote,
        enabled: Boolean(remote.enabled && remote.campaignId && sponsorUrl),
        sponsorUrl
      };
      return window.AVOCADOSS_MONETIZATION;
    })
    .catch(() => window.AVOCADOSS_MONETIZATION);
  return monetizationConfigPromise;
};

window.trackMonetizationEvent = function trackMonetizationEvent(eventName, extra = {}) {
  const c = window.AVOCADOSS_MONETIZATION || {};
  const detail = {
    event: eventName,
    campaignId: String(c.campaignId || ''),
    platform: monetizationPlatform(),
    ts: Date.now(),
    ...extra
  };

  try {
    window.dispatchEvent(new CustomEvent('avocadoss:monetization', {detail}));
  } catch (_) {}

  if (Array.isArray(window.dataLayer)) {
    window.dataLayer.push({event: `monetization_${eventName}`, ...detail});
  }

  try {
    const key = `avocadossMonetization:${detail.campaignId || 'unconfigured'}:${detail.platform}:${eventName}`;
    localStorage.setItem(key, String(Number(localStorage.getItem(key) || '0') + 1));
  } catch (_) {}

  const payload = JSON.stringify({
    event: eventName,
    campaign_id: detail.campaignId,
    platform: detail.platform
  });
  try {
    if (navigator.sendBeacon) {
      const blob = new Blob([payload], {type: 'application/json'});
      if (navigator.sendBeacon('/api/v1/monetization/events', blob)) return;
    }
  } catch (_) {}
  fetch('/api/v1/monetization/events', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: payload,
    keepalive: true
  }).catch(() => {});
};

window.runSponsorGate = async function runSponsorGate(options = {}) {
  await window.loadMonetizationConfig();
  const c = window.AVOCADOSS_MONETIZATION || {};
  const forced = Boolean(options.force);
  const sponsorUrl = safeSponsorUrl(c.sponsorUrl);
  const campaignConfigured = Boolean(c.enabled && sponsorUrl && c.campaignId);
  const enabled = campaignConfigured || forced;
  if (!enabled) return;

  const count = Number(sessionStorage.getItem('avocadossDownloadCount') || '0') + 1;
  sessionStorage.setItem('avocadossDownloadCount', String(count));
  const frequency = Math.max(1, Number(c.frequency || 1));
  if (!forced && count % frequency !== 0) return;

  return new Promise(resolve => {
    const overlay = document.createElement('div');
    overlay.className = 'sponsor-overlay';
    const modal = document.createElement('div');
    modal.className = 'sponsor-modal';

    const label = document.createElement('div');
    label.className = 'sponsor-label';
    label.textContent = campaignConfigured ? (c.sponsorLabel || 'Sponsored') : 'Download preparation';

    const title = document.createElement('h3');
    title.textContent = campaignConfigured ? (c.sponsorTitle || 'Sponsored message') : 'Preparing your download';

    const text = document.createElement('p');
    text.textContent = campaignConfigured ? (c.sponsorText || '') : 'Your download will be ready shortly.';

    const disclosure = document.createElement('small');
    disclosure.textContent = campaignConfigured ? (c.affiliateDisclosure || '') : '';

    const actions = document.createElement('div');
    actions.className = 'sponsor-actions';

    if (campaignConfigured) {
      const visit = document.createElement('a');
      visit.className = 'sponsor-link';
      visit.href = sponsorUrl;
      visit.target = '_blank';
      visit.rel = 'nofollow sponsored noopener';
      visit.textContent = c.sponsorCta || 'Visit sponsor';
      visit.addEventListener('click', () => window.trackMonetizationEvent('click'));
      actions.appendChild(visit);
    }

    const cont = document.createElement('button');
    cont.className = 'btn sponsor-continue';
    cont.disabled = true;
    const configured = campaignConfigured ? Number(c.delaySeconds || 4) : 0;
    const required = Number(options.requiredSeconds || 0);
    const seconds = Math.max(0, Math.min(15, Math.max(configured, required)));
    let left = seconds;
    cont.textContent = left ? `Continue in ${left}s` : 'Continue to download';
    actions.appendChild(cont);

    modal.append(label, title, text, disclosure, actions);
    overlay.appendChild(modal);
    document.body.appendChild(overlay);
    if (campaignConfigured) window.trackMonetizationEvent('impression');

    const finish = () => {
      if (campaignConfigured) window.trackMonetizationEvent('continue');
      overlay.remove();
      resolve();
    };
    cont.addEventListener('click', finish);

    if (!left) {
      cont.disabled = false;
      return;
    }

    const timer = setInterval(() => {
      left -= 1;
      if (left <= 0) {
        clearInterval(timer);
        cont.disabled = false;
        cont.textContent = 'Continue to download';
      } else {
        cont.textContent = `Continue in ${left}s`;
      }
    }, 1000);
  });
};

// Warm the public config without blocking page rendering.
window.loadMonetizationConfig();
