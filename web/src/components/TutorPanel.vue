<script setup lang="ts">
/**
 * AI 教师面板（B1）。
 *
 * 和"生成动画"的区别：动画那条线让模型产出 JSON，
 * 这条线让模型产出自然语言，但上下文仍然来自规则层的结构化数据。
 */
import {nextTick, ref, watch} from 'vue';
import {ApiError, askTutor, type ChatTurn} from '../api';

const props = defineProps<{
  /** 当前知识点标题，用于空状态提示 */
  topicTitle: string;
  topicId: string;
  /** 当前剧本；有它模型才能引用真实的 seq/ack */
  props?: unknown;
}>();

const open = ref(false);
const history = ref<ChatTurn[]>([]);
const input = ref('');
const streaming = ref(false);
const error = ref('');
const listEl = ref<HTMLElement | null>(null);

/** 常见追问：新手最容易卡住的地方，直接给几个胶囊少打字 */
const presets = [
  '为什么是三次，两次不行吗',
  'seq 和 ack 到底谁加 1',
  '这一步丢包了会怎样',
  '现实中怎么看到这个字段',
];

async function scrollToBottom() {
  await nextTick();
  const el = listEl.value;
  if (el) el.scrollTop = el.scrollHeight;
}

async function ask(question: string) {
  const q = question.trim();
  if (!q || streaming.value) return;
  error.value = '';
  input.value = '';
  history.value.push({role: 'user', content: q});
  // 先放一条空的助手消息，token 到了直接往上追加，避免反复重排整个列表
  history.value.push({role: 'assistant', content: ''});
  streaming.value = true;
  const idx = history.value.length - 1;
  await scrollToBottom();

  try {
    await askTutor(
      {
        question: q,
        topic: props.topicId,
        props: props.props,
        // 去掉刚压进去的空助手消息，历史只带已完成的轮次
        history: history.value.slice(0, -2).slice(-6),
      },
      (piece) => {
        history.value[idx].content += piece;
        scrollToBottom();
      },
    );
  } catch (err) {
    const msg = err instanceof ApiError ? err.message : '回答中断了，检查后端是否在运行';
    error.value = msg;
    if (!history.value[idx].content) history.value.splice(idx, 1);
  } finally {
    streaming.value = false;
    await scrollToBottom();
  }
}

/** 切换知识点时清空对话：上下文变了，旧回答会误导 */
watch(
  () => props.topicId,
  () => {
    if (history.value.length) {
      history.value = [];
      error.value = '已切换到新的知识点，对话已清空';
    }
  },
);
</script>

<template>
  <aside class="panel tutor">
    <div class="tutor-head">
      <h2>AI 教师</h2>
      <span class="tutor-tag">{{ topicTitle || '未选择' }}</span>
    </div>

    <div ref="listEl" class="tutor-list">
      <div v-if="!history.length" class="tutor-empty">
        <p>我按「{{ topicTitle }}」这个知识点的报文来回答，不编数字。</p>
        <div class="preset-row">
          <button v-for="p in presets" :key="p" class="preset" @click="ask(p)">{{ p }}</button>
        </div>
      </div>

      <div v-for="(m, i) in history" :key="i" class="msg" :class="m.role">
        <div class="avatar">{{ m.role === 'user' ? '我' : '教' }}</div>
        <div class="bubble">
          <template v-if="m.content">{{ m.content }}</template>
          <span v-else class="typing"><i></i><i></i><i></i></span>
        </div>
      </div>

      <p v-if="error" class="tutor-error">{{ error }}</p>
    </div>

    <div class="tutor-input">
      <textarea
        v-model="input"
        rows="2"
        placeholder="问点什么…（Ctrl+Enter 发送）"
        :disabled="streaming"
        @keydown.ctrl.enter="ask(input)"
      />
      <button class="primary" :disabled="streaming || !input.trim()" @click="ask(input)">
        {{ streaming ? '…' : '发送' }}
      </button>
    </div>
  </aside>
</template>
