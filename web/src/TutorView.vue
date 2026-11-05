<script setup lang="ts">
/**
 * AI 教师（B1 + B2）的会话界面。
 *
 * 布局参照 DeepSeek Harness：左边是会话语料库，中间是消息流。
 * 两条硬约束：
 * 1. 动画是"消息的一种"（kind='animation'），所以它出现在气泡之间，而不是挤到右侧另开一栏；
 * 2. 流式状态按会话 id 存（`busy` / `rows` 都是 map），切走再切回来不会打断，
 *    也能同时有多个会话在生成——这就是需求里的"并发操作"。
 */
import {computed, nextTick, onMounted, ref} from 'vue';
import MotionPreview from './components/MotionPreview.vue';
import {askTutor, conversationApi, type ChatMessage, type Conversation, type KnowledgePoint} from './api';

const props = defineProps<{points: KnowledgePoint[]}>();
const emit = defineEmits<{toast: [text: string]}>();

type Row = ChatMessage & {pending?: boolean; failed?: string};

const convs = ref<Conversation[]>([]);
const activeId = ref<number | null>(null);
/** 每个会话的消息缓存：切换会话时先渲染缓存，再从服务端刷新 */
const rows = ref<Record<number, Row[]>>({});
/** 每个会话是否正在流式回答（并发正是靠这个 map 支撑的） */
const busy = ref<Record<number, boolean>>({});
const drafts = ref<Record<number, string>>({});
const newTopic = ref('');
const loading = ref(false);
const error = ref('');
const bodyEl = ref<HTMLElement | null>(null);
const expanded = ref<any | null>(null);

const activeConv = computed(() => convs.value.find((c) => c.id === activeId.value) || null);
const activeRows = computed<Row[]>(() => (activeId.value ? rows.value[activeId.value] || [] : []));
const draft = computed({
  get: () => (activeId.value ? drafts.value[activeId.value] || '' : ''),
  set: (v: string) => {
    if (activeId.value) drafts.value[activeId.value] = v;
  },
});
const streaming = computed(() => (activeId.value ? !!busy.value[activeId.value] : false));

const PRESETS = [
  '为什么是三次握手，两次不行吗',
  'seq 和 ack 到底谁加 1',
  '这一步丢包了会怎样',
  '现实中怎么抓到这个字段',
];

function ago(iso: string): string {
  const t = new Date(iso).getTime();
  if (!t) return '';
  const gap = Date.now() - t;
  if (gap < 60_000) return '刚刚';
  if (gap < 3_600_000) return `${Math.floor(gap / 60_000)} 分钟前`;
  if (gap < 86_400_000) return `${Math.floor(gap / 3_600_000)} 小时前`;
  return `${Math.floor(gap / 86_400_000)} 天前`;
}

function scrollToBottom() {
  nextTick(() => {
    if (bodyEl.value) bodyEl.value.scrollTop = bodyEl.value.scrollHeight;
  });
}

function bump(id: number, snippet: string) {
  const idx = convs.value.findIndex((c) => c.id === id);
  if (idx < 0) return;
  const [item] = convs.value.splice(idx, 1);
  item.updatedAt = new Date().toISOString();
  item.lastSnippet = snippet.slice(0, 60);
  item.messageCount = (rows.value[id] || []).length || item.messageCount;
  convs.value.unshift(item);
}

async function ensureRows(id: number, force = false) {
  if (rows.value[id] && !force) return;
  rows.value[id] = await conversationApi.messages(id);
}

async function pick(id: number) {
  activeId.value = id;
  error.value = '';
  try {
    await ensureRows(id);
  } catch (e: any) {
    error.value = e?.message || '加载会话失败';
  }
  scrollToBottom();
}

async function load() {
  loading.value = true;
  try {
    convs.value = await conversationApi.list();
    if (!convs.value.length) {
      const conv = await conversationApi.create({});
      convs.value = [conv];
    }
    await pick(convs.value[0].id);
  } catch (e: any) {
    error.value = e?.message || '加载会话失败';
  } finally {
    loading.value = false;
  }
}

async function newChat() {
  try {
    const conv = await conversationApi.create({topicId: newTopic.value || undefined});
    convs.value.unshift(conv);
    rows.value[conv.id] = [];
    await pick(conv.id);
    emit('toast', '已新建会话');
  } catch (e: any) {
    error.value = e?.message || '新建会话失败';
  }
}

async function dropConv(id: number) {
  try {
    await conversationApi.remove(id);
    convs.value = convs.value.filter((c) => c.id !== id);
    delete rows.value[id];
    delete busy.value[id];
    if (!convs.value.length) await load();
    else if (activeId.value === id) await pick(convs.value[0].id);
    emit('toast', '会话已删除');
  } catch (e: any) {
    error.value = e?.message || '删除失败';
  }
}

