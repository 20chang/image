import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import {
  AlertCircle,
  ChevronDown,
  ChevronLeft,
  FolderInput,
  Image as ImageIcon,
  Layers,
  Upload,
} from 'lucide-react'
import Button from '../components/ui/Button.jsx'
import Badge from '../components/ui/Badge.jsx'
import EmptyState from '../components/ui/EmptyState.jsx'
import ConfirmDialog from '../components/ui/ConfirmDialog.jsx'
import Breadcrumbs from '../components/layout/Breadcrumbs.jsx'
import ProductInfoDialog from '../components/product/ProductInfoDialog.jsx'
import MoveProductDialog from '../components/folder/MoveProductDialog.jsx'
import ReferenceCard from '../components/reference/ReferenceCard.jsx'
import ReferenceEditor from '../components/reference/ReferenceEditor.jsx'
import ImagePreview from '../components/reference/ImagePreview.jsx'
import ImagePlansPanel from '../components/plan/ImagePlansPanel.jsx'
import { TAB_IDS } from '../data/constants.js'
import * as api from '../services/productService.js'

export default function ProductDetailPage() {
  const { folderId, productId } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()

  const rawTab = searchParams.get('tab') || 'references'
  const tab = TAB_IDS.includes(rawTab) ? rawTab : 'references'

  const [product, setProduct] = useState(null)
  const [folder, setFolder] = useState(null)
  const [allFolders, setAllFolders] = useState([])
  const [notFound, setNotFound] = useState(false)
  const [showFacts, setShowFacts] = useState(true)
  // Focus mode: collapse top chrome while working on reference images
  const [chromeCompact, setChromeCompact] = useState(false)
  const [showEdit, setShowEdit] = useState(false)
  const [showMove, setShowMove] = useState(false)
  const [references, setReferences] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [draft, setDraft] = useState(null)
  const [draftBase, setDraftBase] = useState(null)
  const [saveError, setSaveError] = useState('')
  const [previewUrl, setPreviewUrl] = useState(null)
  const [pendingAction, setPendingAction] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [isMobile, setIsMobile] = useState(() => window.innerWidth < 1024)

  const fileInputRef = useRef(null)

  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth < 1024)
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  const loadProduct = useCallback(async () => {
    setNotFound(false)
    const p = await api.getProduct(productId)
    if (!p || (folderId && p.folderId !== folderId)) {
      setNotFound(true)
      setProduct(null)
      return
    }
    setProduct(p)
    const f = await api.getFolder(p.folderId)
    setFolder(f)
  }, [productId, folderId])

  const loadRefs = useCallback(async () => {
    const list = await api.listReferences(productId)
    setReferences(list)
  }, [productId])

  useEffect(() => {
    loadProduct()
    loadRefs()
    api.listFolders().then(setAllFolders)
  }, [loadProduct, loadRefs])

  // Reset selection when product changes
  useEffect(() => {
    setSelectedId(null)
    setDraft(null)
    setDraftBase(null)
    setSaveError('')
  }, [productId])

  // Load draft when selection changes (keep base snapshot for dirty check / revert)
  useEffect(() => {
    if (!selectedId) {
      setDraft(null)
      setDraftBase(null)
      setSaveError('')
      return
    }
    const target = references.find((r) => r.id === selectedId)
    if (target) {
      setDraft({ ...target })
      setDraftBase({ ...target })
      setSaveError('')
    }
  }, [selectedId]) // eslint-disable-line react-hooks/exhaustive-deps

  const dirty = Boolean(
    draft &&
      draftBase &&
      (draft.productRelation !== draftBase.productRelation ||
        draft.aiStatus !== draftBase.aiStatus ||
        draft.desc !== draftBase.desc),
  )

  const guard = (action) => {
    if (dirty) {
      setPendingAction(() => action)
    } else {
      action()
    }
  }

  const handleTabChange = (next) => {
    guard(() => setSearchParams({ tab: next }, { replace: false }))
  }

  const handleBack = () => {
    guard(() => navigate(`/folders/${product?.folderId || folderId}`))
  }

  const handleSelect = (id) => {
    guard(() => {
      setSelectedId(id)
      if (id) {
        // Give the image + editor more vertical space
        setChromeCompact(true)
        setShowFacts(false)
      }
    })
  }

  const handleSave = async () => {
    if (!draft || !selectedId) return
    setSaveError('')
    try {
      const saved = await api.saveReferenceMeta(productId, selectedId, draft)
      setReferences((prev) =>
        prev.map((r) => (r.id === selectedId ? saved : r)),
      )
      setDraft({ ...saved })
      setDraftBase({ ...saved })
    } catch (e) {
      setSaveError(e.message || '保存失败，输入已保留')
    }
  }

  const handleRevert = () => {
    if (draftBase) {
      setDraft({ ...draftBase })
      setSaveError('')
    }
  }

  const handleUploadClick = () => {
    guard(() => fileInputRef.current?.click())
  }

  const handleFiles = async (fileList) => {
    const files = Array.from(fileList || [])
    if (!files.length) return
    setUploading(true)
    try {
      for (const file of files) {
        if (!file.type.startsWith('image/')) continue
        await api.addReference(productId, { file, status: 'success' })
      }
      setReferences(await api.listReferences(productId))
    } catch (e) {
      setSaveError(e.message || '上传失败')
    } finally {
      setUploading(false)
    }
  }

  const handleRetry = async (refId) => {
    // Real uploads either succeed or fail at request time; retry is a no-op refresh
    setReferences(await api.listReferences(productId))
  }

  const handleRemove = async (refId) => {
    try {
      await api.removeReference(productId, refId)
      if (selectedId === refId) setSelectedId(null)
      setReferences(await api.listReferences(productId))
      setSaveError('')
    } catch (e) {
      setSaveError(e.message || '删除失败，图片可能仍被方案引用')
    }
  }

  const handleMove = async (refId, direction) => {
    const list = await api.reorderReferences(productId, refId, direction)
    setReferences(list)
  }

  const requestRemoveSelected = () => {
    if (!selectedId) return
    setPendingAction(() => () => handleRemove(selectedId))
  }

  if (notFound) {
    return (
      <div className="p-10 flex flex-col items-center">
        <AlertCircle className="w-12 h-12 text-red-500 mb-4" />
        <h2 className="text-xl font-bold mb-4">未找到这个商品</h2>
        <Button onClick={() => navigate(`/folders/${folderId}`)}>
          返回商品库
        </Button>
      </div>
    )
  }

  if (!product) {
    return (
      <div className="p-10 flex flex-col items-center text-gray-500">
        <p>加载中...</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      <div
        className={`bg-white border-b border-[var(--border-whisper)] z-10 shrink-0 transition-[padding] duration-200 ease-[var(--ease-out)] ${
          chromeCompact ? 'pb-0' : ''
        }`}
      >
        <div
          className={`transition-all duration-200 ease-[var(--ease-out)] overflow-hidden ${
            chromeCompact ? 'max-h-0 opacity-0 pointer-events-none' : 'max-h-10 opacity-100'
          }`}
        >
          <div className="px-6 pt-4">
            <Breadcrumbs
              items={[
                {
                  label: folder?.name || '文件夹',
                  to: `/folders/${product.folderId}`,
                  key: product.folderId,
                },
                { label: product.name, key: product.id },
              ]}
            />
          </div>
        </div>

        <div
          className={`flex flex-col md:flex-row md:items-center justify-between gap-2 ${
            chromeCompact ? 'px-4 py-2' : 'px-6 pb-4'
          }`}
        >
          <div className="flex items-center gap-2 min-w-0">
            <button
              type="button"
              onClick={handleBack}
              className="p-1.5 rounded-[var(--radius-xs)] text-[var(--text-3)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-1)] transition-colors"
              aria-label="返回商品库"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <h1
              className={`font-semibold tracking-[-0.02em] text-[var(--text-1)] truncate transition-all duration-200 ${
                chromeCompact ? 'text-[14px]' : 'text-[18px]'
              }`}
              title={product.name}
            >
              {product.name}
            </h1>
            {product.market && !chromeCompact && <Badge>{product.market}</Badge>}
          </div>

          <div className="flex items-center gap-2 self-start md:self-auto">
            {chromeCompact ? (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setChromeCompact(false)
                  setShowFacts(true)
                }}
              >
                展开资料
              </Button>
            ) : (
              <>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setShowMove(true)}
                >
                  <FolderInput className="w-3.5 h-3.5" />
                  移动到…
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setShowEdit(true)}
                >
                  编辑资料
                </Button>
              </>
            )}
          </div>
        </div>

        <div
          className={`transition-all duration-200 ease-[var(--ease-out)] overflow-hidden ${
            chromeCompact ? 'max-h-0 opacity-0' : 'max-h-32 opacity-100'
          }`}
        >
          <div className="px-6 pb-2">
            <div className="rounded-[var(--radius-sm)] overflow-hidden border border-[var(--border-whisper)] bg-[var(--bg-subtle)]">
              <button
                type="button"
                onClick={() => setShowFacts(!showFacts)}
                className="w-full px-3.5 py-2 flex items-center justify-between text-[12.5px] font-medium text-[var(--text-2)] hover:bg-[var(--bg-hover)]"
                aria-expanded={showFacts}
              >
                <span>已知事实</span>
                <ChevronDown
                  className={`w-3.5 h-3.5 transition-transform duration-200 ${
                    showFacts ? 'rotate-180' : ''
                  }`}
                  aria-hidden="true"
                />
              </button>
              {showFacts && (
                <div className="px-3.5 py-2.5 text-[12.5px] text-[var(--text-2)] border-t border-[var(--border-whisper)] bg-[var(--bg-surface)]">
                  {product.facts || (
                    <span className="text-[var(--text-3)]">
                      暂无事实记录，可在「编辑资料」中补充。
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>

          <div className="px-6 pt-3 flex gap-5 border-t border-[var(--border-whisper)]">
            {[
              { id: 'references', label: '资料与参考图' },
              { id: 'plans', label: '图片方案' },
              { id: 'images', label: '图片与版本' },
            ].map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => handleTabChange(t.id)}
                className={`pb-2.5 text-[13px] font-medium border-b-2 transition-colors ${
                  tab === t.id
                    ? 'border-[var(--accent)] text-[var(--accent-text)]'
                    : 'border-transparent text-[var(--text-3)] hover:text-[var(--text-1)]'
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>

        {/* Compact tab strip while focused on images */}
        {chromeCompact && (
          <div className="px-4 pb-0 flex gap-4 border-t border-[var(--border-whisper)] pt-1">
            {[
              { id: 'references', label: '参考图' },
              { id: 'plans', label: '方案' },
              { id: 'images', label: '版本' },
            ].map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => handleTabChange(t.id)}
                className={`pb-1.5 text-[12px] font-medium border-b-2 transition-colors ${
                  tab === t.id
                    ? 'border-[var(--accent)] text-[var(--accent-text)]'
                    : 'border-transparent text-[var(--text-3)] hover:text-[var(--text-1)]'
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="flex-1 overflow-hidden bg-[var(--bg-page)] relative">
        {tab === 'references' && (
          <div className="flex flex-col lg:flex-row h-full">
            <div className="flex-1 overflow-y-auto p-5 lg:p-6">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="m-0 text-[12.5px] font-semibold tracking-[-0.01em] text-[var(--text-2)]">
                  参考图
                  <span className="ml-1.5 font-normal text-[var(--text-3)] tabular-nums">
                    {references.length}
                  </span>
                </h2>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={handleUploadClick}
                  loading={uploading}
                >
                  <Upload className="w-3.5 h-3.5" aria-hidden="true" />
                  上传参考图
                </Button>
              </div>

              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                multiple
                className="hidden"
                onChange={(e) => {
                  handleFiles(e.target.files)
                  e.target.value = ''
                }}
              />

              <div
                className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-4 pb-20 lg:pb-0"
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault()
                  handleFiles(e.dataTransfer.files)
                }}
              >
                {references.map((item, index) => (
                  <ReferenceCard
                    key={item.id}
                    item={item}
                    index={index}
                    selected={item.id === selectedId}
                    onSelect={handleSelect}
                    onPreview={setPreviewUrl}
                    onMove={handleMove}
                    canMoveUp={index > 0}
                    canMoveDown={index < references.length - 1}
                    onRetry={handleRetry}
                    onRemove={handleRemove}
                  />
                ))}

                <div
                  role="button"
                  tabIndex={0}
                  onClick={handleUploadClick}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') handleUploadClick()
                  }}
                  className="aspect-square rounded-[var(--radius-md)] border border-dashed border-[var(--border-quiet)] bg-[var(--bg-surface)] flex flex-col items-center justify-center cursor-pointer text-[var(--text-3)] hover:border-[var(--accent)] hover:text-[var(--accent-text)] transition-colors"
                >
                  <Upload className="w-7 h-7 mb-2" aria-hidden="true" />
                  <span className="text-[12px] font-medium">点击或拖入上传</span>
                </div>
              </div>
            </div>

            <div
              className={`${
                isMobile
                  ? `fixed inset-y-0 right-0 z-40 w-full max-w-sm shadow-[var(--shadow-3)] transform transition-transform ${
                      selectedId ? 'translate-x-0' : 'translate-x-full'
                    }`
                  : 'relative w-80 border-l border-[var(--border-whisper)]'
              } bg-[var(--bg-raised)] flex flex-col`}
            >
              <ReferenceEditor
                draft={draft}
                dirty={dirty}
                isMobile={isMobile}
                saveError={saveError}
                onChange={setDraft}
                onSave={handleSave}
                onRevert={handleRevert}
                onCloseMobile={() => setSelectedId(null)}
                onRemove={requestRemoveSelected}
              />
            </div>
          </div>
        )}

        {tab === 'plans' && (
          <ImagePlansPanel
            productId={productId}
            references={references}
            onOpenReferences={() => handleTabChange('references')}
          />
        )}

        {tab === 'images' && (
          <EmptyState
            icon={<Layers className="w-8 h-8" />}
            title="暂无可用图片"
            desc="生成后的图片与历史版本会保存在这里，选择采用版本并导出。"
            action={{
              label: '去查看方案',
              onClick: () => handleTabChange('plans'),
            }}
          />
        )}
      </div>

      {previewUrl && (
        <ImagePreview url={previewUrl} onClose={() => setPreviewUrl(null)} />
      )}

      {showEdit && (
        <ProductInfoDialog
          product={product}
          onClose={() => setShowEdit(false)}
          onSaved={(updated) => {
            setProduct(updated)
            setShowEdit(false)
          }}
        />
      )}

      {showMove && product && (
        <MoveProductDialog
          product={product}
          folders={allFolders}
          onClose={() => setShowMove(false)}
          onMoved={(updated, targetFolder) => {
            setShowMove(false)
            setProduct(updated)
            setFolder(targetFolder)
            navigate(`/folders/${updated.folderId}/products/${updated.id}`, {
              replace: true,
            })
          }}
        />
      )}

      {pendingAction && (
        <ConfirmDialog
          title="存在未保存的修改"
          message="当前参考图的信息已修改但未保存，继续将丢失这些内容。"
          confirmText="保存并继续"
          discardText="放弃修改"
          cancelText="继续编辑"
          onConfirm={async () => {
            await handleSave()
            const act = pendingAction
            setPendingAction(null)
            act()
          }}
          onDiscard={() => {
            const act = pendingAction
            if (draftBase) setDraft({ ...draftBase })
            setPendingAction(null)
            act()
          }}
          onCancel={() => setPendingAction(null)}
        />
      )}
    </div>
  )
}
