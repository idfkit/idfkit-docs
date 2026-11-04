import { defineConfig } from 'vite';
import { readFileSync } from 'fs';
import path from 'path';

/** The @idfkit packages the bundle is built from, released in lockstep. */
const IDFKIT_PACKAGES = ['@idfkit/core', '@idfkit/language', '@idfkit/schemas'] as const;

/**
 * The installed version of one package. The packages' export maps do not
 * expose package.json, so it is read from disk rather than imported.
 */
function installedVersion(name: string): string {
  const manifest = JSON.parse(
    readFileSync(path.resolve(__dirname, 'node_modules', name, 'package.json'), 'utf-8')
  ) as { version: string };
  return manifest.version;
}

/**
 * The single version of the @idfkit packages. `@idfkit/core` depends on an
 * exact `@idfkit/schemas`, so pins that differ install a second, nested copy
 * and the bundle would mix two releases. The build stops rather than ship that.
 */
function idfkitVersion(): string {
  const installed = IDFKIT_PACKAGES.map((name) => ({ name, version: installedVersion(name) }));
  const versions = new Set(installed.map(({ version }) => version));
  if (versions.size !== 1) {
    const listed = installed.map(({ name, version }) => `${name}@${version}`).join(', ');
    throw new Error(`The @idfkit packages must be pinned to one version; installed: ${listed}`);
  }
  return installed[0].version;
}

/**
 * The bundle fetches schema data from jsDelivr at exactly the installed
 * @idfkit/schemas version, so the data always matches the code that reads it.
 */
const schemasVersion = idfkitVersion();

export default defineConfig({
  define: {
    __IDFKIT_SCHEMAS_VERSION__: JSON.stringify(schemasVersion),
  },
  build: {
    lib: {
      entry: path.resolve(__dirname, 'src/main.ts'),
      name: 'IDFEditor',
      formats: ['iife'],
      fileName: () => 'idf-editor.js',
    },
    outDir: path.resolve(__dirname, 'dist'),
    cssFileName: 'idf-editor',
    minify: 'esbuild',
    sourcemap: false,
    rollupOptions: {
      output: {
        assetFileNames: 'idf-editor.[ext]',
      },
    },
  },
});
