import { useState } from 'react'
import Button from '../ui/Button.jsx'
import Input from '../ui/Input.jsx'
import ConfirmDialog from '../ui/ConfirmDialog.jsx'
import DialogShell from '../ui/DialogShell.jsx'
import * as api from '../../services/productService.js'

export default function CreateProductDialog({
  folderId,
  folderName,
  onClose,
  onSuccess,
}) {
  const [formData, setFormData] = useState({ name: '', market: '', facts: '' })
  const [errors, setErrors] = useState({})
  const [loading, setLoading] = useState(false)
  const [failMsg, setFailMsg] = useState('')
  const [confirmLeave, setConfirmLeave] = useState(false)

  const hasContent =
    formData.name.trim() || formData.market.trim() || formData.facts.trim()

  const requestClose = () => {
    if (hasContent && !loading) {
      setConfirmLeave(true)
      return
    }
    onClose()
  }

  const handleSubmit = async () => {
    if (!formData.name.trim()) {
      setErrors({ name: '填写商品名称后才能创建' })
      return
    }
    setLoading(true)
    setFailMsg('')
    try {
      const created = await api.createProduct({ folderId, ...formData })
      onSuccess(created)
    } catch (e) {
      setFailMsg(e.message || '创建失败，填写的内容已保留')
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <DialogShell
        title="新建商品"
        subtitle={`保存到${folderName ? `「${folderName}」` : '当前文件夹'}。图片稍后在详情页上传。`}
        onClose={requestClose}
        footer={
          <>
            <Button
              variant="secondary"
              size="sm"
              onClick={requestClose}
              disabled={loading}
            >
              取消
            </Button>
            <Button size="sm" onClick={handleSubmit} loading={loading}>
              创建并进入
            </Button>
          </>
        }
      >
        <Input
          label="商品名称"
          name="name"
          placeholder="例如：摩托车高亮辅助灯"
          value={formData.name}
          onChange={(e) => {
            setFormData({ ...formData, name: e.target.value })
            setErrors({})
          }}
          error={errors.name}
          autoFocus
        />
        <Input
          label="目标市场"
          name="market"
          hint="选填"
          placeholder="例如：巴西、北美"
          value={formData.market}
          onChange={(e) => setFormData({ ...formData, market: e.target.value })}
        />
        <div className="mb-1">
          <label className="field-label" htmlFor="facts">
            商品说明 / 已知事实
          </label>
          <textarea
            id="facts"
            className="field-input min-h-[104px] h-auto py-2.5 resize-y"
            placeholder="记录用途、特点和限制。未知参数先留空。"
            value={formData.facts}
            onChange={(e) =>
              setFormData({ ...formData, facts: e.target.value })
            }
          />
          <p className="field-hint">选填。这里只写已确认的信息。</p>
        </div>
        {failMsg && (
          <p role="alert" className="field-error">
            {failMsg}
          </p>
        )}
      </DialogShell>

      {confirmLeave && (
        <ConfirmDialog
          title="放弃已填写的内容？"
          message="关闭后这些资料不会保存。"
          confirmText="继续编辑"
          cancelText="放弃输入"
          showDiscard={false}
          onConfirm={() => setConfirmLeave(false)}
          onCancel={() => {
            setConfirmLeave(false)
            onClose()
          }}
        />
      )}
    </>
  )
}
