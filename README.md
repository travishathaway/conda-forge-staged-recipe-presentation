# conda-forge deck template for reveal.js

Slide template whose colors and typography follow the
[conda-forge brand guide](https://conda-forge.org/style-guide/). Authored on a
fixed 1920×1080 canvas that reveal.js scales uniformly to the viewport.

## Quickstart

```sh
npm install
npm run dev      # Vite dev server with hot reload
npm run build    # static site in dist/ (base: './', works on GitHub Pages)
```

`npm run build` emits `dist/`; serve it with any static file server. Do **not**
load one of reveal's own themes or highlight.js stylesheets —
`theme/conda-forge.css` replaces both.

## What's in here

| Path | What it is |
| --- | --- |
| `index.html` | The deck. Slides only; no reveal init or theme `<link>`. |
| `main.js` | Imports reveal.js + plugins, imports CSS in the right order, calls `Reveal.initialize`. |
| `theme/conda-forge.css` | The theme — every color, type size and layout. |
| `assets/anvil-light.svg` | conda-forge anvil logo for light backgrounds. |
| `assets/anvil-dark.svg` | conda-forge anvil logo for dark backgrounds. |
| `vite.config.js` | Vite config (`base: './'` so built paths are relative). |
| `README.md` | This file. |

Fonts load from Google Fonts via `@import` at the top of the theme (Montserrat
for headings, Inter for body). To self-host, delete that line and add your own
`@font-face` rules for the two families.

## reveal.js configuration

Everything reveal-related lives in `main.js`:

- CSS import order is `reveal.js/reset.css` → `reveal.js/reveal.css` →
  `./theme/conda-forge.css`. Keep it that way: the theme must come last so it
  can override reveal's defaults. Do not add a `<link>` for the theme in
  `index.html`.
- `Reveal.initialize` sets `width: 1920, height: 1080, margin: 0,
  center: false`, `slideNumber: 'c/t'`, `transition: 'fade'`, and loads the
  Markdown, Highlight and Notes plugins. The theme's px tokens assume this
  canvas; reveal exposes it as `--slide-width`, `--slide-height` and
  `--slide-scale` on `.reveal-viewport`, which the theme reads.

## Authoring slides

reveal.js sets `display: block` inline on the active `<section>`, which would
override a flex layout, so every slide's layout lives on an inner wrapper:

```html
<section data-label="Two column">
  <div class="cf-slide cf-slide--split">
    <div>
      <span class="cf-eyebrow">Comparison</span>
      <h2>Two columns</h2>
    </div>
    <div class="cf-cols">
      <div class="cf-col"><h3>Column one</h3><p class="cf-muted">…</p></div>
      <div class="cf-col"><h3>Column two</h3><p class="cf-muted">…</p></div>
    </div>
  </div>
  <aside class="notes">Speaker notes. Press S for the notes window.</aside>
</section>
```

Layout classes on `.cf-slide`:

| Class | Layout | Section attribute |
| --- | --- | --- |
| `cf-slide--title` | Title slide with logo, rule and meta row | `data-background-color="var(--cf-surface)"` |
| `cf-slide--divider` | Section divider, big section number | `data-background-gradient="var(--cf-gradient)"` |
| *(no modifier)* | Bulleted content, code, tables | — |
| `cf-slide--split` | Two columns (`.cf-cols` > `.cf-col`) | — |
| `cf-slide--stat` | One big figure; `.cf-stat-row` for three across | — |
| `cf-slide--quote` | Pull quote + attribution | `data-background-color="var(--cf-surface)"` |
| `cf-slide--bleed` | Full-bleed image with caption protection gradient | `data-background-image="…" data-background-size="cover"` |
| `cf-slide--end` | Closing slide with links | `data-background-gradient="var(--cf-gradient)"` |

### Colored and photo slides

The `.cf-slide` wrapper only covers the 1920×1080 canvas. reveal letterboxes
the canvas on viewports that are not 16:9, so a background painted on
`.cf-slide` would stop short of the viewport edge. Colored slides therefore set
the background on the `<section>` with reveal's `data-background-color`,
`data-background-gradient` or `data-background-image` attributes (third column
above) **in addition to** the layout class. reveal paints those on its
viewport-filling `.backgrounds` layer, and its PDF export places them inside
each printed page. CSS custom properties are fine in the attribute values, so
the dark-mode toggle still recolors them.

Helpers: `.cf-eyebrow` (small uppercase kicker), `.cf-lede`, `.cf-small`,
`.cf-muted`, `.cf-rule` (gradient bar), `.cf-card`, `.cf-spacer` (pushes
following content to the bottom), `.cf-attrib`, `.cf-stat`, `.cf-num`
(right-aligned tabular table figures).

`data-state="bare"` on a `<section>` hides the footer, watermark and slide
number — used on the title, dividers, full-bleed and closing slides.

Fragments: add `class="fragment"` to reveal items one at a time (see the
bulleted slide).

## Chrome

The footer and anvil watermark live in `<div class="cf-chrome">` at the end of
`.reveal`, outside `.slides`, so they persist across slides. `.cf-chrome` is a
1920×1080 layer that the theme positions and scales exactly like reveal
positions `.slides` (via `--slide-scale`), so the footer's left edge lines up
with slide content at any window size. Edit the footer text once in
`.cf-footer`.

reveal renders its own slide counter (`.slide-number`) outside `.cf-chrome`;
the theme repositions it onto the footer line with a `calc()` on the same
variables.

## Dark mode

Add `cf-dark` to `<html>`. The button top-right toggles it; delete the button
and hard-code the class if you present in one mode only.

## Resizing everything

Type scale and page padding are custom properties in `:root`
(`--cf-type-title`, `--cf-type-body`, `--cf-pad-x`, `--cf-pad-bottom`, …).
Change one number to re-scale the whole deck. The canvas itself is set in
`main.js` (`width`/`height`); the theme follows it through `--slide-width` /
`--slide-height`.

## Colors

Primary `#008478` light / `#4db6ac` dark · gradient
`linear-gradient(60deg, #00695c 20%, #26a69a 80%)` · teal ramp `#e0f2f1` →
`#004d40` · system colors `#1976d2` info, `#388e3c` success, `#ef6c00` warning,
`#d84315` danger.

## Images

The full-bleed slide ships with the brand gradient as a stand-in. For a real
photo, replace `data-background-gradient="var(--cf-gradient)"` on that
`<section>` with `data-background-image="assets/photo.jpg"
data-background-size="cover"`. The caption block (`.cf-bleed-caption`) stays as
is.

## PDF export

Append `?print-pdf` to the URL and print from the browser — one page per slide.
