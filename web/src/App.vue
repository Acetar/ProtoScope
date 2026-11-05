<script setup lang="ts">
/**
 * 工作台主界面。
 *
 * 布局：左侧知识库 / 中间预览 / 右侧说明与设置，
 * 一条主线是「目录或一句话 → 生成 props → 浏览器预览 → 导出 MP4」。
 */
import {computed, onMounted, ref} from 'vue';
import AdminPanel from './components/AdminPanel.vue';
import AuthModal from './AuthModal.vue';
import CaptureView from './CaptureView.vue';
import Landing from './Landing.vue';
import TutorView from './TutorView.vue';
import MotionPreview from './components/MotionPreview.vue';
import {
  ApiError,
  authApi,
  getToken,
  motionApi,
  setToken,
  type AuthUser,
  type GenerateResult,
  type KnowledgePoint,
} from './api';

// ---------- 顶层视图切换 ----------

/** motion = 知识点动画；capture = 抓包解析；tutor = AI 教师答疑 */
const view = ref<'motion' | 'capture' | 'tutor'>('motion');

/** 抓包页把会话翻译成 props 后，切回动画页直接播放 */
function onCaptureMotion(res: GenerateResult) {
  result.value = res;
  view.value = 'motion';
  notify('已把这段抓包变成动画，可以播放或导出');
}

/** 落地页把这两种意图都收敛到同一个弹窗，只是初始 tab 不同 */
const authOpen = ref(false);
const authMode = ref<'login' | 'register'>('login');
const adminOpen = ref(false);

function openAuth(mode: 'login' | 'register' = 'login') {
  authMode.value = mode;
  authOpen.value = true;
}

function onAuthSuccess(u: AuthUser) {
  user.value = u;
  authOpen.value = false;
  notify(`欢迎，${u.email}`);
  loadAnimations();
  if (!result.value) generate(true);
}

// ---------- 基础状态 ----------

const catalog = ref<KnowledgePoint[]>([]);
const user = ref<AuthUser | null>(null);
const result = ref<GenerateResult | null>(null);
const loading = ref(false);
const booting = ref(true);
const toast = ref('');
const toastKind = ref<'ok' | 'err'>('ok');

/** 未登录只能看落地页：工作台整个不渲染，不是用 CSS 盖住 */
const loggedIn = computed(() => !!user.value);
const isAdmin = computed(() => user.value?.role === 'admin');

let toastTimer: number | undefined;
function notify(text: string, kind: 'ok' | 'err' = 'ok') {
  toast.value = text;
  toastKind.value = kind;
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => (toast.value = ''), 4200);
}

// ---------- 生成表单 ----------

const topic = ref('tcp.handshake');
const prompt = ref('');
const durationSec = ref(16);

const currentTitle = computed(() => result.value?.props?.title || '还没有生成动画');
const sourceLabel = computed(() => {
  const src = result.value?.meta.source;
  if (src === 'llm') return '大模型编排';
  if (src === 'capture') return '真实抓包';
  return '规则库';
});

async function generate(useTopic = false) {
  if (loading.value) return;
  if (!useTopic && !prompt.value.trim()) {
    notify('先在输入框里描述一下想看什么，或直接点左边的知识点', 'err');
    return;
  }
  loading.value = true;
  try {
    const payload = useTopic || !prompt.value.trim()
      ? {topic: topic.value, durationSec: durationSec.value}
      : {prompt: prompt.value.trim(), durationSec: durationSec.value};
    const res = await motionApi.generate(payload);
    result.value = res;
    notify(
      `${sourceLabel.value}完成：${res.props.scenes.length} 个场景 / ${res.meta.durationSec}s / ${res.meta.elapsedMs}ms`,
    );
  } catch (err) {
    if (err instanceof ApiError) {
      notify(err.message, 'err');
      if (err.suggestions?.length) {
        prompt.value = '';
        topic.value = err.suggestions[0];
      }
    } else {
      notify('生成失败，检查后端是否在 8000 端口运行', 'err');
    }
  } finally {
    loading.value = false;
  }
}

function pickKnowledgePoint(kp: KnowledgePoint) {
  topic.value = kp.id;
  prompt.value = '';
  generate(true);
}

// ---------- 认证 ----------

function logout() {
  setToken(null);
  user.value = null;
  animations.value = [];
  result.value = null;
  notify('已退出登录');
}

