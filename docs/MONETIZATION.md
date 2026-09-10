# Monetization plan (policy-aware)

## Important policy finding

Do **not** assume AdSense can monetize the downloader itself.

Google Publisher Policies list pages that help users download streaming videos when the content provider prohibits downloading as an example of disallowed "enabling dishonest behavior." YouTube's Terms also restrict downloading except where the service expressly authorizes it, the relevant rights holders give permission, or applicable law permits it.

Therefore:

- Do not put AdSense display ads, AdSense Offerwall, or other Google publisher monetization on the YouTube downloader flow without a policy/legal review that specifically clears the use case.
- AdSense Offerwall being a supported rewarded format does **not** override Publisher Policies.
- Never require a user to click a normal ad to unlock a download.
- Never style ads to look like Download buttons.

## 2026 benchmark findings

Observed business models across comparable downloader services:

- **SSSTik / SnapTik-style tools:** free utility funded mainly by display ads, ad walls, interstitials or occasional pop-ups. This maximizes short-term ad RPM but creates substantial UX and trust costs.
- **SaveFrom-style tools:** advertising plus a direct upsell to a desktop downloader / premium product. The free web tool acts as an acquisition funnel.
- **ThreadsDownloader.com:** public policy pages disclose Google AdSense and Monumetric, showing that some downloader publishers combine multiple display-ad demand sources. Eligibility can vary by page, geography and policy review, so this is not a blanket approval signal for our downloader flow.
- **SaveInsta-style tools:** free web downloader plus Android-app installation funnel, allowing the operator to monetize repeat users in an app environment.
- **Downloader mobile-app templates/products:** commonly combine AdMob, AppLovin or Meta Audience Network with banner/interstitial/native/open-app ads and, in some cases, an in-app purchase to remove ads.
- **Cleaner newer tools:** some deliberately advertise a no-popup/no-fake-button experience. This indicates that low-friction UX itself can be a competitive advantage even when monetization is less aggressive.

### What to copy

- Keep the core downloader free and friction-light.
- Treat the web product as both a utility and a funnel for higher-value monetization.
- Use clearly labeled sponsor placements around results and after completion.
- Add affiliate placements that match downloader intent: storage, creator tools, editing software, backup, VPN/security only where the affiliate program permits the placement.
- When traffic justifies it, sell direct monthly sponsorships rather than relying entirely on remnant display ads.
- Later add an optional premium tier: ad-free experience, faster queue, larger files, batch downloads and saved history where technically/legal-policy appropriate.
- If an Android/iOS companion app is launched later, evaluate mobile-native ad networks and an ad-removal purchase separately from the web monetization stack.

### What not to copy

- fake Download buttons
- pop-under / redirect traps
- mandatory ad clicks
- multiple interstitial loops before one download
- misleading countdowns
- aggressive placements that materially increase abandonment or malware-like perception

## Recommended revenue stack

### 1. Direct sponsor / affiliate view gate

The project includes an **optional, disabled-by-default** direct sponsor gate in `web/public/monetization.js`.

Recommended behavior:

1. User analyzes the URL for free.
2. User chooses a file.
3. A clearly labeled sponsor/affiliate message is shown for 3–5 seconds.
4. The Continue button unlocks automatically.
5. Clicking the sponsor is optional and never required.
6. Download preparation begins.

This can be sold directly on CPM/fixed sponsorship terms or used with an affiliate campaign whose terms allow the placement. Do not place Google ads inside this gate.

### 2. Affiliate modules on editorial/help content

For Korean traffic, product modules can focus on creator/storage gear (SSDs, card readers, phone accessories, microphones, tripods). Coupang Partners may be tested only in placements that comply with its current terms and with a clear affiliate disclosure.

For international traffic, consider Amazon/creator-tool affiliate programs where eligible.

### 3. Direct sponsorship inventory

Sell placements such as:

- "Sponsored by" result card
- post-download sponsor card
- creator-tool promotion
- storage/backup sponsor
- video editing software sponsor

A direct sponsor is operationally attractive because the site owner controls the format and does not depend on a general ad network deciding that the downloader category is eligible.

### 4. Search/content pages

Create genuinely useful troubleshooting and platform-guide pages. If a page is independently policy-compliant, ad eligibility can be evaluated separately. Do not create thin doorway pages or pages whose only purpose is displaying ads.

### 5. Premium tier after usage data exists

Do not launch paid plans blindly. First collect enough anonymous aggregate usage data to identify whether users value higher file limits, faster processing, batch workflows or ad removal. Then test a simple paid tier rather than fragmenting the product into many plans.

## Settlement / payout requirement

Revenue is not automatically sent to a bank account by this website. Each monetization provider or affiliate network accrues earnings in the owner's publisher/affiliate account and pays out using the payout method configured in that provider.

Before any live revenue integration is enabled, complete this checklist:

1. Create/approve the publisher, affiliate or direct-sponsor account.
2. Configure the provider's payout profile (bank transfer, PayPal, Payoneer or another supported method, depending on provider and country).
3. Complete identity/tax verification when required.
4. Store only the public campaign/publisher identifiers in frontend code; private API keys or secrets must remain server-side or in deployment secrets.
5. Run a test conversion/click event where the provider supports it.
6. Verify reporting attribution before increasing ad frequency.

Until a real revenue account and payout destination are configured, monetization links remain disabled or non-revenue placeholders.

## Optimization policy

Optimize for **revenue per 1,000 completed downloads**, not raw clicks or raw impressions. A placement that raises CTR but reduces completed downloads or repeat usage can lower total revenue.

Default sequence:

1. Baseline: no intrusive ads, measure completed downloads.
2. Test one result-page sponsor placement.
3. Test post-download sponsor placement.
4. Test affiliate modules on help/editorial pages.
5. Compare by geography and device type.
6. Increase frequency only when revenue lift exceeds the loss in completed downloads and retention.
7. Once traffic is material, compare direct sponsorship revenue against ad-network RPM before adding more ad inventory.

## Metrics to track

- analyses per platform
- successful downloads per platform
- failure rate by extractor
- average output MB
- outbound GB
- sponsor impressions
- sponsor optional click-through rate
- affiliate conversions
- revenue per 1,000 completed downloads
- server cost per 1,000 completed downloads
- download completion rate before/after each monetization experiment
- repeat-visitor rate
- revenue by country, platform and device class

## Avoid

- "Click this ad to download"
- fake download buttons
- forced affiliate clicks
- pop-under networks
- misleading countdowns
- repeated forced refreshes for impressions
- AdSense on downloader flows that conflict with Google Publisher Policies
