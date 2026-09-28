import Reveal from 'reveal.js';
import RevealMarkdown from 'reveal.js/plugin/markdown';
import RevealHighlight from 'reveal.js/plugin/highlight';
import RevealNotes from 'reveal.js/plugin/notes';
import Chart from 'chart.js/auto';

import feedstockHistory from './feedstock-count-history.json';
import maintainerCountries from './maintainer-countries.json';

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

// --- Feedstock count chart ---------------------------------------------------
// Colors and fonts come from the theme tokens so the chart matches the deck.
const theme = getComputedStyle(document.documentElement);
const token = (name) => theme.getPropertyValue(name).trim();
const primary = token('--cf-primary');

// Chart.js defaults assume a normal web page; the deck is a 1920x1080 canvas.
Chart.defaults.font.family = token('--r-main-font');
// Axis labels use the deck's body text size (34px) so they read from the back
// of the room once reveal scales the canvas down.
Chart.defaults.font.size = parseFloat(token('--cf-type-body'));
Chart.defaults.color = token('--cf-ink-subtle');

const options = {
	responsive: true,
	maintainAspectRatio: false,
	plugins: {
		legend: { display: false }
	},
	scales: {
		y: {
			beginAtZero: true,
			ticks: {
				stepSize: 5000,
				// 5000 -> "5k"; the 0 label is hidden (null) to keep the origin clean.
				callback: (val) => val === 0 ? null : `${val / 1000}k`,
			},
		},
		x: {
			ticks: {
				// Every label is evaluated so each January gets a year tick;
				// Chart.js' default auto-skipping would drop most of them.
				autoSkip: false,
				maxRotation: 0,
				callback: function(val, index) {
					let date = new Date(Date.parse(this.getLabelForValue(val)));

					if ( date.getMonth() === 0 ) {
						return date.getFullYear();
					} else {
						return null;
					}
				}
			}
		}
	}
};

new Chart(document.getElementById('feedstock-chart'), {
	type: 'line',
	data: {
		labels: feedstockHistory.map((row) => row.date),
		datasets: [{
			label: 'Feedstocks',
			data: feedstockHistory.map((row) => row.feedstock_count),
			borderColor: primary,
			backgroundColor: primary,
			borderWidth: 4,
			pointRadius: 0,
		}],
	},
	options,
});

// --- Maintainer countries chart ----------------------------------------------
// Top ten countries by maintainer count, as horizontal bars (sorted descending
// in the JSON, so the largest bar sits on top).
const topCountries = maintainerCountries.slice(0, 10);

new Chart(document.getElementById('countries-chart'), {
	type: 'bar',
	data: {
		labels: topCountries.map((row) => row.country),
		datasets: [{
			label: 'Maintainers',
			data: topCountries.map((row) => row.maintainers),
			backgroundColor: primary,
			borderRadius: 4,
		}],
	},
	options: {
		indexAxis: 'y',
		responsive: true,
		maintainAspectRatio: false,
		plugins: {
			legend: { display: false },
		},
		scales: {
			x: {
				beginAtZero: true,
				grid: { display: false },
				ticks: { stepSize: 500 },
			},
			y: {
				grid: { display: false },
				ticks: { autoSkip: false, font: { size: parseFloat(token('--cf-type-micro')) } },
			},
		},
	},
});