async function send(text?: string) {
  const id = activeId.value;
  const question = (text ?? draft.value).trim();
  if (!id || !question || busy.value[id]) return;

  drafts.value[id] = '';
  error.value = '';
  const list = rows.value[id] || (rows.value[id] = []);
  const conv = convs.value.find((c) => c.id === id);
  list.push({
    id: -Date.now(),
    conversationId: id,
    role: 'user',
    kind: 'text',
    content: question,
    payload: null,
    pending: true,
  });
  list.push({
    id: -Date.now() - 1,
    conversationId: id,
    role: 'assistant',
    kind: 'text',
    content: '',
    payload: null,
    pending: true,
  });
  // 必须拿数组里的代理对象再改：直接改 push 进去的原始对象不会触发渲染
  const reply = list[list.length - 1];
  busy.value[id] = true;
  scrollToBottom();

  // 服务端识别出"他在要一段动画"时会推进来一个动作，等这条文字流结束后再真的去排
  let pendingAction: {type: string; topicId?: string; prompt?: string} | null = null;

  try {
    await askTutor(
      {question, conversationId: id, topic: conv?.topicId || undefined},
      {
        onToken: (piece) => {
          reply.content += piece;
          if (reply.id === list[list.length - 1].id) scrollToBottom();
        },
        onMeta: (meta) => {
          const u = list.find((r) => r.role === 'user' && r.pending);
          if (u && meta.userMessageId) u.id = meta.userMessageId;
        },
        onSaved: (saved) => {
          reply.id = saved.assistantMessageId;
        },
        onAction: (action) => {
          if (action?.type === 'animate') pendingAction = action;
        },
      },
    );
    reply.pending = false;
  } catch (e: any) {
    reply.pending = false;
    reply.failed = e?.message || '回答失败';
    if (!reply.content) {
      reply.content = '（这次没答上来，可以再问一次）';
    }
  } finally {
    busy.value[id] = false;
    const last = list[list.length - 1];
    bump(id, last?.content || question);
    scrollToBottom();
  }

  if (pendingAction) {
    await runAnimation(id, {
      prompt: pendingAction.prompt || question,
      topic: pendingAction.topicId || undefined,
      silent: true,
    });
  }
}

/** 在指定会话里排一段动画：聊天里识别到意图、或点底部"生成动画"都走这里 */
async function runAnimation(
  id: number,
  opts: {prompt: string; topic?: string; silent?: boolean},
) {
  const prompt = opts.prompt.trim();
  if (!id || !prompt) return;

  error.value = '';
  const list = rows.value[id] || (rows.value[id] = []);
  const placeholder: Row = {
    id: -Date.now(),
    conversationId: id,
    role: 'assistant',
    kind: 'animation',
    content: prompt,
    payload: null,
    pending: true,
  };
  list.push(placeholder);
  busy.value[id] = true;
  scrollToBottom();

  try {
    // 服务端会把「用户请求 + 动画消息」都写进会话，所以成功后以服务端为准重载一次
    await conversationApi.animate({
      conversationId: id,
      prompt,
      topic: opts.topic || undefined,
      durationSec: 16,
    });
    await ensureRows(id, true);
    const conv = convs.value.find((c) => c.id === id);
    if (conv) bump(id, '生成了动画');
    if (!opts.silent) emit('toast', '动画已生成');
  } catch (e: any) {
    rows.value[id] = list.filter((r) => r !== placeholder);
    error.value = e?.message || '生成动画失败';
  } finally {
    busy.value[id] = false;
    scrollToBottom();
  }
}

function animate() {
  const id = activeId.value;
  const prompt = draft.value.trim();
  if (!id || !prompt || busy.value[id]) return;
  drafts.value[id] = '';
  void runAnimation(id, {prompt});
}

function onKeydown(ev: KeyboardEvent) {
  if (ev.key === 'Enter' && !ev.shiftKey && !ev.isComposing) {
    ev.preventDefault();
    send();
  }
}

function frameInfo(row: Row): {frames: number; seconds: number} {
  const p = row.payload?.props;
  const frames = Number(p?.totalFrames || 0);
  const fps = Number(p?.fps || 30);
  return {frames, seconds: Math.round((frames / fps) * 10) / 10};
}

onMounted(load);
</script>

