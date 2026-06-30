import axios from 'axios'
import type { AppError } from '../utils/errors'

export const API_BASE_URL = '/api'

export function getApiErrorPayload(error: unknown, fallback: string): {
  error: AppError | string
  error_message: string
} {
  if (axios.isAxiosError(error)) {
    if (error.code === 'ECONNABORTED') {
      return {
        error: '请求超时，请检查网络连接',
        error_message: '请求超时，请检查网络连接'
      }
    }
    if (!error.response) {
      return {
        error: '网络连接失败，请检查网络设置',
        error_message: '网络连接失败，请检查网络设置'
      }
    }
    const data = error.response.data || {}
    const message = data.error_message || fallback
    return {
      error: data.error || message,
      error_message: message
    }
  }

  return {
    error: fallback,
    error_message: fallback
  }
}

export async function readErrorResponse(response: Response, fallback: string) {
  try {
    return await response.json()
  } catch {
    return new Error(fallback)
  }
}

export async function readSseResponse(
  response: Response,
  handlers: Record<string, (data: any) => void>
) {
  const reader = response.body?.getReader()
  if (!reader) {
    throw new Error('无法读取响应流')
  }

  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()

      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.trim()) continue

        const [eventLine, dataLine] = line.split('\n')
        if (!eventLine || !dataLine) continue

        const eventType = eventLine.replace('event: ', '').trim()
        const eventData = dataLine.replace('data: ', '').trim()

        try {
          const data = JSON.parse(eventData)
          handlers[eventType]?.(data)
        } catch (e) {
          console.error('解析 SSE 数据失败:', e)
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}

