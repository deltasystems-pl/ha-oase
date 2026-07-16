# OASE brand assets

Home Assistant does **not** load icons/logos from a custom integration. Brand images live
in the central [`home-assistant/brands`](https://github.com/home-assistant/brands) repository
and are served from `https://brands.home-assistant.io/`. This folder only documents what has
to be submitted there; it deliberately contains **no binary images** (none are fabricated).

## Required files

Submit these under `custom_integrations/oase/` in `home-assistant/brands`:

| File | Size | Purpose |
|------|------|---------|
| `icon.png` | 256×256 | Square icon (the device/brand mark). Required. |
| `icon@2x.png` | 512×512 | High-DPI icon. Required. |
| `logo.png` | ≤ 512×512 (landscape ok) | Wordmark/logo shown in the UI. Optional but recommended. |
| `logo@2x.png` | 2× of `logo.png` | High-DPI logo. Optional. |
| `dark_icon.png` / `dark_icon@2x.png` | as above | Optional variants used on dark backgrounds. |
| `dark_logo.png` / `dark_logo@2x.png` | as above | Optional dark-mode logo variants. |

## Rules (from the brands repo)

- PNG, transparent background, trimmed to the content (no surrounding padding).
- `icon.png` must be square; `logo.png` may be landscape.
- Provide the `@2x` variant for every image you submit.
- Use official OASE artwork **only** if licensing permits redistribution; otherwise ship a
  neutral, non-infringing placeholder. This integration is **not affiliated with OASE GmbH**.

## Submission steps

1. Fork `home-assistant/brands`.
2. Add the files under `custom_integrations/oase/`.
3. Open a PR; the brands CI validates dimensions/format.
4. Once merged, the icons appear automatically for the `oase` domain — no change is needed
   in this repository.

See the [brands contributing guide](https://github.com/home-assistant/brands#readme) for the
authoritative, current requirements.
