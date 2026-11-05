<script setup lang="ts">
/**
 * 抓包页：上传 pcap → 报文列表 / 时序图 / 字段树三者联动 → 把某个会话变成动画。
 *
 * 三个面板共享一个 selectedIndex（Packet 列表选中项），
 * 这就是设计文档 4.3 里"单一事实来源"的最小形态：
 * 不维护三份状态，只有一份"当前选中的报文"。
 */
import { computed, ref } from 'vue';
import {
  ApiError,
  captureApi,
  uploadCapture,
  type CapturePacket,
  type CaptureParsed,
  type CaptureSession,
} from './api';

const emit = defineEmits<{ (e: 'use-motion', payload: any): void }>();

const parsed = ref<CaptureParsed | null>(null);
const sessionId = ref('');
const selectedIndex = ref(0);
const busy = ref(false);
const error = ref('');
const durationSec = ref(12);
const dragging = ref(false);
const filename = ref('');

const sessions = computed<CaptureSession[]>(() => parsed.value?.sessions ?? []);
const session = computed<CaptureSession | null>(
  () => sessions.value.find((s) => s.id === sessionId.value) ?? null,
);

/** 当前会话里的报文，按原始顺序 */
const packets = computed<CapturePacket[]>(() => {
  if (!parsed.value || !session.value) return [];
  const ids = new Set(session.value.packetIndexes);
  return parsed.value.packets.filter((p) => ids.has(p.index));
});

const selected = computed<CapturePacket | null>(
  () => packets.value.find((p) => p.index === selectedIndex.value) ?? packets.value[0] ?? null,
);

/** 字段树：把扁平字段按前缀分组，ip.* / tcp.* / http.* 各成一段 */
const fieldGroups = computed<{ name: string; rows: [string, string][] }[]>(() => {
  const p = selected.value;
  if (!p) return [];
  const groups = new Map<string, [string, string][]>();
  for (const [key, value] of Object.entries(p.fields)) {
    const prefix = key.includes('.') ? key.split('.')[0] : 'frame';
    if (!groups.has(prefix)) groups.set(prefix, []);
    groups.get(prefix)!.push([key, value]);
  }
  return [...groups.entries()].map(([name, rows]) => ({name, rows}));
});

function pickSession(id: string) {
  sessionId.value = id;
  const s = sessions.value.find((x) => x.id === id);
  selectedIndex.value = s?.packetIndexes[0] ?? 0;
}

async function handleFile(file: File) {
  busy.value = true;
  error.value = '';
  try {
    const res = await uploadCapture(file);
    parsed.value = res.parsed;
    filename.value = res.parsed.filename;
    // 默认选"报文最多"的那个会话，通常就是主连接
    const main = [...res.parsed.sessions].sort((a, b) => b.packetCount - a.packetCount)[0];
    pickSession(main?.id ?? res.parsed.sessions[0]?.id ?? '');
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : String(e);
  } finally {
    busy.value = false;
  }
}

function onPick(ev: Event) {
  const input = ev.target as HTMLInputElement;
  if (input.files?.[0]) handleFile(input.files[0]);
}

function onDrop(ev: DragEvent) {
  dragging.value = false;
  const file = ev.dataTransfer?.files?.[0];
  if (file) handleFile(file);
}

async function toMotion() {
  if (!session.value || !parsed.value) return;
  busy.value = true;
  error.value = '';
  try {
    const res = await captureApi.animate(session.value, parsed.value.packets, durationSec.value);
    emit('use-motion', res);
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : String(e);
  } finally {
    busy.value = false;
  }
}

/** 时序图纵向排布：每条报文一根箭，行高随条数压缩，最多 200 行以内都还算清楚 */
const rowH = computed(() => (packets.value.length > 14 ? 30 : 44));
const svgH = computed(() => Math.max(160, packets.value.length * rowH.value + 48));

function arrowY(i: number) {
  return 34 + i * rowH.value;
}

function fmtKB(bytes: number) {
  return bytes < 1024 ? `${bytes} B` : `${(bytes / 1024).toFixed(1)} KB`;
}
</script>