// ---------- 设置（BYOK） ----------

const settingsOpen = ref(false);
const settings = ref({baseUrl: '', model: '', apiKey: '', maskedKey: '', hasKey: false});
const settingsBusy = ref(false);

async function openSettings() {
  if (!user.value) {
    authOpen.value = true;
    notify('先登录，key 是按用户保存的', 'err');
    return;
  }
  settingsOpen.value = true;
  try {
    const s = await motionApi.settings();
    settings.value = {
      baseUrl: s.baseUrl || s.defaults.baseUrl,
      model: s.model || s.defaults.model,
      apiKey: '',
      maskedKey: s.maskedKey,
      hasKey: s.hasKey,
    };
  } catch (err) {
    notify(err instanceof ApiError ? err.message : '读取设置失败', 'err');
  }
}

async function saveSettings() {
  settingsBusy.value = true;
  try {
    const s = await motionApi.saveSettings({
      baseUrl: settings.value.baseUrl,
      model: settings.value.model,
      apiKey: settings.value.apiKey,
    });
    settings.value.maskedKey = s.maskedKey;
    settings.value.hasKey = s.hasKey;
    settings.value.apiKey = '';
    settingsOpen.value = false;
    notify('已保存，之后的生成会走你的 DeepSeek 账号');
  } catch (err) {
    notify(err instanceof ApiError ? err.message : '保存失败', 'err');
  } finally {
    settingsBusy.value = false;
  }
}

// ---------- 我的动画 ----------

const animationsOpen = ref(false);
const animations = ref<{id: string; title: string; knowledge_point: string; duration_sec: number; created_at: string}[]>([]);

async function loadAnimations() {
  if (!user.value) return;
  try {
    animations.value = await motionApi.animations();
  } catch {
    animations.value = [];
  }
}

async function openAnimations() {
  if (!user.value) {
    authOpen.value = true;
    notify('登录后才能看自己的作品', 'err');
    return;
  }
  animationsOpen.value = true;
  await loadAnimations();
}

async function loadAnimation(id: string) {
  try {
    const data = await motionApi.animation(id);
    result.value = {
      props: data.props,
      meta: {
        source: 'catalog',
        knowledgePoint: data.knowledge_point,
        durationSec: data.duration_sec,
        totalFrames: data.props.totalFrames,
        elapsedMs: 0,
        notes: ['从我的动画里载入'],
      },
    };
    animationsOpen.value = false;
    notify(`已载入：${data.props.title}`);
  } catch (err) {
    notify(err instanceof ApiError ? err.message : '载入失败', 'err');
  }
}

async function removeAnimation(id: string) {
  try {
    await motionApi.remove(id);
    await loadAnimations();
    notify('已删除');
  } catch (err) {
    notify(err instanceof ApiError ? err.message : '删除失败', 'err');
  }
}

// ---------- 导出 MP4 ----------

const renderJob = ref<{id: string; status: string; url?: string; error?: string} | null>(null);
const rendering = ref(false);

async function exportMp4() {
  if (!result.value || rendering.value) return;
  rendering.value = true;
  renderJob.value = null;
  try {
    const job = await motionApi.render(result.value.props);
    renderJob.value = job;
    pollRender(job.id);
  } catch (err) {
    rendering.value = false;
    notify(err instanceof ApiError ? err.message : '提交渲染失败', 'err');
  }
}

function pollRender(id: string) {
  const timer = window.setInterval(async () => {
    try {
      const job = await motionApi.renderStatus(id);
      renderJob.value = job;
      if (job.status === 'done' || job.status === 'failed') {
        window.clearInterval(timer);
        rendering.value = false;
        if (job.status === 'done') notify('MP4 已生成');
        else notify(job.error || '渲染失败', 'err');
      }
    } catch {
      window.clearInterval(timer);
      rendering.value = false;
      notify('查询渲染状态失败', 'err');
    }
  }, 1500);
}

// ---------- 启动 ----------

onMounted(async () => {
  // 先确认登录态：没有 token 就停在落地页，连目录都不拉——未登录不该拿到任何功能数据
  if (!getToken()) {
    booting.value = false;
    return;
  }
  try {
    user.value = await authApi.me();
  } catch {
    setToken(null);
    booting.value = false;
    return;
  }

  try {
    catalog.value = await motionApi.catalog();
  } catch {
    notify('后端没起来？先在 server/ 里跑 uvicorn', 'err');
  }
  await loadAnimations();
  booting.value = false;
  await generate(true);
});
</script>

