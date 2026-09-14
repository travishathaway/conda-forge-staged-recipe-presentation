import Reveal from 'reveal.js';
import RevealMarkdown from 'reveal.js/plugin/markdown';
import RevealHighlight from 'reveal.js/plugin/highlight';
import RevealNotes from 'reveal.js/plugin/notes';

// Order matters: reveal's base styles first, then the theme so it can
// override them. The theme carries its own highlight.js palette, so no
// hljs stylesheet from reveal is imported.
import 'reveal.js/reset.css';
import 'reveal.js/reveal.css';
import './theme/conda-forge.css';

// More info about initialization & config:
// - https://revealjs.com/initialization/
// - https://revealjs.com/config/
Reveal.initialize({
	// Fixed 1920x1080 canvas, uniformly scaled to the viewport. The theme's
	// sizing tokens (theme/conda-forge.css) assume this canvas.
	width: 1920,
	height: 1080,
	margin: 0,
	center: false,

	hash: true,
	slideNumber: 'c/t',
	transition: 'fade',
	transitionSpeed: 'fast',

	// Learn about plugins: https://revealjs.com/plugins/
	plugins: [RevealMarkdown, RevealHighlight, RevealNotes],
});
