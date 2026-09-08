/*
  Direct sponsor / affiliate gate. Disabled by default.
  IMPORTANT: Do not put Google AdSense display ads inside this forced-view modal,
  and never require an ad click to unlock a download.
*/
window.AVOCADOSS_MONETIZATION = {
  enabled: false,
  delaySeconds: 4,
  frequency: 1, // UI preference. Server-side gate, when enabled, always wins.
  sponsorLabel: 'Sponsored message',
  sponsorTitle: 'A short message from our sponsor',
  sponsorText: 'Configure an approved direct sponsor or affiliate campaign here.',
  sponsorUrl: '',
  sponsorCta: 'Visit sponsor',
  affiliateDisclosure: 'Some links may be affiliate links. A purchase may generate a commission at no extra cost to you.'
};

window.runSponsorGate = function runSponsorGate(options = {}) {
  const c = window.AVOCADOSS_MONETIZATION || {};
  const forced = Boolean(options.force);
  const enabled = Boolean(c.enabled) || forced;
  if (!enabled) return Promise.resolve();

  const count = Number(sessionStorage.getItem('avocadossDownloadCount') || '0') + 1;
  sessionStorage.setItem('avocadossDownloadCount', String(count));
  const frequency = Math.max(1, Number(c.frequency || 1));
  // A server-required gate cannot be skipped by the UI frequency setting.
  if (!forced && count % frequency !== 0) return Promise.resolve();

  return new Promise(resolve => {
    const overlay = document.createElement('div');
    overlay.className = 'sponsor-overlay';
    const modal = document.createElement('div');
    modal.className = 'sponsor-modal';

    const label = document.createElement('div'); label.className = 'sponsor-label'; label.textContent = c.sponsorLabel || 'Sponsored';
    const title = document.createElement('h3'); title.textContent = c.sponsorTitle || 'Sponsored message';
    const text = document.createElement('p'); text.textContent = c.sponsorText || '';
    const disclosure = document.createElement('small'); disclosure.textContent = c.affiliateDisclosure || '';
    const actions = document.createElement('div'); actions.className = 'sponsor-actions';

    if (c.sponsorUrl) {
      const visit = document.createElement('a');
      visit.className = 'sponsor-link';
      visit.href = c.sponsorUrl;
      visit.target = '_blank';
      visit.rel = 'nofollow sponsored noopener';
      visit.textContent = c.sponsorCta || 'Visit sponsor';
      actions.appendChild(visit);
    }

    const cont = document.createElement('button');
    cont.className = 'btn sponsor-continue';
    cont.disabled = true;
    const configured = Number(c.delaySeconds || 4);
    const required = Number(options.requiredSeconds || 0);
    const seconds = Math.max(0, Math.min(15, Math.max(configured, required)));
    let left = seconds;
    cont.textContent = left ? `Continue in ${left}s` : 'Continue to download';
    actions.appendChild(cont);

    modal.append(label, title, text, disclosure, actions);
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    const finish = () => { overlay.remove(); resolve(); };
    cont.addEventListener('click', finish);
    if (!left) { cont.disabled = false; return; }
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
