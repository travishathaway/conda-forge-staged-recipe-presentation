import Reveal from 'reveal.js';
import RevealMarkdown from 'reveal.js/plugin/markdown';
import RevealHighlight from 'reveal.js/plugin/highlight';
import RevealNotes from 'reveal.js/plugin/notes';
import Chart from 'chart.js/auto';
import { ChoroplethController, GeoFeature, ColorLogarithmicScale, ProjectionScale } from 'chartjs-chart-geo';
import { feature } from 'topojson-client';

import feedstockHistory from './feedstock-count-history.json';
import maintainerCountries from './maintainer-countries.json';
import worldAtlas from 'world-atlas/countries-50m.json';

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

// The theme CSS starts with an @import of web fonts. Firefox doesn't apply a
// stylesheet's rules until its @imports have loaded, so at this point the CSS
// variables can still be empty (charts then fall back to black/default
// colors and NaN sizes). Wait for them before reading any token.
for (let waited = 0; !token('--cf-primary') && waited < 10000; waited += 25) {
	await new Promise((resolve) => setTimeout(resolve, 25));
}

const primary = token('--cf-primary');

// Chart.js defaults assume a normal web page; the deck is a 1920x1080 canvas.
Chart.defaults.font.family = token('--r-main-font');
// Axis labels use the deck's body text size (34px) so they read from the back
// of the room once reveal scales the canvas down.
Chart.defaults.font.size = parseFloat(token('--cf-type-body'));
Chart.defaults.color = token('--cf-ink-subtle');

// Tooltips inherit the 34px axis size, which is oversized for a popover.
const tooltipFontSize = parseFloat(token('--cf-type-micro'));
Chart.defaults.plugins.tooltip.titleFont = { size: tooltipFontSize };
Chart.defaults.plugins.tooltip.bodyFont = { size: tooltipFontSize };
Chart.defaults.plugins.tooltip.padding = 12;
Chart.defaults.plugins.tooltip.boxPadding = 6;

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

// Years that get a highlighted point and a count label. Each maps to the
// January data point of that year.
const labelledYears = [2018, 2020, 2022, 2024];
const isLabelled = (row) => {
	const [year, month] = row.date.split('-').map(Number);
	return month === 1 && labelledYears.includes(year);
};
const lastIndex = feedstockHistory.length - 1;
const labelledIndexes = new Set([
	...feedstockHistory.flatMap((row, i) => isLabelled(row) ? [i] : []),
	lastIndex,
]);

// Small inline plugin (Chart.js has no built-in data labels): draws the count
// to the upper left of each labelled point, since the line rises to the right.
// The final point sits near the top of the plot, so its label goes to the left,
// vertically centred, to avoid being clipped above the chart area.
const pointLabels = {
	id: 'pointLabels',
	afterDatasetsDraw(chart) {
		const { ctx } = chart;
		const meta = chart.getDatasetMeta(0);
		ctx.save();
		ctx.font = `bold ${Chart.defaults.font.size}px ${Chart.defaults.font.family}`;
		ctx.fillStyle = token('--cf-ink');
		ctx.textAlign = 'right';
		for (const i of labelledIndexes) {
			const point = meta.data[i];
			const isLast = i === lastIndex;
			ctx.textBaseline = isLast ? 'middle' : 'bottom';
			ctx.fillText(
				feedstockHistory[i].feedstock_count.toLocaleString('en-US'),
				point.x - 14,
				isLast ? point.y : point.y - 14
			);
		}
		ctx.restore();
	},
};

new Chart(document.getElementById('feedstock-chart'), {
	type: 'line',
	plugins: [pointLabels],
	data: {
		labels: feedstockHistory.map((row) => row.date),
		datasets: [{
			label: 'Feedstocks',
			data: feedstockHistory.map((row) => row.feedstock_count),
			borderColor: primary,
			backgroundColor: primary,
			borderWidth: 4,
			pointRadius: (ctx) => labelledIndexes.has(ctx.dataIndex) ? 8 : 0,
		}],
	},
	options,
});

