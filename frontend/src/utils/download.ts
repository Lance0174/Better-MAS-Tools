import { androidCall, isAndroidLocal } from '@/services/android'

/** 手机使用系统文件选择器，桌面和 Web 保留原有下载行为。 */
export async function saveTextFile(
  filename: string,
  content: string,
  type = 'application/json'
): Promise<void> {
  if (isAndroidLocal) {
    await androidCall('file.save', { filename, content })
    return
  }
  const url = URL.createObjectURL(new Blob([content], { type }))
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