<template>
  <div class="cap">
    <!-- 未上传：落地页 -->
    <div v-if="!parsed" class="cap-empty">
      <div
        class="dropzone"
        :class="{hot: dragging}"
        @dragover.prevent="dragging = true"
        @dragleave.prevent="dragging = false"
        @drop.prevent="onDrop"
      >
        <div class="drop-icon">⤓</div>
        <h2>把 .pcap / .pcapng 拖进来</h2>
        <p>
          用 Wireshark 抓一段流量 →「文件 / 另存为」选 pcap 格式 → 拖到这里。<br />
          也可以先看仓库里的样例：<code>samples/http-handshake.pcap</code>
        </p>
        <label class="primary file-btn">
          <input type="file" accept=".pcap,.pcapng,.cap" @change="onPick" />
          选择文件
        </label>
        <p class="tiny">单个文件 ≤ 12 MB / 5000 个报文；只解析 IPv4、IPv6、TCP、UDP、ICMP、ARP。</p>
      </div>
      <p v-if="busy" class="hint">正在解析…</p>
      <p v-if="error" class="err">{{ error }}</p>
    </div>

    <!-- 已上传：三栏联动 -->
    <div v-else class="cap-body">
      <aside class="cap-col sessions">
        <div class="col-head">
          <strong>{{ filename }}</strong>
          <span>{{ parsed.packetCount }} 包 · {{ parsed.sessionCount }} 会话 · {{ fmtKB(parsed.size) }}</span>
        </div>
        <ul>
          <li
            v-for="s in sessions"
            :key="s.id"
            :class="{active: s.id === sessionId}"
            @click="pickSession(s.id)"
          >
            <strong>{{ s.label }}</strong>
            <span>{{ s.client }}<template v-if="s.clientPort">:{{ s.clientPort }}</template> → {{ s.server }}<template v-if="s.serverPort">:{{ s.serverPort }}</template></span>
            <em>{{ s.packetCount }} 包 · {{ s.durationMs }} ms</em>
          </li>
        </ul>
        <label class="ghost file-btn small">
          <input type="file" accept=".pcap,.pcapng,.cap" @change="onPick" />
          换一个文件
        </label>
      </aside>

      <section class="cap-col packets">
        <div class="col-head">
          <strong>报文列表</strong>
          <span>点一行，右边两个视图跟着走</span>
        </div>
        <ol>
          <li
            v-for="p in packets"
            :key="p.index"
            :class="{active: p.index === selected?.index}"
            @click="selectedIndex = p.index"
          >
            <em>#{{ p.index }}</em>
            <span class="t">{{ p.time }}</span>
            <span class="sum">{{ p.summary }}</span>
            <span class="len">{{ p.length }}B</span>
          </li>
        </ol>
      </section>

      <section class="cap-col detail">
        <div class="seq-wrap">
          <div class="col-head">
            <strong>时序图</strong>
            <span v-if="session">{{ session.client }} ↔ {{ session.server }}</span>
          </div>
          <svg :viewBox="`0 0 600 ${svgH}`" class="seq" preserveAspectRatio="xMidYMin meet">
            <line x1="120" :y1="16" x2="120" :y2="svgH - 12" class="life" />
            <line x1="480" :y1="16" x2="480" :y2="svgH - 12" class="life" />
            <text x="120" y="12" class="who">{{ session?.client }}</text>
            <text x="480" y="12" class="who" text-anchor="end">{{ session?.server }}</text>

            <g v-for="(p, i) in packets" :key="p.index" @click="selectedIndex = p.index">
              <line
                :x1="p.src === session?.client ? 120 : 480"
                :y1="arrowY(i)"
                :x2="p.src === session?.client ? 480 : 120"
                :y2="arrowY(i)"
                class="arrow"
                :class="{on: p.index === selected?.index, rev: p.src !== session?.client}"
              />
              <!-- 箭头尖 -->
              <polygon
                :points="
                  p.src === session?.client
                    ? `472,${arrowY(i) - 5} 484,${arrowY(i)} 472,${arrowY(i) + 5}`
                    : `128,${arrowY(i) - 5} 116,${arrowY(i)} 128,${arrowY(i) + 5}`
                "
                class="head"
                :class="{on: p.index === selected?.index}"
              />
              <text :x="300" :y="arrowY(i) - 7" class="alabel" :class="{on: p.index === selected?.index}">
                {{ p.summary }}
              </text>
            </g>
          </svg>
        </div>

        <div class="fields">
          <div class="col-head">
            <strong>字段树</strong>
            <span v-if="selected">第 {{ selected.index }} 个报文</span>
          </div>
          <div v-if="selected" class="field-body">
            <div v-for="g in fieldGroups" :key="g.name" class="fgroup">
              <div class="fname">▾ {{ g.name }}</div>
              <div v-for="[k, v] in g.rows" :key="k" class="frow">
                <span class="k">{{ k }}</span>
                <span class="v">{{ v }}</span>
              </div>
            </div>
          </div>
        </div>

        <div class="cap-action">
          <label class="dur">
            时长
            <input v-model.number="durationSec" type="range" min="6" max="30" step="1" />
            <b>{{ durationSec }}s</b>
          </label>
          <button class="primary" :disabled="busy || !session" @click="toMotion">
            {{ busy ? '正在翻译…' : '把这个会话变成动画 →' }}
          </button>
        </div>
        <p v-if="error" class="err">{{ error }}</p>
      </section>
    </div>
  </div>
</template>

