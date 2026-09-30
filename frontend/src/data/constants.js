export const SOURCE_OPTIONS = [
  { value: 'same', label: '同款商品' },
  { value: 'other', label: '其他商品' },
  { value: 'ai', label: 'AI 生成' },
  { value: 'unknown', label: '未知来源' },
]

export const PURPOSE_OPTIONS = [
  { value: 'overall', label: '整体外观' },
  { value: 'detail', label: '局部细节' },
  { value: 'install', label: '安装方式' },
  { value: 'composition', label: '构图参考' },
]

export const SOURCE_LABELS = Object.fromEntries(
  SOURCE_OPTIONS.map((o) => [o.value, o.label]),
)

export const PURPOSE_LABELS = Object.fromEntries(
  PURPOSE_OPTIONS.map((o) => [o.value, o.label]),
)

export const TAB_IDS = ['references', 'plans', 'images']
