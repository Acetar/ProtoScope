<script setup lang="ts">
/**
 * 登录 / 注册弹窗。
 *
 * 从 App.vue 里抽出来，是因为落地页和登录墙都要唤起它，
 * 放在里面会让 App.vue 继续膨胀。
 */
import {ref, watch} from 'vue';
import {ApiError, authApi, setToken} from './api';

const props = defineProps<{
  open: boolean;
  /** 初始模式；从"免费注册"按钮进来时是 register */
  mode?: 'login' | 'register';
}>();

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'success', user: {id: number; email: string; role?: string}): void;
}>();

const tab = ref<'login' | 'register'>('login');
const form = ref({email: '', password: ''});
const busy = ref(false);
const error = ref('');

watch(
  () => props.open,
  (v) => {
    if (!v) return;
    tab.value = props.mode || 'login';
    error.value = '';
    form.value = {email: '', password: ''};
  },
  {immediate: true},
);

async function submit() {
  const {email, password} = form.value;
  if (!email.trim() || !password) {
    error.value = '邮箱和密码都要填';
    return;
  }
  if (tab.value === 'register' && password.length < 6) {
    error.value = '密码至少 6 位';
    return;
  }
  busy.value = true;
  error.value = '';
  try {
    const res = tab.value === 'login'
      ? await authApi.login(email.trim(), password)
      : await authApi.register(email.trim(), password);
    setToken(res.token);
    emit('success', res.user);
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : '网络异常，检查后端是否在 8000 端口';
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <div v-if="open" class="modal-mask" @click.self="emit('close')">
    <div class="modal auth-modal">
      <div class="auth-head">
        <span class="landing-logo">◎</span>
        <div>
          <h2>{{ tab === 'login' ? '登录' : '创建账号' }}</h2>
          <p class="hint">
            {{ tab === 'login' ? '登录后查看动画、答疑与抓包解析' : '注册即可使用全部功能，无需邀请码' }}
          </p>
        </div>
      </div>

      <label>
        邮箱
        <input
          v-model="form.email"
          type="email"
          autocomplete="username"
          placeholder="you@example.com"
          @keydown.enter="submit"
        />
      </label>
      <label>
        密码
        <input
          v-model="form.password"
          type="password"
          :autocomplete="tab === 'login' ? 'current-password' : 'new-password'"
          :placeholder="tab === 'login' ? '输入密码' : '至少 6 位'"
          @keydown.enter="submit"
        />
      </label>

      <p v-if="error" class="auth-error">{{ error }}</p>

      <div class="modal-actions">
        <button class="ghost" @click="tab = tab === 'login' ? 'register' : 'login'">
          {{ tab === 'login' ? '没有账号？去注册' : '已有账号？去登录' }}
        </button>
        <button class="primary" :disabled="busy" @click="submit">
          {{ busy ? '请稍候…' : tab === 'login' ? '登录' : '注册并登录' }}
        </button>
      </div>
    </div>
  </div>
</template>
