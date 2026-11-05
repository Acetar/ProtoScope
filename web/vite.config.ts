import {fileURLToPath, URL} from 'node:url';
import {defineConfig} from 'vite';
import vue from '@vitejs/plugin-vue';

const here = fileURLToPath(new URL('.', import.meta.url));
const at = (p: string) => fileURLToPath(new URL(p, import.meta.url));

/**
 * 两个 alias 是有原因的：
 * 1. @motion → ../renderer/src，让 web 直接复用渲染工程里的 Composition，
 *    保证"预览"和"出片"跑的是同一份代码，不会出现预览对、成片错。
 * 2. react / react-dom / remotion / @remotion/player / zod 全部指向 web 自己的
 *    node_modules。不加这几条，Vite 会按"就近解析"去 renderer/node_modules 取，
 *    于是加载两份 remotion，Player 报 context 不匹配（错误信息通常是
 *    "useCurrentFrame can only be called inside a component that was "
 *    "passed to at least one <Composition />" 之类，很难看出是这份原因）。
 */
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: [
      {find: '@motion', replacement: at('../renderer/src')},
      {find: '@', replacement: at('./src')},
      {find: /^react$/, replacement: at('./node_modules/react')},
      {find: /^react\/jsx-runtime$/, replacement: at('./node_modules/react/jsx-runtime')},
      {find: /^react\/jsx-dev-runtime$/, replacement: at('./node_modules/react/jsx-dev-runtime')},
      {find: /^react-dom$/, replacement: at('./node_modules/react-dom')},
      {find: /^react-dom\/client$/, replacement: at('./node_modules/react-dom/client')},
      {find: /^remotion$/, replacement: at('./node_modules/remotion')},
      {find: /^@remotion\/player$/, replacement: at('./node_modules/@remotion/player')},
      {find: /^zod$/, replacement: at('./node_modules/zod')},
    ],
  },
  server: {
    port: 5173,
    // 允许读取仓库外的 ../renderer/src
    fs: {allow: ['..']},
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/media': 'http://127.0.0.1:8000',
    },
  },
  optimizeDeps: {
    include: ['react', 'react-dom', 'react-dom/client', 'remotion', '@remotion/player'],
  },
});
