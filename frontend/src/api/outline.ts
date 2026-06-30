import axios from 'axios'
import { API_BASE_URL } from './client'
import type { OutlineResponse } from './types'

export async function generateOutline(
  topic: string,
  images?: File[]
): Promise<OutlineResponse & { has_images?: boolean }> {
  if (images && images.length > 0) {
    const formData = new FormData()
    formData.append('topic', topic)
    images.forEach((file) => {
      formData.append('images', file)
    })

    const response = await axios.post<OutlineResponse & { has_images?: boolean }>(
      `${API_BASE_URL}/outline`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      }
    )
    return response.data
  }

  const response = await axios.post<OutlineResponse>(`${API_BASE_URL}/outline`, {
    topic
  })
  return response.data
}

