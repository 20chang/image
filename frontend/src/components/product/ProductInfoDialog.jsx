import { useState } from 'react'
import Button from '../ui/Button.jsx'
import Input from '../ui/Input.jsx'
import DialogShell from '../ui/DialogShell.jsx'
import * as api from '../../services/productService.js'

export default function ProductInfoDialog({ product, onClose, onSaved }) {
  const [formData, setFormData] = useState({
    name: product.name || '',
    market: product.market || '',
    facts: product.facts || '',
  })
  const [errors, setErrors] = useState({})
  const [loading, setLoading] = useState(false)
  const [failMsg, setFailMsg] = useState('')

  const handleSubmit = async () => {
    if (!formData.name.trim()) {
      setErrors({ name: '填写商品名称后才能保存' })
      return
    }
    setLoading(true)
    setFailMsg('')
    try {
      const updated = await api.updateProduct(product.id, formData)
      onSaved(updated)
    } catch (e) {
      setFailMsg(e.message || '保存失败，填写的内容已保留')
    } finally {
      setLoading(false)
    }
  }

  return (
    <DialogShell
      title="编辑商品资料"
      subtitle="更新名称、市场和已知事实。"
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
            保存更改
          </Button>
        </>
      }
    >
      <Input
        label="商品名称"
        name="name"
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
        value={formData.market}
        onChange={(e) => setFormData({ ...formData, market: e.target.value })}
      />
      <div className="mb-1">
        <label className="field-label" htmlFor="facts-edit">
          商品说明 / 已知事实
        </label>
        <textarea
          id="facts-edit"
          className="field-input min-h-[104px] h-auto py-2.5 resize-y"
          value={formData.facts}
          onChange={(e) => setFormData({ ...formData, facts: e.target.value })}
        />
      </div>
      {failMsg && (
        <p role="alert" className="field-error">
          {failMsg}
        </p>
      )}
    </DialogShell>
  )
}
