import axios from 'axios'
import { API_BASE_URL } from './client'
import type { Config } from './types'
import type { AppError } from '../utils/errors'

export async function getConfig(): Promise<{
  success: boolean
  config?: Config
  error?: AppError | string
  error_message?: string
}> {
  const response = await axios.get(`${API_BASE_URL}/config`)
  return response.data
}

export async function updateConfig(config: Partial<Config>): Promise<{
  success: boolean
  message?: string
  error?: AppError | string
  error_message?: string
}> {
  const response = await axios.post(`${API_BASE_URL}/config`, config)
  return response.data
}

export async function testConnection(config: {
  type: string
  provider_name?: string
  api_key?: string
  base_url?: string
  endpoint_type?: string
  model: string
}): Promise<{
  success: boolean
  message?: string
  error?: AppError | string
  error_message?: string
}> {
  const response = await axios.post(`${API_BASE_URL}/config/test`, config)
  return response.data
}

