<script setup lang="ts">
/**
 * 未登录首页（落地页）。
 *
 * 只负责"讲清这是什么"，不放任何功能入口：
 * 唯一可点的动作是登录 / 注册，点功能卡片也只会唤起登录框。
 * 视觉参照：浅灰绿底 + 绿色主色 + 白卡片 + 超大标题。
 */
import {onMounted, ref} from 'vue';

const emit = defineEmits<{(e: 'login'): void}>();

/** 首屏那排"卖点胶囊"，和 hero 下方功能卡一一对应 */
const pills = [
  '规则库秒出动画',
  '真实抓包可解析',
  'AI 教师可追问',
  '断网也能演示',
];

const features = [
  {
    icon: '▶',
    title: '协议动画演示',
    text: 'TCP 握手、四次挥手、TLS、HTTP、ARP、DNS 六个知识点，每个都是可暂停、可拖动的真实动效。报文上的 seq / ack / flags 来自真实字段，不是示意图。',
  },
  {
    icon: '◫',
    title: '知识汇总',
    text: '每个知识点配一张速查表：状态机怎么走、哪个字段决定什么、新手最容易在哪一步理解错。',
  },
  {
    icon: '✎',
    title: 'AI 教师答疑',
    text: '把它当成计算机网络老师：先讲原理，再回答你的"为什么"。回答基于当前知识点的报文上下文，不凭空编数字。',
  },
  {
    icon: '◈',
    title: '按需生成科普动画',
    text: '一句话描述你想看的交互（"讲一下 TLS 怎么防中间人"），平台把它编排成一段 15~30 秒的科普动效并直接播放。',
  },
];

/** 滚动到功能区；纯前端交互，不需要路由库 */
const featuresEl = ref<HTMLElement | null>(null);
function scrollToFeatures() {
  featuresEl.value?.scrollIntoView({behavior: 'smooth', block: 'start'});
}

/** 页面加载后让首屏元素依次淡入，不引动画库 */
const ready = ref(false);
onMounted(() => {
  requestAnimationFrame(() => (ready.value = true));
});
</script>

<template>
  <div class="landing" :class="{ready}">
    <!-- 顶部导航 -->
    <header class="nav">
      <div class="nav-brand">
        <span class="nav-logo">◎</span>
        <span class="nav-name">协议动画学堂</span>
      </div>
      <nav class="nav-links">
        <a @click="scrollToFeatures">功能</a>
        <a @click="scrollToFeatures">原理</a>
        <a @click="emit('login')">文档</a>
      </nav>
      <div class="nav-actions">
        <span class="nav-version"><i></i>v0.1 内测中</span>
        <button class="btn-line" @click="emit('login')">登录</button>
        <button class="btn-solid" @click="emit('login')">免费注册</button>
      </div>
    </header>

    <!-- 首屏 -->
    <section class="hero">
      <div class="hero-copy">
        <div class="hero-tag">
          <span class="dot"></span>
          计算机网络 · 实验项目
        </div>
        <h1>
          把每一次握手<br />
          都<em>看得见</em>
        </h1>
        <p class="hero-sub">
          网络协议不是背出来的。平台把一段真实的网络交互拆成可播放的动效，<br />
          再让 AI 教师站到旁边，回答你每一个"为什么"。
        </p>
        <div class="hero-cta">
          <button class="btn-solid lg" @click="emit('login')">
            <span class="ico">→</span> 开始学习
          </button>
          <button class="btn-line lg" @click="scrollToFeatures">先看看能做什么</button>
        </div>
        <ul class="pill-row">
          <li v-for="p in pills" :key="p"><i></i>{{ p }}</li>
        </ul>
      </div>

      <!-- 右：示意窗口（纯 CSS 画的假界面，不放真实组件，避免未登录就能用功能） -->
      <div class="hero-art">
        <div class="mock">
          <div class="mock-bar">
            <span class="tl r"></span><span class="tl y"></span><span class="tl g"></span>
            <span class="mock-title">TCP 三次握手 · 播放中</span>
          </div>
          <div class="mock-body">
            <div class="node left">
              <div class="node-icon">💻</div>
              <div class="node-name">客户端</div>
              <div class="node-state">SYN_SENT</div>
            </div>
            <div class="node right">
              <div class="node-icon">🖧</div>
              <div class="node-name">服务端</div>
              <div class="node-state">ESTABLISHED</div>
            </div>
            <div class="wire w1"><span>SYN seq=100</span></div>
            <div class="wire w2 rev"><span>SYN+ACK seq=300 ack=101</span></div>
            <div class="wire w3"><span>ACK seq=101 ack=301</span></div>
          </div>
          <div class="mock-caption">第三次 ACK 落地，连接建立 —— 双方都确认了对方的接收能力</div>
        </div>
      </div>
    </section>

    <!-- 功能 -->
    <section ref="featuresEl" class="features">
      <div class="sec-head">
        <h2>登录后你能做什么</h2>
        <p>四个模块共用同一份报文数据：动画里看到的字段，就是答疑时引用的字段。</p>
      </div>
      <div class="cards">
        <article v-for="f in features" :key="f.title" class="card">
          <div class="card-icon">{{ f.icon }}</div>
          <h3>{{ f.title }}</h3>
          <p>{{ f.text }}</p>
        </article>
      </div>
    </section>

    <!-- 原理 -->
    <section class="how">
      <div class="how-inner">
        <h2>为什么不直接把抓包丢给模型</h2>
        <p class="how-sub">大模型擅长解释，不擅长读字节。所以中间隔了一层"结构化语义"。</p>
        <div class="steps">
          <div class="step">
            <b>01</b>
            <h4>规则层先算</h4>
            <p>抓包 → 会话 → 报文 → 字段。这一步不经过模型，结果是确定的。</p>
          </div>
          <div class="step">
            <b>02</b>
            <h4>语义压缩</h4>
            <p>把会话压成几百 token 的摘要，只留讲解真正需要的字段。</p>
          </div>
          <div class="step">
            <b>03</b>
            <h4>模型推理</h4>
            <p>模型只在这份结构化事实上解释，引用编号能对上报文才采信。</p>
          </div>
          <div class="step">
            <b>04</b>
            <h4>前端渲染</h4>
            <p>同一份剧本既能在浏览器里播放，也能导出成 MP4。</p>
          </div>
        </div>
      </div>
    </section>

    <footer class="foot">
      <span>协议动画学堂 · 计算机实验项目</span>
      <span>Vue3 + FastAPI + Remotion</span>
    </footer>
  </div>
</template>
