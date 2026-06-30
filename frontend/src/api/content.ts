import axios from 'axios'
import { API_BASE_URL } from './client'
import type { ContentResponse } from './types'

export async function generateContent(
  topic: string,
  outline: string
): Promise<ContentResponse> {
  const response = await axios.post<ContentResponse>(`${API_BASE_URL}/content`, {
    topic,
    outline
  })
  return response.data
}

