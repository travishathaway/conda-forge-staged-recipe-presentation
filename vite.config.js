import { defineConfig } from 'vite';

export default defineConfig({
	// Use relative asset paths so the built site works whether it's served
	// from a GitHub Pages user/org root (https://<user>.github.io/) or a
	// project subpath (https://<user>.github.io/<repo>/).
	base: './',
});
