import { AlertCircle, CheckCircle2, Trash2, X } from 'lucide-react'
import Button from '../ui/Button.jsx'
import {
  AI_STATUS_OPTIONS,
  PRODUCT_RELATION_OPTIONS,
} from '../../data/constants.js'

export default function ReferenceEditor({
  draft,
  dirty,
  isMobile,
  onChange,
  onSave,
  onRevert,
  onCloseMobile,
  onRemove,
  saveError,
}) {
  const header = (
    <div className="flex items-center justify-between border-b border-[var(--border-whisper)] bg-[var(--bg-surface)] px-4 py-3">
      <h3 className="m-0 text-[13px] font-semibold tracking-[-0.01em] text-[var(--text-1)]">
        编辑参考图
      </h3>
      {isMobile && (
        <button
          type="button"
          onClick={onCloseMobile}
          className="p-1 text-[var(--text-3)] hover:text-[var(--text-1)]"
          aria-label="关闭面板"
        >
          <X className="w-4 h-4" aria-hidden="true" />
        </button>
      )}
    </div>
  )

  if (!draft) {
    return (
      <>
        {header}
        <div className="flex flex-1 flex-col items-center justify-center p-6 text-center">
          <p className="text-[12.5px] leading-relaxed text-[var(--text-3)]">
            在左侧选择一张参考图
            <br />
            即可编辑与商品的关系、AI 状态和备注
          </p>
        </div>
      </>
    )
  }

  const relation = draft.productRelation || 'unknown'
  const aiStatus = draft.aiStatus || 'unknown'

  return (
    <>
      {header}

      <div className="flex-1 overflow-y-auto p-4">
        <fieldset className="mb-5 border-0 p-0 m-0">
          <legend className="mb-1 text-[12.5px] font-semibold text-[var(--text-1)]">
            与当前商品的关系
          </legend>
          <p className="mb-2.5 text-[11px] text-[var(--text-3)]">
            这张图和当前商品是什么关系？允许「不确定」。
          </p>
          <div className="space-y-1.5">
            {PRODUCT_RELATION_OPTIONS.map((opt) => (
              <label
                key={opt.value}
                className={`flex cursor-pointer items-center rounded-[var(--radius-sm)] border px-2.5 py-2 transition-colors ${
                  relation === opt.value
                    ? 'border-[var(--accent)] bg-[var(--accent-soft)]'
                    : 'border-[var(--border-whisper)] hover:bg-[var(--bg-hover)]'
                }`}
              >
                <input
                  type="radio"
                  name="productRelation"
                  value={opt.value}
                  checked={relation === opt.value}
                  onChange={() => onChange({ ...draft, productRelation: opt.value })}
                  className="accent-[var(--accent)]"
                />
                <span className="ml-2.5 text-[12.5px] font-medium text-[var(--text-1)]">
                  {opt.label}
                </span>
              </label>
            ))}
          </div>
        </fieldset>

        <fieldset className="mb-5 border-0 p-0 m-0">
          <legend className="mb-1 text-[12.5px] font-semibold text-[var(--text-1)]">
            是否经过 AI 处理
          </legend>
          <p className="mb-2.5 text-[11px] text-[var(--text-3)]">
            是否经 AI 生成或修改？与「关系」相互独立。
          </p>
          <div className="space-y-1.5">
            {AI_STATUS_OPTIONS.map((opt) => (
              <label
                key={opt.value}
                className={`flex cursor-pointer items-center rounded-[var(--radius-sm)] border px-2.5 py-2 transition-colors ${
                  aiStatus === opt.value
                    ? 'border-[var(--accent)] bg-[var(--accent-soft)]'
                    : 'border-[var(--border-whisper)] hover:bg-[var(--bg-hover)]'
                }`}
              >
                <input
                  type="radio"
                  name="aiStatus"
                  value={opt.value}
                  checked={aiStatus === opt.value}
                  onChange={() => onChange({ ...draft, aiStatus: opt.value })}
                  className="accent-[var(--accent)]"
                />
                <span className="ml-2.5 text-[12.5px] font-medium text-[var(--text-1)]">
                  {opt.label}
                </span>
              </label>
            ))}
          </div>
        </fieldset>

        <div className="mb-4">
          <label
            className="mb-1 block text-[12.5px] font-semibold text-[var(--text-1)]"
            htmlFor="ref-desc"
          >
            备注
          </label>
          <textarea
            id="ref-desc"
            className="field-input min-h-[96px] h-auto py-2 text-[12.5px] resize-y"
            placeholder="例如：仅参考连接件位置，不参考背景"
            value={draft.desc}
            onChange={(e) => onChange({ ...draft, desc: e.target.value })}
          />
          <p className="mt-1.5 text-[11px] text-[var(--text-3)]">
            备注填 <code>error</code> 并保存可模拟失败。
          </p>
          {saveError && (
            <p role="alert" className="field-error">
              {saveError}
            </p>
          )}
        </div>

        <div className="border-t border-[var(--border-whisper)] pt-3">
          <button
            type="button"
            onClick={onRemove}
            className="inline-flex items-center text-[12px] font-medium text-[var(--danger)] hover:underline"
          >
            <Trash2 className="mr-1 w-3.5 h-3.5" aria-hidden="true" />
            从本商品移除
          </button>
          <p className="mt-1 text-[11px] text-[var(--text-3)]">
            被图片方案引用时无法删除。只解除关联，不会删除全部历史记录。
          </p>
        </div>
      </div>

      <div className="flex gap-2 border-t border-[var(--border-whisper)] bg-[var(--bg-surface)] p-3">
        {dirty ? (
          <>
            <Button variant="secondary" size="sm" className="flex-1" onClick={onRevert}>
              取消修改
            </Button>
            <Button size="sm" className="flex-1" onClick={onSave}>
              保存
            </Button>
          </>
        ) : (
          <Button variant="success" size="sm" className="w-full" disabled>
            <CheckCircle2 className="w-3.5 h-3.5" aria-hidden="true" />
            已保存
          </Button>
        )}
      </div>
    </>
  )
}