<template>
  <div class="tutor-app">
    <!-- 左：会话列表 -->
    <aside class="conv-side">
      <div class="conv-top">
        <button class="btn primary block" :disabled="loading" @click="newChat">＋ 新建对话</button>
        <select v-model="newTopic" class="conv-topic" title="新对话绑定的知识点">
          <option value="">不绑定知识点</option>
          <option v-for="p in props.points" :key="p.id" :value="p.id">{{ p.title }}</option>
        </select>
      </div>

      <div class="conv-list">
        <div
          v-for="c in convs"
          :key="c.id"
          class="conv-item"
          :class="{on: c.id === activeId}"
          :data-conv-id="c.id"
          @click="pick(c.id)"
        >
          <div class="conv-line">
            <span class="conv-title">{{ c.title }}</span>
            <span v-if="busy[c.id]" class="conv-dot" title="正在生成" />
          </div>
          <div class="conv-sub">
            <span>{{ ago(c.updatedAt) }}</span>
            <span v-if="c.messageCount">{{ c.messageCount }} 条</span>
          </div>
          <button class="conv-del" title="删除会话" @click.stop="dropConv(c.id)">×</button>
        </div>
        <p v-if="!convs.length && !loading" class="conv-empty">还没有会话，点上面新建一个。</p>
      </div>
    </aside>

    <!-- 右：消息流 -->
    <section class="chat-main">
      <header class="chat-head">
        <div>
          <h2>{{ activeConv?.title || 'AI 教师' }}</h2>
          <p class="chat-sub">
            <template v-if="activeConv?.topicId">
              知识点 · {{ props.points.find((p) => p.id === activeConv?.topicId)?.title || activeConv.topicId }}
            </template>
            <template v-else>可以问原理，也可以直接让它画一段动画</template>
          </p>
        </div>
        <span v-if="streaming" class="typing-chip">正在回答…</span>
      </header>

      <div ref="bodyEl" class="chat-body">
        <p v-if="error" class="chat-error">{{ error }}</p>

        <div v-if="!activeRows.length" class="chat-blank">
          <div class="blank-icon">✎</div>
          <h3>把不懂的地方直接问出来</h3>
          <p>我会用当前知识点的真实报文讲，不编数字；也可以让它把刚才讲的流程画成动画。</p>
          <div class="preset-row">
            <button v-for="q in PRESETS" :key="q" class="preset" @click="send(q)">{{ q }}</button>
          </div>
        </div>

        <div
          v-for="row in activeRows"
          :key="row.id"
          class="msg"
          :class="row.role"
        >
          <div class="avatar" :class="row.role">{{ row.role === 'user' ? '我' : '教' }}</div>

          <div class="bubble-wrap" :class="{wide: row.kind === 'animation'}">
            <!-- 动画消息：直接长在消息流里 -->
            <div v-if="row.kind === 'animation'" class="anim-card">
              <div class="anim-head">
                <span class="anim-title">
                  {{ row.payload?.props?.title || (row.pending ? '正在编排动画…' : '动画') }}
                </span>
                <span v-if="row.payload?.props" class="anim-meta">
                  {{ frameInfo(row).seconds }}s · {{ frameInfo(row).frames }} 帧
                </span>
              </div>
              <div v-if="row.pending && !row.payload" class="anim-skeleton">
                <span class="spinner" /> 正在把这段话翻译成分镜、时间轴和报文…
              </div>
              <template v-else-if="row.payload?.props">
                <MotionPreview :input-props="row.payload.props" />
                <div class="anim-actions">
                  <button class="btn tiny" @click="expanded = row.payload.props">全屏预览</button>
                  <span class="anim-src">
                    来源 · {{ row.payload?.meta?.source === 'llm' ? '大模型生成' : '规则库' }}
                  </span>
                </div>
              </template>
            </div>

            <!-- 文本消息 -->
            <div v-else class="bubble">
              <template v-if="row.content">{{ row.content }}</template>
              <span v-else-if="row.pending" class="typing"><i /><i /><i /></span>
              <span v-if="row.failed" class="msg-fail">{{ row.failed }}</span>
            </div>
          </div>
        </div>
      </div>

      <footer class="composer">
        <textarea
          v-model="draft"
          class="composer-input"
          rows="2"
          placeholder="问原理，或者描述你想要的动画（Enter 发送，Shift+Enter 换行）"
          @keydown="onKeydown"
        />
        <div class="composer-actions">
          <span class="composer-hint">
            回答基于当前知识点的结构化报文；没有配置模型 key 时用规则兜底
          </span>
          <button class="btn tiny" :disabled="!draft.trim() || streaming" @click="animate">
            ◈ 生成动画
          </button>
          <button class="btn primary" :disabled="!draft.trim() || streaming" @click="send()">
            发送
          </button>
        </div>
      </footer>
    </section>

    <!-- 全屏预览 -->
    <div v-if="expanded" class="anim-modal" @click.self="expanded = null">
      <div class="anim-modal-box">
        <div class="anim-modal-head">
          <span>{{ expanded.title }}</span>
          <button class="btn tiny" @click="expanded = null">关闭</button>
        </div>
        <MotionPreview :input-props="expanded" />
      </div>
    </div>
  </div>
</template>
