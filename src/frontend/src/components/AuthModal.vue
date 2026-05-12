<script setup lang="ts">
import { ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'

const router = useRouter()
const authStore = useAuthStore()
const emit = defineEmits(['close', 'authenticated'])

const mode = ref<'login' | 'register'>('login')
const loading = ref(false)
const error = ref('')

// 登录表单
const loginForm = ref({
  email: '',
  password: ''
})

// 注册表单
const registerForm = ref({
  email: '',
  username: '',
  password: '',
  confirmPassword: ''
})

async function handleLogin() {
  if (!loginForm.value.email || !loginForm.value.password) {
    error.value = '请填写邮箱和密码'
    return
  }
  
  loading.value = true
  error.value = ''
  
  try {
    const result = await authStore.login(loginForm.value.email, loginForm.value.password)
    emit('authenticated', result.user)
    emit('close')
    router.push('/')
  } catch (e: any) {
    error.value = e.message || '登录失败'
  } finally {
    loading.value = false
  }
}

async function handleRegister() {
  if (!registerForm.value.email || !registerForm.value.username || !registerForm.value.password) {
    error.value = '请填写所有必填项'
    return
  }
  
  if (registerForm.value.password !== registerForm.value.confirmPassword) {
    error.value = '两次输入的密码不一致'
    return
  }
  
  if (registerForm.value.password.length < 8) {
    error.value = '密码长度至少8位'
    return
  }
  
  loading.value = true
  error.value = ''
  
  try {
    const result = await authStore.register(
      registerForm.value.email,
      registerForm.value.username,
      registerForm.value.password,
      registerForm.value.confirmPassword
    )
    emit('authenticated', result.user)
    emit('close')
    router.push('/')
  } catch (e: any) {
    error.value = e.message || '注册失败'
  } finally {
    loading.value = false
  }
}

function switchMode() {
  mode.value = mode.value === 'login' ? 'register' : 'login'
  error.value = ''
}
</script>

<template>
  <div class="auth-modal">
    <div class="auth-card">
      <button class="close-btn" @click="$emit('close')">×</button>
      
      <div class="auth-header">
        <h2>{{ mode === 'login' ? '登录' : '注册' }}</h2>
        <p v-if="mode === 'login'">登录您的账户以使用完整功能</p>
        <p v-else>创建新账户开始设计质粒</p>
      </div>
      
      <div v-if="error" class="error-message">{{ error }}</div>
      
      <!-- 登录表单 -->
      <form v-if="mode === 'login'" @submit.prevent="handleLogin" class="auth-form">
        <div class="form-group">
          <label>邮箱</label>
          <input 
            v-model="loginForm.email" 
            type="email" 
            placeholder="your@email.com"
            class="form-input"
          />
        </div>
        
        <div class="form-group">
          <label>密码</label>
          <input 
            v-model="loginForm.password" 
            type="password" 
            placeholder="输入密码"
            class="form-input"
          />
        </div>
        
        <button type="submit" class="btn btn-primary submit-btn" :disabled="loading">
          {{ loading ? '登录中...' : '登录' }}
        </button>
        
        <p class="switch-text">
          还没有账户？
          <a @click="switchMode">立即注册</a>
        </p>
      </form>
      
      <!-- 注册表单 -->
      <form v-else @submit.prevent="handleRegister" class="auth-form">
        <div class="form-group">
          <label>邮箱 *</label>
          <input 
            v-model="registerForm.email" 
            type="email" 
            placeholder="your@email.com"
            class="form-input"
          />
        </div>
        
        <div class="form-group">
          <label>用户名 *</label>
          <input 
            v-model="registerForm.username" 
            type="text" 
            placeholder="用户名"
            class="form-input"
          />
        </div>
        
        <div class="form-group">
          <label>密码 *</label>
          <input 
            v-model="registerForm.password" 
            type="password" 
            placeholder="至少8位"
            class="form-input"
          />
        </div>
        
        <div class="form-group">
          <label>确认密码 *</label>
          <input 
            v-model="registerForm.confirmPassword" 
            type="password" 
            placeholder="再次输入密码"
            class="form-input"
          />
        </div>
        
        <button type="submit" class="btn btn-primary submit-btn" :disabled="loading">
          {{ loading ? '注册中...' : '注册' }}
        </button>
        
        <p class="switch-text">
          已有账户？
          <a @click="switchMode">立即登录</a>
        </p>
      </form>
    </div>
  </div>
</template>

<style scoped>
.auth-modal {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.auth-card {
  background: white;
  padding: 2rem;
  border-radius: 12px;
  width: 100%;
  max-width: 400px;
  position: relative;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
}

.close-btn {
  position: absolute;
  top: 1rem;
  right: 1rem;
  background: none;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
  color: #999;
}

.close-btn:hover {
  color: #333;
}

.auth-header {
  text-align: center;
  margin-bottom: 1.5rem;
}

.auth-header h2 {
  font-size: 1.5rem;
  margin-bottom: 0.5rem;
}

.auth-header p {
  color: #666;
  font-size: 0.875rem;
}

.auth-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.form-group label {
  font-size: 0.875rem;
  font-weight: 500;
}

.form-input {
  padding: 0.75rem;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 1rem;
}

.form-input:focus {
  outline: none;
  border-color: var(--primary-color);
  box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
}

.error-message {
  padding: 0.75rem;
  background: rgba(239, 68, 68, 0.1);
  border-radius: 6px;
  color: #dc2626;
  font-size: 0.875rem;
  text-align: center;
}

.submit-btn {
  margin-top: 0.5rem;
}

.switch-text {
  text-align: center;
  font-size: 0.875rem;
  color: #666;
}

.switch-text a {
  color: var(--primary-color);
  cursor: pointer;
  text-decoration: underline;
}

.switch-text a:hover {
  color: #4338ca;
}
</style>
