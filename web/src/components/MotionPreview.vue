<script setup lang="ts">
/**
 * Vue ↔ React 的桥：把渲染工程里的 <Handshake />（Remotion Composition）
 * 塞进 @remotion/player，让浏览器里直接预览。
 *
 * 为什么不用 iframe / 另起页面：Player 与 Composition 必须共享同一份
 * remotion 运行时，跨 iframe 就要重新打包，还会因两份 context 报错。
 * 这里用 createRoot 挂一个 React 子树，Vue 只负责传 props。
 *
 * 注意：不要给 <Player> 传 ref。@remotion/player 4.0.540 在 React 18 开发模式下
 * 会把 ref 透传到内部的 AbsoluteFill，刷出两条 "Function components cannot be
 * given refs" 告警，看着像我们的 bug。需要控制播放就用 autoPlay/loop 这两个 props。
 *
 * 另外课程项目没有配音，autoPlay 必须配 muted，否则浏览器会拦下自动播放并把
 * Player 强制静音，控制台会多一条“已为你静音”的警告。
 */
import {onBeforeUnmount, onMounted, ref, watch} from 'vue';
import React from 'react';
import {createRoot, type Root} from 'react-dom/client';
import {Player} from '@remotion/player';
// @ts-expect-error —— 渲染工程用的是 TSX，类型交给 Vite 处理
import {Handshake} from '@motion/compositions/Handshake';

const props = defineProps<{inputProps: any}>();
const emit = defineEmits<{ready: []}>();

const host = ref<HTMLDivElement | null>(null);
let root: Root | null = null;

function render() {
  if (!root || !props.inputProps) return;
  const p = props.inputProps;
  root.render(
    React.createElement(Player, {
      component: Handshake,
      inputProps: p,
      durationInFrames: p.totalFrames,
      compositionWidth: p.width,
      compositionHeight: p.height,
      fps: p.fps,
      controls: true,
      loop: true,
      autoPlay: true,
      muted: true,
      // 公司规模超过 3 人时商业使用需购买 Remotion 许可；课程项目加上这句即可消除控制台提示
      acknowledgeRemotionLicense: true,
      style: {width: '100%', borderRadius: '12px', overflow: 'hidden'},
    }),
  );
}

onMounted(() => {
  if (!host.value) return;
  root = createRoot(host.value);
  render();
  requestAnimationFrame(() => emit('ready'));
});

watch(
  () => props.inputProps,
  () => render(),
  {deep: true},
);

onBeforeUnmount(() => {
  root?.unmount();
  root = null;
});
</script>

<template>
  <div ref="host" class="player-host" />
</template>

<style scoped>
.player-host {
  width: 100%;
  aspect-ratio: 16 / 9;
  background: #0b1020;
  border-radius: 12px;
  overflow: hidden;
}
</style>
