import axios from 'axios'
import type {
  AiConfig,
  AppSettings,
  BackgroundJob,
  DuplicateGroup,
  FsList,
  MediaFilter,
  MediaFile,
  MediaList,
  OrganizeBatch,
  OrganizePlan,
  OrganizeResult,
  ScanJob,
  StatsOverview,
  UndoResult,
  WatchStatus,
  DbBackup,
} from '../types'

const client = axios.create({ baseURL: '/api' })

export const scanApi = {
  start: (sourceDir: string) =>
    client.post<{ job_id: string }>('/scan/start', { source_dir: sourceDir }).then((r) => r.data),
  status: (jobId: string) =>
    client.get<ScanJob>(`/scan/status/${jobId}`).then((r) => r.data),
  latest: () => client.get<ScanJob>('/scan/latest').then((r) => r.data),
  cancel: (jobId: string) => client.post(`/scan/cancel/${jobId}`).then((r) => r.data),
}

export const fsApi = {
  list: (path: string) =>
    client.get<FsList>('/scan/fs/list', { params: { path } }).then((r) => r.data),
}

export const jobsApi = {
  status: (jobId: string) =>
    client.get<BackgroundJob>(`/jobs/${jobId}`).then((r) => r.data),
}

export const mediaApi = {
  list: (params: { page?: number; page_size?: number } & MediaFilter) =>
    client.get<MediaList>('/media', { params }).then((r) => r.data),
  dirs: () =>
    client.get<{ dirs: { dir: string; count: number }[] }>('/media/dirs').then((r) => r.data),
  years: () => client.get<{ years: number[] }>('/media/years').then((r) => r.data),
  heic: () => client.get<{ count: number; items: MediaFile[] }>('/media/heic').then((r) => r.data),
  analyze: () =>
    client.post<{ job_id: string; pending: number }>('/media/analyze').then((r) => r.data),
  cleanup: (params: { ids: number[]; action: 'trash' | 'move'; target_dir?: string; confirm_trash?: boolean }) =>
    client.post<{ done: number; failed: number; errors: string[]; job_id?: string }>('/media/cleanup', params).then((r) => r.data),
  convert: (mediaIds: number[]) =>
    client.post<{ job_id: string }>('/media/convert', { media_ids: mediaIds }).then((r) => r.data),
  purgeMissing: () =>
    client.post<{ removed: number }>('/media/purge-missing').then((r) => r.data),
  fixTime: (params: { ids: number[]; mode: 'shift' | 'set'; delta_hours?: number; set_datetime?: string }) =>
    client.post<{ updated: number; exif_written: number; skipped: number; errors: string[]; job_id?: string }>('/media/fix-time', params).then((r) => r.data),
  env: () =>
    client.get<{ ffmpeg: boolean; heif: boolean }>('/media/env').then((r) => r.data),
  openInSystem: (id: number) =>
    client.post<{ message: string }>(`/media/${id}/open`).then((r) => r.data),
  thumbnailUrl: (id: number) => `/api/media/${id}/thumbnail`,
  fileUrl: (id: number) => `/api/media/${id}/file`,
  detail: (id: number) => client.get<MediaFile>(`/media/${id}`).then((r) => r.data),
}

export const organizeApi = {
  plan: (params: {
    target_dir: string
    mode: string
    folder_structure: string
    naming: string
    folder_template?: string
    name_template?: string
    media_ids?: number[]
  }) => client.post<OrganizePlan>('/organize/plan', params).then((r) => r.data),
  patchPlan: (planId: string, params: { excluded_ids?: number[]; dst_overrides?: Record<string, string> }) =>
    client.patch<OrganizePlan>(`/organize/plan/${planId}`, params).then((r) => r.data),
  getPlan: (planId: string) =>
    client.get<OrganizePlan>(`/organize/plan/${planId}`).then((r) => r.data),
  execute: (planId: string) =>
    client.post<OrganizeResult>('/organize/execute', { plan_id: planId }).then((r) => r.data),
  undo: (batchId: string) =>
    client.post<UndoResult>('/organize/undo', { batch_id: batchId }).then((r) => r.data),
  cleanEmpty: (dirs: string[]) =>
    client.post<{ removed: number }>('/organize/clean-empty', { dirs }).then((r) => r.data),
  logs: (limit = 20) =>
    client.get<OrganizeBatch[]>('/organize/logs', { params: { limit } }).then((r) => r.data),
  exportCsvUrl: (batchId: string) => `/api/organize/logs/export?batch_id=${batchId}`,
}

export const duplicatesApi = {
  groups: () =>
    client.get<{ exact: DuplicateGroup[]; similar: DuplicateGroup[] }>('/duplicates').then((r) => r.data),
  resolve: (params: { keep_ids: number[]; remove_ids: number[]; action: 'move' | 'trash'; duplicates_dir?: string; confirm_trash?: boolean }) =>
    client.post<{ done: number; failed: number; errors: string[] }>('/duplicates/resolve', params).then((r) => r.data),
}

export const aiApi = {
  config: () => client.get<AiConfig>('/ai/config').then((r) => r.data),
  startTagging: (maxImages = 200) =>
    client.post<{ job_id: string }>('/ai/tag', { max_images: maxImages }).then((r) => r.data),
  status: (jobId: string) =>
    client.get<BackgroundJob>(`/ai/tag/${jobId}`).then((r) => r.data),
}

export const watchApi = {
  status: () => client.get<WatchStatus>('/watch/status').then((r) => r.data),
  toggle: (params: { enabled: boolean; watch_dir: string; target_dir: string; auto_organize: boolean }) =>
    client.post<{ message: string }>('/watch/toggle', params).then((r) => r.data),
  runNow: () => client.post<{ message: string }>('/watch/run-now').then((r) => r.data),
}

export const dbApi = {
  backups: () => client.get<{ items: DbBackup[] }>('/db/backups').then((r) => r.data),
  create: () =>
    client.post<{ filename: string; size: number }>('/db/backup').then((r) => r.data),
  restore: (filename: string) =>
    client.post<{ restored: string; safety_backup: string }>('/db/restore', { filename }).then((r) => r.data),
  remove: (filename: string) =>
    client.post<{ message: string }>('/db/backups/delete', { filename }).then((r) => r.data),
}

export const statsApi = {
  overview: () => client.get<StatsOverview>('/stats/overview').then((r) => r.data),
}

export const settingsApi = {
  get: () => client.get<AppSettings>('/settings').then((r) => r.data),
  update: (payload: Partial<AppSettings>) =>
    client.put<AppSettings>('/settings', payload).then((r) => r.data),
}
