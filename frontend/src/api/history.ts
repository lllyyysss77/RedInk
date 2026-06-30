import axios from 'axios'
import {
  API_BASE_URL,
  getApiErrorPayload
} from './client'
import type {
  HistoryDetail,
  HistoryRecord,
  Page,
  UpdateHistoryParams
} from './types'
import type { AppError } from '../utils/errors'

export async function createHistory(
  topic: string,
  outline: { raw: string; pages: Page[] },
  taskId?: string
): Promise<{ success: boolean; record_id?: string; error?: AppError | string; error_message?: string }> {
  try {
    const response = await axios.post(
      `${API_BASE_URL}/history`,
      {
        topic,
        outline,
        task_id: taskId
      },
      {
        timeout: 10000
      }
    )
    return response.data
  } catch (error: any) {
    return { success: false, ...getApiErrorPayload(error, '创建历史记录失败') }
  }
}

export async function getHistoryList(
  page: number = 1,
  pageSize: number = 20,
  status?: string
): Promise<{
  success: boolean
  records: HistoryRecord[]
  total: number
  page: number
  page_size: number
  total_pages: number
  error?: AppError | string
  error_message?: string
}> {
  try {
    const params: any = { page, page_size: pageSize }
    if (status) params.status = status

    const response = await axios.get(`${API_BASE_URL}/history`, {
      params,
      timeout: 10000
    })
    return response.data
  } catch (error: any) {
    return {
      success: false,
      records: [],
      total: 0,
      page: 1,
      page_size: pageSize,
      total_pages: 0,
      ...getApiErrorPayload(error, '获取历史记录列表失败')
    }
  }
}

export async function getHistory(recordId: string): Promise<{
  success: boolean
  record?: HistoryDetail
  error?: AppError | string
  error_message?: string
}> {
  try {
    const response = await axios.get(`${API_BASE_URL}/history/${recordId}`, {
      timeout: 10000
    })
    return response.data
  } catch (error: any) {
    return { success: false, ...getApiErrorPayload(error, '获取历史记录详情失败') }
  }
}

export async function updateHistory(
  recordId: string,
  data: UpdateHistoryParams
): Promise<{ success: boolean; error?: AppError | string; error_message?: string }> {
  try {
    const response = await axios.put(
      `${API_BASE_URL}/history/${recordId}`,
      data,
      {
        timeout: 10000
      }
    )
    return response.data
  } catch (error: any) {
    return { success: false, ...getApiErrorPayload(error, '更新历史记录失败') }
  }
}

export async function checkHistoryExists(recordId: string): Promise<boolean> {
  try {
    const response = await axios.get(
      `${API_BASE_URL}/history/${recordId}/exists`,
      {
        timeout: 5000
      }
    )
    return response.data.exists === true
  } catch (error: any) {
    if (axios.isAxiosError(error)) {
      return false
    }
    return false
  }
}

export async function deleteHistory(recordId: string): Promise<{
  success: boolean
  error?: AppError | string
  error_message?: string
}> {
  try {
    const response = await axios.delete(
      `${API_BASE_URL}/history/${recordId}`,
      {
        timeout: 10000
      }
    )
    return response.data
  } catch (error: any) {
    return { success: false, ...getApiErrorPayload(error, '删除历史记录失败') }
  }
}

export async function searchHistory(keyword: string): Promise<{
  success: boolean
  records: HistoryRecord[]
  error?: AppError | string
  error_message?: string
}> {
  try {
    const response = await axios.get(`${API_BASE_URL}/history/search`, {
      params: { keyword },
      timeout: 10000
    })
    return response.data
  } catch (error: any) {
    return { success: false, records: [], ...getApiErrorPayload(error, '搜索历史记录失败') }
  }
}

export async function getHistoryStats(): Promise<{
  success: boolean
  total: number
  by_status: Record<string, number>
  error?: AppError | string
  error_message?: string
}> {
  try {
    const response = await axios.get(`${API_BASE_URL}/history/stats`, {
      timeout: 10000
    })
    return response.data
  } catch (error: any) {
    return { success: false, total: 0, by_status: {}, ...getApiErrorPayload(error, '获取统计信息失败') }
  }
}

export async function scanAllTasks(): Promise<{
  success: boolean
  total_tasks?: number
  synced?: number
  failed?: number
  orphan_tasks?: string[]
  results?: any[]
  error?: AppError | string
  error_message?: string
}> {
  const response = await axios.post(`${API_BASE_URL}/history/scan-all`)
  return response.data
}