// --- Maintainer countries map ------------------------------------------------
// Choropleth of maintainers per country. The US has ~3x the next country and
// ~1800x the smallest, so the color scale is logarithmic; otherwise every
// other country would collapse into the palest shade.

// maintainer-countries.json uses common names; the Natural Earth data behind
// world-atlas uses its own for a few countries. Réunion (2 maintainers) is
// an overseas region of France in the map data, so it has no shape of its own.
const atlasNames = {
	'United States': 'United States of America',
	'Czech Republic': 'Czechia',
	'Türkiye': 'Turkey',
};
const maintainersByAtlasName = new Map(
	maintainerCountries.map((row) => [atlasNames[row.country] ?? row.country, row.maintainers])
);

// Antarctica has no maintainers and would shrink the rest of the world.
const countryShapes = feature(worldAtlas, worldAtlas.objects.countries).features
	.filter((shape) => shape.properties.name !== 'Antarctica');

// Linear blend from a pale tint of the primary color up to the primary itself.
const hexToRgb = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
const primaryRgb = hexToRgb(primary);
const paleRgb = primaryRgb.map((c) => Math.round(c + (255 - c) * 0.8));
const primaryRamp = (t) => {
	const [r, g, b] = paleRgb.map((c, i) => Math.round(c + (primaryRgb[i] - c) * t));
	return `rgb(${r}, ${g}, ${b})`;
};

// chartjs-chart-geo only accepts a d3 palette *name* through options (a function
// passed there gets treated as a scriptable option and called with the chart
// context), so a small subclass swaps in the primary-color ramp instead.
class PrimaryLogarithmicScale extends ColorLogarithmicScale {
	init(options) {
		super.init(options);
		this.interpolate = primaryRamp;
	}
}
PrimaryLogarithmicScale.id = 'primaryLogarithmic';

Chart.register(ChoroplethController, GeoFeature, PrimaryLogarithmicScale, ProjectionScale);

new Chart(document.getElementById('countries-chart'), {
	type: 'choropleth',
	data: {
		labels: countryShapes.map((shape) => shape.properties.name),
		datasets: [{
			label: 'Maintainers',
			data: countryShapes.map((shape) => ({
				feature: shape,
				// null = no maintainers found; drawn in the scale's "missing" color.
				value: maintainersByAtlasName.get(shape.properties.name) ?? null,
			})),
			borderColor: '#ffffff',
			borderWidth: 0.75,
		}],
	},
	options: {
		responsive: true,
		maintainAspectRatio: false,
		plugins: {
			legend: { display: false },
			tooltip: {
				callbacks: {
					// The choropleth controller blanks the title by default.
					title: (items) => items[0]?.chart.data.labels[items[0].dataIndex] ?? '',
					label: (ctx) => ctx.raw.value
						? `${ctx.raw.value.toLocaleString('en-US')} maintainers`
						: 'No maintainers listed',
				},
			},
		},
		scales: {
			projection: {
				axis: 'x',
				projection: 'equalEarth',
			},
			color: {
				axis: 'x',
				type: 'primaryLogarithmic',
				missing: '#e9eceb',
				min: 1,
				max: 2000,
				legend: {
					position: 'bottom-left',
					align: 'bottom',
					length: 300,
					width: 44,
					indicatorWidth: 12,
					// Room for the tick labels below the bar and the "1" at its left end.
					margin: { left: 20, bottom: 36, top: 0, right: 0 },
				},
				ticks: {
					font: { size: 20 },
					// Every tick is evaluated (most get an empty label); auto-skipping
					// would otherwise drop some of the labelled decades.
					autoSkip: false,
					// Log ticks land on 1, 10, 100, 1000 and the max; keep just the decades.
					callback: (val) => [1, 10, 100, 1000].includes(val) ? val.toLocaleString('en-US') : '',
				},
			},
		},
	},
});
