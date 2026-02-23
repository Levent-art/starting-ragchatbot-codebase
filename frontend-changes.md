# Frontend Changes

## Feature: Dark / Light Theme Toggle

### Summary
Added a theme toggle button that lets users switch between the existing dark theme and a new light theme. The preference is persisted in `localStorage` so it survives page reloads. A brief transition animation smoothly crossfades colors when the theme switches.

---

### `frontend/index.html`

1. **Anti-FOUC inline script (in `<head>`)** — Reads `localStorage` and sets `data-theme` on `<html>` before the page renders, preventing a flash of the wrong theme on page load.

2. **Theme toggle `<button>` (before closing `</body>`)** — Fixed-position button containing two SVG icons:
   - **Sun icon** — shown in dark mode; clicking switches to light.
   - **Moon icon** — shown in light mode; clicking switches to dark.
   - `aria-label` and `title` attributes for accessibility.

3. **Cache-busting versions bumped** — `style.css?v=10 → v=11`, `script.js?v=9 → v=10`.

---

### `frontend/style.css`

1. **`[data-theme="light"]` CSS custom properties** — Full override of every CSS variable for the light theme:
   - `--background: #f8fafc` (near-white page background)
   - `--surface: #ffffff` (card/sidebar background)
   - `--surface-hover: #f1f5f9`
   - `--text-primary: #0f172a` (near-black for strong contrast)
   - `--text-secondary: #64748b`
   - `--border-color: #e2e8f0`
   - `--shadow: 0 4px 6px -1px rgba(0,0,0,0.1)` (lighter shadow)
   - All other variables (`--primary-color`, `--user-message`, etc.) are unchanged.

2. **`.theme-toggle` button styles** — Fixed to `top: 1rem; right: 1rem; z-index: 1000`. Circular (40 × 40 px), blends with surface/border variables. Hover scales up slightly and adopts `--primary-color`. Focus shows a `box-shadow` focus ring for keyboard accessibility.

3. **Icon visibility rules** — `.sun-icon` visible by default (dark mode); `.moon-icon` hidden. `[data-theme="light"]` inverts this.

4. **Light-mode source chip contrast fix** — In light mode, source chip text is set to `#2563eb` (the primary blue) instead of the dark-mode `#93b4f5` (which would be too pale on a white background).

---

### `frontend/script.js`

1. **`toggleTheme()` function** — Reads the current `data-theme` attribute on `<html>`, flips it between `'dark'` and `'light'`, writes the new value to `localStorage`. Before switching it temporarily injects a `<style>` tag that forces `transition` on all elements for 350 ms, producing a smooth crossfade without conflicting with component-level transitions.

2. **DOMContentLoaded wiring** — `document.getElementById('themeToggle').addEventListener('click', toggleTheme)` added alongside the existing event-listener setup.
