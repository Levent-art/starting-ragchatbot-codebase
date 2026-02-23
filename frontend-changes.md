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

---

## Frontend Quality Tools

### Summary

Added Prettier as the standard code formatter for all frontend files (JS, CSS, HTML), applied consistent formatting throughout, and created development scripts for running quality checks.

### New Files

#### `frontend/package.json`
- Introduces `npm` tooling for the frontend
- Dev dependency: `prettier@^3.0.0`
- Scripts:
  - `npm run format` — auto-format all `*.js`, `*.css`, `*.html` files
  - `npm run format:check` — CI-safe check that reports formatting violations without writing

#### `frontend/.prettierrc`
- Prettier configuration enforcing consistent style across all frontend files:
  - 2-space indentation
  - Single quotes in JS
  - Trailing commas where valid in ES5 (arrays, objects, function params)
  - 80-character print width
  - LF line endings
  - Semicolons on

#### `scripts/check-frontend.sh`
- Shell script to run `prettier --check` on the frontend directory
- Auto-installs npm dependencies if `node_modules` is absent
- Exits with a non-zero code on any formatting violation (suitable for CI)

#### `scripts/format-frontend.sh`
- Shell script to auto-format all frontend files with Prettier
- Auto-installs npm dependencies if `node_modules` is absent

### Modified Files

#### `frontend/script.js`
- Reformatted to match Prettier conventions:
  - 4-space indentation → 2-space
  - Added trailing commas to multi-line object/array literals
  - Arrow function parameters always wrapped in parens
  - Chained `.map(...).join(...)` split across lines for readability

#### `frontend/index.html`
- Reformatted to Prettier HTML conventions:
  - 2-space indentation throughout
  - `<!doctype html>` lowercased (Prettier default)
  - Self-closing void elements (`<meta />`, `<link />`, `<input />`)
  - Multi-attribute elements broken one-attribute-per-line for readability

#### `frontend/style.css`
- No changes needed — CSS was already consistently formatted.

### Usage

```bash
# Install dependencies (first time only)
npm install --prefix frontend

# Check formatting (CI / pre-commit)
./scripts/check-frontend.sh

# Auto-format all frontend files
./scripts/format-frontend.sh

# Or run directly via npm
npm run format --prefix frontend
npm run format:check --prefix frontend
```
