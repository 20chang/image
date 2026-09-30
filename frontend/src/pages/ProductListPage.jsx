import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  Image as ImageIcon,
  Plus,
  Search,
  X,
  AlertCircle,
  ArrowLeft,
} from 'lucide-react'
import Button from '../components/ui/Button.jsx'
import EmptyState from '../components/ui/EmptyState.jsx'
import Breadcrumbs from '../components/layout/Breadcrumbs.jsx'
import PageHeader, {
  StatStrip,
  Toolbar,
} from '../components/layout/PageHeader.jsx'
import ProductCard from '../components/product/ProductCard.jsx'
import CreateProductDialog from '../components/product/CreateProductDialog.jsx'
import * as api from '../services/productService.js'

export default function ProductListPage() {
  const { folderId } = useParams()
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [products, setProducts] = useState([])
  const [folder, setFolder] = useState(null)
  const [allFolders, setAllFolders] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notFound, setNotFound] = useState(false)
  const [showCreate, setShowCreate] = useState(false)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      const [f, list] = await Promise.all([
        api.getFolder(folderId),
        api.listFolders(),
      ])
      if (cancelled) return
      if (!f) {
        setNotFound(true)
        setLoading(false)
        return
      }
      setFolder(f)
      setAllFolders(list)
      setNotFound(false)
    })()
    return () => {
      cancelled = true
    }
  }, [folderId])

  const load = useCallback(async () => {
    if (!folderId) return
    setLoading(true)
    setError('')
    try {
      const list = await api.listProducts({ folderId, name: search })
      setProducts(list)
    } catch (e) {
      setError(e.message || '加载失败')
    } finally {
      setLoading(false)
    }
  }, [folderId, search])

  useEffect(() => {
    const t = setTimeout(load, 200)
    return () => clearTimeout(t)
  }, [load])

  const folderStat = allFolders.find((f) => f.id === folderId)
  const refTotal =
    products.reduce((n, p) => n + (p.refCount || 0), 0) ||
    folderStat?.refCount ||
    0

  if (notFound) {
    return (
      <div className="page">
        <EmptyState
          icon={<AlertCircle className="w-6 h-6 text-[var(--danger)]" />}
          title="未找到这个文件夹"
          desc="它可能已被删除。返回商品库查看现有文件夹。"
          action={{ label: '返回商品库', onClick: () => navigate('/folders') }}
        />
      </div>
    )
  }

  return (
    <div className="page">
      <PageHeader
        breadcrumb={
          <Breadcrumbs
            items={[{ label: folder?.name || '…', key: folderId }]}
          />
        }
        title={folder?.name || '商品库'}
        desc="管理该文件夹下的商品资料与参考图，为图片生成做准备。"
        actions={
          <>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => navigate('/folders')}
            >
              <ArrowLeft className="w-3.5 h-3.5" aria-hidden="true" />
              全部文件夹
            </Button>
            <Button size="sm" onClick={() => setShowCreate(true)}>
              <Plus className="w-4 h-4" aria-hidden="true" />
              新建商品
            </Button>
          </>
        }
      />

      <StatStrip
        items={[
          { label: '商品', value: products.length },
          { label: '参考图', value: refTotal },
          {
            label: '最近更新',
            value: products[0]?.updatedAt?.slice(0, 10) || '—',
          },
        ]}
      />

      <Toolbar>
        <div className="relative flex-1 min-w-[200px] max-w-md">
          <label className="sr-only" htmlFor="search-products">
            搜索商品名称
          </label>
          <Search
            className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-3)] pointer-events-none"
            aria-hidden="true"
          />
          <input
            id="search-products"
            type="text"
            placeholder="按名称搜索本文件夹内的商品"
            className="field-input field-search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          {search && (
            <button
              type="button"
              onClick={() => setSearch('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded text-[var(--text-3)] hover:text-[var(--text-1)] hover:bg-[var(--bg-hover)]"
              aria-label="清空搜索"
            >
              <X className="w-4 h-4" aria-hidden="true" />
            </button>
          )}
        </div>
        {search && (
          <p className="text-[12px] text-[var(--text-3)] tabular-nums">
            匹配 {products.length} 个商品
          </p>
        )}
      </Toolbar>

      {loading && (
        <div className="card-grid" aria-hidden="true">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="skeleton h-56" />
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
          <Button variant="secondary" size="sm" onClick={load}>
            重新加载
          </Button>
        </div>
      )}

      {!loading && !error && products.length === 0 && (
        <EmptyState
          icon={<ImageIcon className="w-6 h-6" />}
          title={search ? '没有匹配的商品' : '在这个文件夹里添加商品'}
          desc={
            search
              ? '换一个名称关键词，或清空搜索查看全部商品。'
              : '每个商品可以上传参考图并标注来源、用途，作为后续生成的素材库。'
          }
          action={
            search
              ? { label: '清空搜索', onClick: () => setSearch('') }
              : { label: '新建商品', onClick: () => setShowCreate(true) }
          }
        />
      )}

      {!loading && !error && products.length > 0 && (
        <div className="card-grid">
          {products.map((p) => (
            <ProductCard
              key={p.id}
              product={p}
              onClick={() => navigate(`/folders/${folderId}/products/${p.id}`)}
            />
          ))}
        </div>
      )}

      {showCreate && folderId && (
        <CreateProductDialog
          folderId={folderId}
          folderName={folder?.name}
          onClose={() => setShowCreate(false)}
          onSuccess={(created) => {
            setShowCreate(false)
            navigate(`/folders/${folderId}/products/${created.id}`)
          }}
        />
      )}
    </div>
  )
}