<style scoped>
.cap {
  height: 100%;
  padding: 16px 20px 20px;
}
.cap-empty {
  display: grid;
  place-items: center;
  height: 100%;
}
.dropzone {
  width: min(680px, 100%);
  padding: 44px 32px;
  text-align: center;
  border: 1.5px dashed rgba(255, 255, 255, 0.18);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.02);
  transition: 0.15s;
}
.dropzone.hot {
  border-color: var(--accent);
  background: rgba(255, 180, 84, 0.08);
}
.drop-icon {
  font-size: 34px;
  opacity: 0.7;
}
.dropzone h2 {
  margin: 10px 0 8px;
  font-size: 19px;
}
.dropzone p {
  color: var(--muted);
  font-size: 13px;
  line-height: 1.75;
}
.dropzone code {
  background: rgba(255, 255, 255, 0.07);
  padding: 1px 6px;
  border-radius: 5px;
}
.file-btn {
  display: inline-block;
  margin-top: 14px;
  cursor: pointer;
}
.file-btn input {
  display: none;
}
.file-btn.small {
  margin: 10px 12px;
  font-size: 12px;
  padding: 7px 10px;
  text-align: center;
}
.tiny {
  font-size: 11.5px !important;
  opacity: 0.6;
  margin-top: 14px;
}

.cap-body {
  display: grid;
  grid-template-columns: 240px 320px 1fr;
  gap: 14px;
  height: calc(100% - 4px);
  min-height: 0;
}
.cap-col {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 14px;
  overflow: auto;
  min-height: 0;
}
.cap-col.detail {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.col-head {
  padding: 12px 14px;
  border-bottom: 1px solid var(--line);
  display: flex;
  flex-direction: column;
  gap: 3px;
  position: sticky;
  top: 0;
  background: var(--panel);
  z-index: 2;
}
.col-head strong {
  font-size: 13px;
}
.col-head span {
  font-size: 11.5px;
  color: var(--muted);
}

.sessions ul,
.packets ol {
  list-style: none;
  margin: 0;
  padding: 6px;
}
.sessions li {
  padding: 9px 10px;
  border-radius: 10px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-bottom: 2px;
}
.sessions li:hover,
.packets li:hover {
  background: rgba(255, 255, 255, 0.04);
}
.sessions li.active {
  background: rgba(255, 180, 84, 0.13);
  box-shadow: inset 2px 0 0 var(--accent);
}
.sessions li strong {
  font-size: 12.5px;
}
.sessions li span,
.sessions li em {
  font-size: 11px;
  color: var(--muted);
  font-style: normal;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.packets li {
  display: grid;
  grid-template-columns: 38px 78px 1fr 34px;
  gap: 6px;
  align-items: center;
  padding: 6px 8px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 11.5px;
}
.packets li.active {
  background: rgba(87, 212, 160, 0.14);
  box-shadow: inset 2px 0 0 var(--accent-2);
}
.packets li em {
  color: var(--muted);
  font-style: normal;
}
.packets .t {
  color: #8ea0bb;
  font-variant-numeric: tabular-nums;
}
.packets .sum {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.packets .len {
  color: var(--muted);
  text-align: right;
}

.seq-wrap {
  flex: 0 0 auto;
  max-height: 46%;
  overflow: auto;
  border-bottom: 1px solid var(--line);
}
.seq {
  width: 100%;
  display: block;
}
.life {
  stroke: rgba(255, 255, 255, 0.16);
  stroke-dasharray: 4 4;
}
.who {
  fill: #8ea0bb;
  font-size: 10px;
}
.arrow {
  stroke: #4d6a92;
  stroke-width: 1.6;
}
.arrow.on {
  stroke: var(--accent);
  stroke-width: 2.6;
}
.head {
  fill: #4d6a92;
}
.head.on {
  fill: var(--accent);
}
.alabel {
  fill: #9fb0c8;
  font-size: 9.5px;
  text-anchor: middle;
}
.alabel.on {
  fill: var(--accent);
  font-weight: 600;
}

.fields {
  flex: 1 1 auto;
  overflow: auto;
  min-height: 0;
}
.field-body {
  padding: 6px 10px 12px;
  font-size: 11.5px;
}
.fgroup {
  margin-bottom: 8px;
}
.fname {
  color: #8ea0bb;
  padding: 4px 2px;
  font-weight: 600;
}
.frow {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  padding: 2px 2px 2px 12px;
  border-radius: 6px;
}
.frow:hover {
  background: rgba(255, 255, 255, 0.04);
}
.frow .k {
  color: #7f93ad;
  font-family: ui-monospace, Consolas, monospace;
  overflow: hidden;
  text-overflow: ellipsis;
}
.frow .v {
  font-family: ui-monospace, Consolas, monospace;
  color: #d7e0ee;
  overflow-wrap: anywhere;
}

.cap-action {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 14px;
  border-top: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.02);
}
.dur {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--muted);
}
.dur input {
  width: 110px;
}
.dur b {
  color: var(--accent);
  font-variant-numeric: tabular-nums;
}
.err {
  color: #ff8080;
  font-size: 12px;
  padding: 0 14px 10px;
}
</style>
