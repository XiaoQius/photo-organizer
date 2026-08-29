export type MediaType = 'photo' | 'video' | 'doc' | 'audio' | 'archive'

export interface MediaFile {
  id: number
  path: string
  filename: string
  ext: string
  media_type: MediaType
  size: number
  mtime: number
  taken_at: string | null
  taken_source: 'exif' | 'video' | 'filename' | 'mtime' | null
  width: number | null
  height: number | null
  md5: string | null
  phash: string | null
  status: string
  category: 'normal' | 'screenshot' | 'chat_export'
  city: string | null
  gps_lat: number | null
  gps_lon: number | null
  blur_score: number | null
  quality_flag: 'blurry' | 'dark' | 'bright' | null
  tags: string[] | null
  codec: string | null
}

export interface MediaList {
  total: number
  page: number
  page_size: number
  items: MediaFile[]
}

export interface MediaFilter {
  media_type?: string
  year?: number
  month?: number
  category?: string
  quality?: string
  tag?: string
  search?: string
  dir?: string
  on_this_day?: number
  order?: 'time_desc' | 'time_asc' | 'size_desc' | 'name'
}

export interface DbBackup {
  filename: string
  size: number
  created_at: string
}

export interface ScanJob {
  job_id: string
  source_dir?: string
  status: 'running' | 'done' | 'error' | 'cancelled' | 'none'
  total: number
  processed: number
  current_file: string
  added: number
  updated: number
  skipped: number
  error: string
  started_at?: number
  finished_at?: number | null
}

export interface BackgroundJob {
  job_id: string
  kind: string
  label: string
  status: 'running' | 'done' | 'error' | 'cancelled' | 'none'
  total: number
  processed: number
  current: string
  result: Record<string, unknown>
  error: string
}

export interface FsList {
  path: string
  parent: string | null
  directories: string[]
}

export interface OrganizePlanItem {
  media_id: number
  filename: string
  media_type: string
  src: string
  dst: string
  dst_dir: string
  action: 'move' | 'copy' | 'skip'
  note: string
  size: number
  excluded: boolean
}

export interface OrganizePlan {
  plan_id: string
  items: OrganizePlanItem[]
}

export interface OrganizeResult {
  batch_id: string
  done: number
  failed: number
  skipped: number
  total: number
}

export interface OrganizeBatch {
  batch_id: string
  created_at: string
  total: number
  done: number
  failed: number
  skipped: number
  action: string
  undone: boolean
}

export interface DuplicateGroup {
  key: string
  kind: 'exact' | 'similar'
  keep_id: number
  recommended_id: number
  files: MediaFile[]
}

export interface StatsOverview {
  total_count: number
  total_size: number
  photo_count: number
  photo_size: number
  video_count: number
  video_size: number
  doc_count: number
  doc_size: number
  audio_count: number
  audio_size: number
  archive_count: number
  archive_size: number
  duplicate_count: number
  no_date_count: number
  screenshot_count: number
  chat_export_count: number
  flagged_count: number
  tagged_count: number
  located_count: number
  by_year: Record<string, number>
}

export interface AppSettings {
  folder_structure: string
  naming: string
  folder_template: string
  name_template: string
  default_mode: 'move' | 'copy'
  last_source_dir: string
  last_target_dir: string
  watch_dir: string
  watch_enabled: string
  watch_auto_organize: string
  watch_target_dir: string
  scan_docs: string
  scan_audio: string
  scan_archives: string
  exclude_names: string
  exclude_paths: string
}

export interface WatchStatus {
  watch_dir: string
  watch_target_dir: string
  watch_auto_organize: boolean
  enabled: boolean
  running: boolean
  last_run: string | null
  last_result: string
  error: string
}

export interface AiConfig {
  configured: boolean
  model: string
}

export interface UndoResult {
  batch_id: string
  moved_back: number
  copies_removed: number
  failed: number
  total: number
}
