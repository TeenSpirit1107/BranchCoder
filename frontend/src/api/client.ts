import axios, { AxiosError } from 'axios';

// API配置
export const API_CONFIG = {
  host: import.meta.env.VITE_API_URL,
  version: 'v1',
  timeout: 30000, // 请求超时时间（毫秒）
};

// 完整API基础URL
export const BASE_URL = API_CONFIG.host 
  ? `${API_CONFIG.host}/api/${API_CONFIG.version}` 
  : `/api/${API_CONFIG.version}`;

// 统一响应格式
export interface ApiResponse<T> {
  code: number;
  msg: string;
  data: T;
}

// 错误格式
export interface ApiError {
  code: number;
  message: string;
  details?: unknown;
}

// 创建axios实例
export const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: API_CONFIG.timeout,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器，可添加认证令牌等
apiClient.interceptors.request.use(
  (config) => {
    // 可在此处添加认证令牌
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// 响应拦截器，统一错误处理
apiClient.interceptors.response.use(
  (response) => {
    // 检查后端响应格式
    if (response.data && typeof response.data.code === 'number') {
      // 如果是业务逻辑错误（code不为0），转为错误处理
      if (response.data.code !== 0) {
        const apiError: ApiError = {
          code: response.data.code,
          message: response.data.msg || '未知错误',
          details: response.data
        };
        return Promise.reject(apiError);
      }
      
      // 如果是成功响应（code为0），自动提取data字段
      if (response.data.code === 0 && response.data.data !== undefined) {
        return {
          ...response,
          data: response.data.data
        };
      }
    }
    return response;
  },
  (error: AxiosError) => {
    const apiError: ApiError = {
      code: 500,
      message: '请求失败',
    };

    if (error.response) {
      const status = error.response.status;
      apiError.code = status;
      
      // 尝试从响应内容中提取详细错误信息
      if (error.response.data && typeof error.response.data === 'object') {
        const data = error.response.data as any;
        if (data.code && data.msg) {
          apiError.code = data.code;
          apiError.message = data.msg;
        } else {
          apiError.message = data.message || error.response.statusText || '请求失败';
        }
        apiError.details = data;
      } else {
        apiError.message = error.response.statusText || '请求失败';
      }
    } else if (error.request) {
      apiError.code = 503;
      apiError.message = '网络错误，请检查您的连接';
    }

    console.error('API错误:', apiError);
    return Promise.reject(apiError);
  }
); 