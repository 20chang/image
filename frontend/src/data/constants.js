export const PRODUCT_RELATION_OPTIONS = [
  { value: 'same_product', label: '同款同规格' },
  { value: 'other_product', label: '其他商品' },
  { value: 'no_product', label: '不含商品' },
  { value: 'unknown', label: '不确定' },
]

export const AI_STATUS_OPTIONS = [
  { value: 'yes', label: '经过 AI 处理' },
  { value: 'no', label: '未经 AI 处理' },
  { value: 'unknown', label: '不确定' },
]

export const PLAN_ROLE_OPTIONS = [
  { value: 'primary', label: '主体依据', hint: '决定商品整体外观' },
  { value: 'detail', label: '细节补充', hint: '接口、支架、线束等指定部位' },
  { value: 'usage', label: '安装与使用', hint: '安装位置、朝向、使用关系' },
  { value: 'composition', label: '构图参考', hint: '位置、角度、大小和布局' },
  { value: 'style', label: '视觉风格', hint: '背景、光线和氛围' },
]

export const PRODUCT_RELATION_LABELS = Object.fromEntries(
  PRODUCT_RELATION_OPTIONS.map((o) => [o.value, o.label]),
)

export const AI_STATUS_LABELS = Object.fromEntries(
  AI_STATUS_OPTIONS.map((o) => [o.value, o.label]),
)

export const PLAN_ROLE_LABELS = Object.fromEntries(
  PLAN_ROLE_OPTIONS.map((o) => [o.value, o.label]),
)

// Legacy labels kept for old data display fallback.
export const SOURCE_LABELS = {
  same: '同款商品',
  other: '其他商品',
  ai: 'AI 生成',
  unknown: '未知来源',
}

export const TAB_IDS = ['references', 'plans', 'images']
