import { DiagnosticsService } from '@/api'

/** 保留生成请求的取消能力，便于日志页卸载时停止轮询。 */
export const useDiagnosticsApi = () => ({
  list: () => DiagnosticsService.getLogs(),
  export: () => DiagnosticsService.exportLogs(),
})
