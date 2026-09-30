import { useState } from 'react'
import Button from '../ui/Button.jsx'
import DialogShell from '../ui/DialogShell.jsx'
import * as api from '../../services/productService.js'

export default function MoveProductDialog({
  product,
  folders,
  onClose,
  onMoved,
}) {
  const [folderId, setFolderId] = useState(product.folderId || '')
  const [loading, setLoading] = useState(false)
  const [failMsg, setFailMsg] = useState('')

  const target = folders.find((f) => f.id === folderId)

  const handleSubmit = async () => {
    if (!folderId) {
      setFailMsg('选择一个目标文件夹')
      return
    }
    if (folderId === product.folderId) {
      onClose()
      return
    }
    setLoading(true)
    setFailMsg('')
    try {
      const updated = await api.moveProduct(product.id, folderId)
      onMoved(updated, target)
    } catch (e) {
      setFailMsg(e.message || '移动失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <DialogShell
      title="移动商品"
      subtitle={`选择「${product.name}」要放入的文件夹。`}
      onClose={onClose}
      footer={
        <>
          <Button
            variant="secondary"
            size="sm"
            onClick={onClose}
            disabled={loading}
          >
            取消
          </Button>
          <Button size="sm" onClick={handleSubmit} loading={loading}>
            移动到所选文件夹
          </Button>
        </>
      }
    >
      <div role="radiogroup" aria-label="目标文件夹" className="space-y-2">
        {folders.map((f) => (
          <label
            key={f.id}
            className={`flex items-center gap-3 p-3 rounded-[var(--radius-sm)] border cursor-pointer transition-colors ${
              folderId === f.id
                ? 'border-[var(--accent)] bg-[var(--accent-soft)]'
                : 'border-[var(--border-whisper)] hover:bg-[var(--bg-hover)]'
            }`}
          >
            <input
              type="radio"
              name="folder"
              checked={folderId === f.id}
              onChange={() => setFolderId(f.id)}
              className="accent-[var(--accent)]"
            />
            <span className="text-[13.5px] font-medium text-[var(--text-1)]">
              {f.name}
            </span>
            {f.id === product.folderId && (
              <span className="ml-auto text-[11.5px] text-[var(--text-3)]">
                当前位置
              </span>
            )}
          </label>
        ))}
      </div>
      {failMsg && (
        <p role="alert" className="field-error">
          {failMsg}
        </p>
      )}
    </DialogShell>
  )
}
