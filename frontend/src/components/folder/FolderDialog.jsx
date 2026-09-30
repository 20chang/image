import { useState } from 'react'
import Button from '../ui/Button.jsx'
import Input from '../ui/Input.jsx'
import DialogShell from '../ui/DialogShell.jsx'
import * as api from '../../services/productService.js'

export default function FolderDialog({ mode = 'create', folder, onClose, onSaved }) {
  const isEdit = mode === 'edit' && folder
  const [name, setName] = useState(isEdit ? folder.name : '')
  const [error, setError] = useState('')
  const [failMsg, setFailMsg] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async () => {
    if (!name.trim()) {
      setError('填写文件夹名称后才能保存')
      return
    }
    setLoading(true)
    setFailMsg('')
    try {
      const saved = isEdit
        ? await api.renameFolder(folder.id, { name })
        : await api.createFolder({ name })
      onSaved(saved)
    } catch (e) {
      setFailMsg(e.message || '保存失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <DialogShell
      title={isEdit ? '重命名文件夹' : '新建文件夹'}
      subtitle={isEdit ? '名称会立即更新到列表。' : '用文件夹归类商品，例如按站点或项目。'}
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
            {isEdit ? '保存名称' : '创建'}
          </Button>
        </>
      }
    >
      <Input
        label="文件夹名称"
        name="folder-name"
        placeholder="例如：摩托车配件"
        value={name}
        onChange={(e) => {
          setName(e.target.value)
          setError('')
        }}
        error={error}
        autoFocus
        onKeyDown={(e) => {
          if (e.key === 'Enter') handleSubmit()
        }}
      />
      {failMsg && (
        <p role="alert" className="field-error">
          {failMsg}
        </p>
      )}
    </DialogShell>
  )
}
