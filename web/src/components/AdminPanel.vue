<script setup lang="ts">
/**
 * 管理员控制台（最小版）。
 *
 * 只做三件必须在服务端做的事：看用户、改角色、看总量。
 * 更细的模型配置 / 限流 / 审计日志留到二期——先把权限边界立起来。
 */
import {onMounted, ref} from 'vue';
import {ApiError, adminApi, type AdminUser} from '../api';

const emit = defineEmits<{(e: 'close'): void}>();

const users = ref<AdminUser[]>([]);
const stats = ref<{users: number; animations: number; captures: number; backend: string} | null>(null);
const loading = ref(true);
const error = ref('');
const busyId = ref<number | null>(null);

async function load() {
  loading.value = true;
  error.value = '';
  try {
    const [u, s] = await Promise.all([adminApi.users(), adminApi.stats()]);
    users.value = u;
    stats.value = s;
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : '读取失败';
  } finally {
    loading.value = false;
  }
}

async function toggleRole(u: AdminUser) {
  busyId.value = u.id;
  try {
    await adminApi.setRole(u.id, u.role === 'admin' ? 'user' : 'admin');
    await load();
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : '修改失败';
  } finally {
    busyId.value = null;
  }
}

function fmt(v: string | null) {
  if (!v) return '—';
  return String(v).replace('T', ' ').slice(0, 19);
}

onMounted(load);
</script>

<template>
  <div class="modal-mask" @click.self="emit('close')">
    <div class="modal admin">
      <div class="admin-head">
        <h2>管理员控制台</h2>
        <button class="ghost" @click="emit('close')">关闭</button>
      </div>

      <div v-if="stats" class="stat-row">
        <div class="stat"><b>{{ stats.users }}</b><span>用户</span></div>
        <div class="stat"><b>{{ stats.animations }}</b><span>动画</span></div>
        <div class="stat"><b>{{ stats.captures }}</b><span>抓包</span></div>
        <div class="stat"><b>{{ stats.backend }}</b><span>数据库</span></div>
      </div>

      <p v-if="error" class="auth-error">{{ error }}</p>
      <p v-if="loading" class="hint">读取中…</p>

      <table v-else class="admin-table">
        <thead>
          <tr><th>ID</th><th>邮箱</th><th>角色</th><th>注册</th><th>最近登录</th><th>失败次数</th><th>操作</th></tr>
        </thead>
        <tbody>
          <tr v-for="u in users" :key="u.id">
            <td>{{ u.id }}</td>
            <td class="email">{{ u.email }}</td>
            <td><span class="role" :class="u.role">{{ u.role }}</span></td>
            <td>{{ fmt(u.created_at) }}</td>
            <td>{{ fmt(u.last_login_at) }}</td>
            <td>{{ u.failed_attempts }}</td>
            <td>
              <button class="ghost sm" :disabled="busyId === u.id" @click="toggleRole(u)">
                {{ u.role === 'admin' ? '降为用户' : '设为管理员' }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
