# Monetization plan (policy-aware)

## Important policy finding

Do **not** assume AdSense can monetize the downloader itself.

Google Publisher Policies list pages that help users download streaming videos when the content provider prohibits downloading as an example of disallowed "enabling dishonest behavior." YouTube's Terms also restrict downloading except where the service expressly authorizes it, the relevant rights holders give permission, or applicable law permits it.

Therefore:

- Do not put AdSense display ads, AdSense Offerwall, or other Google publisher monetization on the YouTube downloader flow without a policy/legal review that specifically clears the use case.
- AdSense Offerwall being a supported rewarded format does **not** override Publisher Policies.
- Never require a user to click a normal ad to unlock a download.
- Never style ads to look like Download buttons.

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

## Avoid

- "Click this ad to download"
- fake download buttons
- forced affiliate clicks
- pop-under networks
- misleading countdowns
- repeated forced refreshes for impressions
- AdSense on downloader flows that conflict with Google Publisher Policies
