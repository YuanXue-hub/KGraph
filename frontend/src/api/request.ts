import axios, { type AxiosInstance, type AxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'

export interface ApiResponse<T = any> {
  code: number
  data: T
  message: string
}

const service: AxiosInstance = axios.create({
  baseURL: 'http://localhost:8888/api',
  timeout: 60000,
  withCredentials: true
})

// 请求拦截器
service.interceptors.request.use(
  (config) => {
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
service.interceptors.response.use(
  (response) => {
    const res = response.data as ApiResponse
    // 如果是文件流等非标准返回，直接返回
    if (response.config.responseType === 'blob') {
      return response
    }
    if (res.code !== 0) {
      ElMessage.error(res.message || '请求失败')
      // 未登录
      if (res.code === 40100) {
        // 避免在登录页跳转循环
        if (window.location.pathname !== '/login') {
          window.location.href = '/login'
        }
      }
      return Promise.reject(new Error(res.message || 'Error'))
    }
    // 直接返回业务数据结构 { code, data, message }，绕过 axios 的 AxiosResponse 类型约束
    return res as unknown as typeof response
  },
  (error) => {
    const msg = error?.response?.data?.message || error.message || '网络异常'
    ElMessage.error(msg)
    return Promise.reject(error)
  }
)

export function request<T = any>(config: AxiosRequestConfig): Promise<ApiResponse<T>> {
  return service(config) as unknown as Promise<ApiResponse<T>>
}

export default service