<template>
  <!-- 未登录：只有落地页，唯一的出口是登录/注册 -->
  <Landing v-if="!loggedIn" @login="openAuth('login')" />

  <div v-else class="app">
    <header class="topbar">
      <div class="brand">
        <span class="logo">◎</span>
        <div>
          <h1>协议动画工作台</h1>
          <p>选一个知识点，或直接用一句话描述你想看的网络交互</p>
        </div>
      </div>
      <nav class="viewtabs">
        <button :class="{on: view === 'motion'}" @click="view = 'motion'">知识点动画</button>
        <button :class="{on: view === 'capture'}" @click="view = 'capture'">抓包解析</button>
        <button :class="{on: view === 'tutor'}" @click="view = 'tutor'">AI 教师</button>
      </nav>
      <div class="topbar-actions">
        <span v-if="user" class="who">{{ user.email }}</span>
        <button v-if="isAdmin" class="ghost" @click="adminOpen = true">管理</button>
        <button class="ghost" @click="openSettings">模型设置</button>
        <button class="ghost" @click="openAnimations">我的动画</button>
        <button class="ghost" @click="logout">退出</button>
      </div>
    </header>

    <main v-if="view === 'motion'" class="layout">
      <!-- 左：知识库 -->
      <aside class="panel catalog">
        <h2>知识点目录</h2>
        <p class="hint">这六个是"人写好剧本"的，离线也能跑</p>
        <ul>
          <li
            v-for="kp in catalog"
            :key="kp.id"
            :class="{active: topic === kp.id}"
            @click="pickKnowledgePoint(kp)"
          >
            <strong>{{ kp.title }}</strong>
            <span>{{ kp.summary }}</span>
            <em>{{ kp.actors.join(' ↔ ') }}</em>
          </li>
        </ul>
      </aside>

      <!-- 中：生成 + 预览 -->
      <section class="panel stage">
        <div class="composer">
          <textarea
            v-model="prompt"
            rows="2"
            placeholder="例如：讲一下 TLS 握手怎么防中间人 / 为什么 TCP 挥手要四次 / ARP 广播是怎么找到网关的"
            @keydown.ctrl.enter="generate(false)"
          />
          <div class="composer-row">
            <label class="slider">
              时长 {{ durationSec }}s
              <input v-model.number="durationSec" type="range" min="8" max="40" step="1" />
            </label>
            <button class="primary" :disabled="loading" @click="generate(false)">
              {{ loading ? '生成中…' : '生成动画' }}
            </button>
          </div>
        </div>

        <div v-if="booting" class="skeleton">正在载入…</div>
        <template v-else-if="result">
          <div class="stage-head">
            <div>
              <h2>{{ currentTitle }}</h2>
              <p>{{ result.props.subtitle }}</p>
            </div>
            <div class="badge" :class="result.meta.source">{{ sourceLabel }}</div>
          </div>

          <MotionPreview :input-props="result.props" />

          <div class="meta">
            <span>{{ result.props.scenes.length }} 个场景</span>
            <span>{{ result.meta.durationSec }}s</span>
            <span>{{ result.meta.totalFrames }} 帧</span>
            <span v-if="result.meta.elapsedMs > 0">{{ result.meta.elapsedMs }}ms</span>
            <span v-if="result.props.actors.length">2 个通信主体</span>
          </div>

          <div class="stage-actions">
            <button
              v-if="result.meta.source !== 'capture'"
              class="ghost"
              @click="generate(true)"
            >
              重新生成
            </button>
            <button class="primary" :disabled="rendering" @click="exportMp4">
              {{ rendering ? '渲染中…' : '导出 MP4' }}
            </button>
            <a
              v-if="renderJob?.status === 'done' && renderJob.url"
              class="download"
              :href="renderJob.url"
              target="_blank"
              rel="noreferrer"
            >下载成片</a>
            <span v-if="renderJob?.status === 'running' || renderJob?.status === 'queued'" class="hint">
              正在逐帧渲染，1080p 大约 30~60s
            </span>
          </div>

          <details v-if="result.meta.notes.length" class="notes">
            <summary>生成说明</summary>
            <ul>
              <li v-for="(n, i) in result.meta.notes" :key="i">{{ n }}</li>
            </ul>
          </details>
        </template>
        <div v-else class="skeleton">左侧选一个知识点开始</div>
      </section>

      <!-- 右：这一屏在讲什么 -->
      <aside class="panel explain">
        <h2>画面怎么读</h2>
        <ol class="legend">
          <li><b>左右两列</b>是两个通信主体，箭头方向就是报文方向。</li>
          <li><b>报文胶囊</b>上的 seq / ack / flags 是真实字段，和抓包一致。</li>
          <li><b>顶部状态</b>随场景推进（LISTEN → SYN_RCVD → ESTABLISHED）。</li>
          <li><b>底部字幕</b>是"为什么"，不是"发生了什么"。</li>
        </ol>
        <h2>两种来源</h2>
        <p class="hint">
          目录里的知识点走规则库，秒出、可离线；
          自由描述走 DeepSeek，把需求编排成同一份 props。
        </p>
        <p class="hint">
          预览和出片跑的是同一份 Composition —— 浏览器里看到什么，MP4 就是什么。
        </p>
        <h2>限制</h2>
        <p class="hint">
          模板是"两方消息时序图"，只有两列。DNS 那种多方接力会用旁白补足，
          不会凭空多出第三个角色。
        </p>
      </aside>
    </main>

    <main v-else-if="view === 'capture'" class="layout-capture">
      <CaptureView @use-motion="onCaptureMotion" />
    </main>

    <!-- AI 教师独立成页：左边保留预览当"板书"，右边才是对话 -->
    <!-- AI 教师：会话式界面（左侧会话列表 + 中间消息流，动画长在消息流里） -->
    <TutorView v-else :points="catalog" @toast="notify" />

    <!-- 管理员控制台 -->
    <AdminPanel v-if="adminOpen" @close="adminOpen = false" />

    <!-- 模型设置 -->
    <div v-if="settingsOpen" class="modal-mask" @click.self="settingsOpen = false">
      <div class="modal">
        <h2>DeepSeek 配置</h2>
        <p class="hint">
          走 OpenAI 兼容协议，key 只保存在本机 SQLite 里，接口只回掩码。
          不填也能用，只是只能选目录里的六个知识点。
        </p>
        <label>Base URL<input v-model="settings.baseUrl" placeholder="https://api.deepseek.com" /></label>
        <label>模型<input v-model="settings.model" placeholder="deepseek-chat" /></label>
        <label>
          API Key
          <input
            v-model="settings.apiKey"
            type="password"
            :placeholder="settings.hasKey ? `已保存：${settings.maskedKey}（留空则不修改）` : 'sk-...'"
          />
        </label>
        <div class="modal-actions">
          <button class="ghost" @click="settingsOpen = false">取消</button>
          <button class="primary" :disabled="settingsBusy" @click="saveSettings">
            {{ settingsBusy ? '保存中…' : '保存' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 我的动画 -->
    <div v-if="animationsOpen" class="modal-mask" @click.self="animationsOpen = false">
      <div class="modal wide">
        <h2>我的动画</h2>
        <p v-if="!animations.length" class="hint">还没有作品，生成一次会自动存一份。</p>
        <ul class="anim-list">
          <li v-for="a in animations" :key="a.id">
            <div>
              <strong>{{ a.title }}</strong>
              <span>{{ a.knowledge_point }} · {{ a.duration_sec }}s · {{ a.created_at.slice(0, 19).replace('T', ' ') }}</span>
            </div>
            <div class="anim-actions">
              <button class="ghost" @click="loadAnimation(a.id)">载入</button>
              <button class="danger" @click="removeAnimation(a.id)">删除</button>
            </div>
          </li>
        </ul>
        <div class="modal-actions">
          <button class="ghost" @click="animationsOpen = false">关闭</button>
        </div>
      </div>
    </div>

    <div v-if="toast" class="toast" :class="toastKind">{{ toast }}</div>
  </div>

  <!-- 登录弹窗放在最外层：落地页和登录墙都要能唤起它 -->
  <AuthModal :open="authOpen" :mode="authMode" @close="authOpen = false" @success="onAuthSuccess" />
</template>
