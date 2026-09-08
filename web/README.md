# Web frontend

Frontend implementation is intentionally separated from the backend-first MVP.

Recommended production frontend: Next.js, because the business model depends on indexable platform-specific landing pages, FAQs, policy pages, multilingual SEO, AdSense/Offerwall integration, analytics, and a fast paste/analyze/select/download flow.

Core UI contract:

1. URL input + Analyze button.
2. Platform auto-detection state.
3. Preview panel with title/author.
4. Media selection list returned by `/api/v1/analyze`.
5. Download action posts `{url, asset_id}` to `/api/v1/download`.
6. Rewarded-ad entitlement check occurs before the final download action, not before Analyze.
