import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Folder, FolderPlus, AlertCircle } from 'lucide-react'
import Button from '../components/ui/Button.jsx'
import ConfirmDialog from '../components/ui/ConfirmDialog.jsx'
import EmptyState from '../components/ui/EmptyState.jsx'
import PageHeader from '../components/layout/PageHeader.jsx'
import FolderCard from '../components/folder/FolderCard.jsx'
import FolderDialog from '../components/folder/FolderDialog.jsx'
import * as api from '../services/productService.js'

export default function FolderListPage() {
  const navigate = useNavigate()
  const [folders, setFolders] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [dialog, setDialog] = useState(null)
  const [pendingDelete, setPendingDelete] = useState(null)
  const [deleteError, setDeleteError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      setFolders(await api.listFolders())
    } catch (e) {
      setError(e.message || '加载失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const handleDelete = async () => {
    if (!pendingDelete) return
    setDeleteError('')
    try {
      await api.deleteFolder(pendingDelete.id)
      setPendingDelete(null)
      await load()
    } catch (e) {
      setDeleteError(e.message || '删除失败')
    }
  }

  return (
    <div className="page">
      <PageHeader
        title="商品文件夹"
        desc="先按业务线或站点分组，再进入文件夹整理商品与参考图。"
        actions={
          <Button size="sm" onClick={() => setDialog({ mode: 'create' })}>
            <FolderPlus className="w-4 h-4" aria-hidden="true" />
            新建文件夹
          </Button>
        }
      />

      {loading && (
        <div className="card-grid" aria-hidden="true">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="skeleton h-28" />
          ))}
        </div>
      )}

      {!loading && error && (
        <div
          role="alert"
          className="panel flex flex-col items-center text-center px-6 py-14"
        >
          <AlertCircle
            className="w-8 h-8 text-[var(--danger)] mb-3"
            aria-hidden="true"
          />
          <p className="text-[var(--text-1)] mb-1 font-medium">{error}</p>
          <p className="text-[13px] text-[var(--text-2)] mb-5">
            检查后端是否在运行，然后重试。
          </p>
          <Button variant="secondary" size="sm" onClick={load}>
            重新加载
          </Button>
        </div>
      )}

      {!loading && !error && folders.length === 0 && (
        <EmptyState
          icon={<Folder className="w-6 h-6" />}
          title="创建第一个文件夹"
          desc="文件夹用来归类商品，例如按站点、季节或项目划分。"
          action={{
            label: '新建文件夹',
            onClick: () => setDialog({ mode: 'create' }),
          }}
        />
      )}

      {!loading && !error && folders.length > 0 && (
        <div className="card-grid">
          {folders.map((f) => (
            <FolderCard
              key={f.id}
              folder={f}
              onOpen={() => navigate(`/folders/${f.id}`)}
              onRename={() => setDialog({ mode: 'edit', folder: f })}
              onDelete={() => {
                setDeleteError('')
                setPendingDelete(f)
              }}
            />
          ))}
        </div>
      )}

      {dialog && (
        <FolderDialog
          mode={dialog.mode}
          folder={dialog.folder}
          onClose={() => setDialog(null)}
          onSaved={() => {
            setDialog(null)
            load()
          }}
        />
      )}

      {pendingDelete && (
        <ConfirmDialog
          title="删除文件夹"
          message={
            deleteError ||
            `「${pendingDelete.name}」里若还有商品，需要先移动或删除它们。`
          }
          confirmText="删除文件夹"
          cancelText="取消"
          showDiscard={false}
          onConfirm={handleDelete}
          onCancel={() => {
            setPendingDelete(null)
            setDeleteError('')
          }}
        />
      )}
    </div>
  )
}
