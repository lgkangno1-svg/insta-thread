# AVOCADOSS Download — Visual System

## Purpose

This document defines the production UI direction for `download.avocadoss.co.kr`.

The downloader is one product with one workflow, not five unrelated branded clones. Platform pages therefore share the AVOCADOSS structure and interaction model while using restrained platform-specific visual cues.

## Product invariants

The visual layer must not change these contracts:

- One URL input accepts every supported platform.
- Platform detection remains automatic.
- Existing canonical URLs, structured data, guide copy, FAQ content and legal boundaries remain intact unless a separate SEO/content change is explicitly reviewed.
- Existing `data-*` hooks used by `app.js` and `monetization.js` remain intact.
- Backend extraction, jobs, delivery, security and public/non-DRM scope are independent of the visual system.
- The primary action is always the downloader input and `Analyze link` button.

## Core AVOCADOSS direction

The shared product should feel like a premium utility rather than a generic SaaS landing page.

- Dark neutral canvas with restrained ambient color.
- High-contrast typography and generous first-viewport spacing.
- The URL input is the visual focal point.
- Fewer bordered cards, badges and pills.
- Editorial sections use open rails, dividers and tables instead of repeating card grids.
- Results remain framed because they represent the actual application output.
- Navigation and status chrome stay quiet so they do not compete with the task.
- Mobile keeps the same hierarchy: headline -> URL input -> analyze -> result.

## Platform personality

Platform accents are selected through `body[data-platform]` and implemented in `web/public/stitch.css`.

### All-in-one

AVOCADOSS mint/green remains the canonical product accent. This page is the neutral home of the service and should not visually privilege one supported source.

### Instagram

Use a restrained violet-to-rose accent around the primary action and ambient hero light. Keep the AVOCADOSS shell, typography and component anatomy. Do not imitate Instagram navigation or proprietary interface chrome.

The result area gives thumbnails slightly more room because Reel covers and image candidates are meaningful output choices.

### Threads

Use near-monochrome surfaces, white primary action and minimal decorative color. Typography and whitespace carry more of the identity. The page should feel conversational and direct rather than like a dashboard.

### Xiaohongshu

Use a refined red/coral accent and stronger media emphasis. Image-note assets receive slightly larger thumbnails. Do not clone Xiaohongshu's application interface.

### Douyin

Use restrained cyan with a secondary magenta trace. The main interaction remains a conventional downloader rather than a short-video feed recreation.

### YouTube

Use a restrained warm red accent. Prefer clarity, source/quality information and predictable controls over decorative styling.

## Component rules

### Header

Keep AVOCADOSS branding, essential navigation and a low-priority engine state. On small screens, navigation/status chrome may collapse before the primary task does.

### Hero

No decorative eyebrow/badge in production. Use one heading, one supporting paragraph and the downloader immediately below it.

### Downloader input

This is the product surface. It receives the strongest focus treatment and platform accent. Clear/Paste are secondary utilities; Analyze is the single primary action.

### Platform indicators

These are status indicators, not navigation tabs. Keep them quiet until the current URL/platform is active.

### Results

Keep a clearly framed result region. Media choices must remain code-native, readable and clickable. Platform accent can signal ready/download states without changing result semantics.

### Guides and troubleshooting

Prefer open columns/rails with dividers over repeated rounded cards. These sections support the downloader and SEO; they are not separate product dashboards.

### FAQ

Use editorial separators instead of card stacks. Native `details/summary` semantics stay intact.

## Accessibility

- Preserve keyboard focus visibility.
- Maintain text/background contrast.
- Do not rely on accent color alone to communicate an error.
- Respect `prefers-reduced-motion`.
- Controls remain code-native and retain existing accessible names and `data-*` hooks.

## Implementation

Base styles remain in `web/public/styles.css`.

The platform visual system is an additive override layer:

```html
<link rel="stylesheet" href="/styles.css?...">
<link rel="stylesheet" href="/stitch.css?v=20260912a">
```

This keeps the redesign reversible and limits risk to presentation. Removing the second stylesheet returns the current base UI without touching extraction behavior or SEO structure.
