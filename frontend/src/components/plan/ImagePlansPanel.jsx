import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  AlertCircle,
  CheckCircle2,
  ChevronLeft,
  Copy,
  FileText,
  Image as ImageIcon,
  ImagePlus,
  Plus,
  Save,
  Sparkles,
  X,
} from 'lucide-react'
import Button from '../ui/Button.jsx'
import Badge from '../ui/Badge.jsx'
import EmptyState from '../ui/EmptyState.jsx'
import {
  PLAN_ROLE_OPTIONS,
  PRODUCT_RELATION_LABELS,
  AI_STATUS_LABELS,
} from '../../data/constants.js'
import * as api from '../../services/productService.js'

function buildUsageSummary(usage) {
  if (!usage?.length) return ''
  const parts = usage.map((item, idx) => {
    const label = String.fromCharCode(65 + idx)
    const roles = item.roles || []
    const useFor = (item.useFor || '').trim()
    const ignore = (item.ignore || '').trim()
    let phrase
    if (roles.includes('primary')) phrase = `${label}图提供${useFor || '主体外观'}`
    else if (roles.includes('detail')) phrase = `${label}图补充${useFor || '细节'}`
    else if (roles.includes('composition')) phrase = `${label}图只参考构图`
    else if (roles.includes('style')) phrase = `${label}图参考视觉风格`
    else if (roles.includes('usage')) phrase = `${label}图参考安装与使用`
    else if (useFor) phrase = `${label}图${useFor}`
    else phrase = `${label}图作参考`
    if (ignore) phrase = `${phrase}，忽略${ignore}`
    return phrase
  })
  return `${parts.join('；')}。`
}

function isRiskyRef(ref) {
  return (
    ref.productRelation === 'other_product' ||
    ref.productRelation === 'unknown' ||
    ref.aiStatus === 'yes'
  )
}

const ROLE_SUGGESTIONS = {
  primary: { useFor: '整体外观轮廓与比例', ignore: '背景、文字和促销元素' },
  detail: { useFor: '接口与关键部位形状', ignore: '背景与其他配件' },
  usage: { useFor: '安装位置与朝向关系', ignore: '无关环境' },
  composition: { useFor: '构图位置与角度', ignore: '其中的商品、文字和 Logo' },
  style: { useFor: '背景光线与氛围', ignore: '具体商品细节' },
}

const FAMILY_OPTIONS = [
  { value: 'main', label: '主图 main', enabled: true },
  { value: 'wear', label: '穿搭 wear', enabled: false },
  { value: 'handheld', label: '手持 handheld', enabled: false },
  { value: 'scene', label: '场景 scene', enabled: false },
  { value: 'texture', label: '质感 texture', enabled: false },
  { value: 'compare', label: '对比 compare', enabled: false },
]

function PlanEditor({
  productId,
  references,
  plan,
  isNew,
  onBack,
  onSaved,
  readOnly,
}) {
  const [name, setName] = useState(plan?.name || '主图方案 1')
  const [family, setFamily] = useState(plan?.family || 'main')
  const [drawingRequest, setDrawingRequest] = useState(plan?.drawingRequest || '')
  const [prompt, setPrompt] = useState(plan?.prompt || '')
  const [designNotes, setDesignNotes] = useState(plan?.designNotes || '')
  const [openQuestions, setOpenQuestions] = useState(plan?.openQuestions || [])
  const [usage, setUsage] = useState(plan?.referenceUsage || [])
  const [saveError, setSaveError] = useState('')
  const [notice, setNotice] = useState('')
  const [saving, setSaving] = useState(false)
  const [running, setRunning] = useState(false)
  const [adopting, setAdopting] = useState(false)
  const [runResult, setRunResult] = useState(null)
  const [currentPlanId, setCurrentPlanId] = useState(plan?.id || null)

  useEffect(() => {
    if (plan) {
      setName(plan.name || '主图方案 1')
      setFamily(plan.family || 'main')
      setDrawingRequest(plan.drawingRequest || '')
      setPrompt(plan.prompt || '')
      setDesignNotes(plan.designNotes || '')
      setOpenQuestions(plan.openQuestions || [])
      setUsage(plan.referenceUsage || [])
      setCurrentPlanId(plan.id)
    }
  }, [plan])

  const refById = useMemo(
    () => Object.fromEntries(references.map((r) => [r.id, r])),
    [references],
  )

  const summary = useMemo(() => buildUsageSummary(usage), [usage])

  const toggleSelect = (refId) => {
    if (readOnly) return
    setUsage((prev) => {
      if (prev.some((u) => u.refImageId === refId)) {
        return prev.filter((u) => u.refImageId !== refId)
      }
      return [...prev, { refImageId: refId, roles: [], useFor: '', ignore: '' }]
    })
  }

  const toggleRole = (refId, role) => {
    if (readOnly) return
    const wasOn = hasRole(refId, role)
    setUsage((prev) => {
      let next = prev.map((u) => {
        if (u.refImageId !== refId) return u
        const roles = wasOn
          ? u.roles.filter((r) => r !== role)
          : [...u.roles.filter((r) => !(role === 'primary' && r === 'primary')), role]
        return { ...u, roles }
      })
      if (!wasOn && role === 'primary') {
        next = next.map((u) =>
          u.refImageId === refId ? u : { ...u, roles: u.roles.filter((r) => r !== 'primary') },
        )
      }
      return next
    })
    if (!wasOn && ROLE_SUGGESTIONS[role]) {
      setUsage((prev) =>
        prev.map((u) => {
          if (u.refImageId !== refId) return u
          const sug = ROLE_SUGGESTIONS[role]
          return {
            ...u,
            useFor: u.useFor || sug.useFor,
            ignore: u.ignore || sug.ignore,
          }
        }),
      )
      const ref = refById[refId]
      if (ref && isRiskyRef(ref) && ['primary', 'detail', 'usage'].includes(role)) {
        setNotice(
          '该图不是「同款同规格」或经过/可能经过 AI 处理，选作主体、细节或安装依据时请核对具体参考范围。',
        )
      }
    }
  }

  const hasRole = (refId, role) => {
    const item = usage.find((u) => u.refImageId === refId)
    return Boolean(item?.roles?.includes(role))
  }

  const updateItem = (refId, patch) => {
    if (readOnly) return
    setUsage((prev) =>
      prev.map((u) => (u.refImageId === refId ? { ...u, ...patch } : u)),
    )
  }

  const moveItem = (refId, dir) => {
    if (readOnly) return
    setUsage((prev) => {
      const idx = prev.findIndex((u) => u.refImageId === refId)
      const next = idx + dir
      if (idx < 0 || next < 0 || next >= prev.length) return prev
      const copy = [...prev]
      const [item] = copy.splice(idx, 1)
      copy.splice(next, 0, item)
      return copy
    })
  }

  const saveDraft = async () => {
    const body = {
      name: name.trim() || '主图方案 1',
      family,
      imageUsage: plan?.imageUsage || '商品主图',
      drawingRequest,
      prompt,
      referenceUsage: usage,
      refImageIds: usage.map((u) => u.refImageId),
    }
    return isNew
      ? api.createPlan(productId, body)
      : api.updatePlan(plan.id, body)
  }

  const handleSave = async () => {
    setSaving(true)
    setSaveError('')
    try {
      const saved = await saveDraft()
      setCurrentPlanId(saved.id)
      onSaved(saved)
    } catch (e) {
      setSaveError(e.message || '保存失败，输入已保留')
    } finally {
      setSaving(false)
    }
  }

  const handleSkillRun = async () => {
    setSaveError('')
    setRunning(true)
    try {
      // 先保存草稿，保证本次运行包含未保存的角色/顺序修改
      const saved = await saveDraft()
      setCurrentPlanId(saved.id)
      const run = await api.skillRunPlan(saved.id)
      setRunResult(run)
      if (run.status === 'failed') {
        setSaveError(run.error || 'AI 生成失败，草稿未改动')
      }
    } catch (e) {
      setSaveError(e.message || 'AI 生成失败，草稿未改动')
    } finally {
      setRunning(false)
    }
  }

  const handleAdopt = async () => {
    if (!runResult || runResult.status !== 'success' || !currentPlanId) return
    setAdopting(true)
    setSaveError('')
    try {
      const saved = await api.adoptPlanRun(currentPlanId, runResult.id)
      setPrompt(saved.prompt)
      setDesignNotes(saved.designNotes || '')
      setOpenQuestions(saved.openQuestions || [])
      setRunResult((prev) => (prev ? { ...prev, adoptedAt: new Date().toISOString() } : prev))
      setNotice('已采纳到草稿，可继续手工修改后再确认。')
    } catch (e) {
      setSaveError(e.message || '采纳失败')
    } finally {
      setAdopting(false)
    }
  }

  const handleConfirm = async () => {
    setSaveError('')
    const incomplete = usage.filter((u) => !u.roles?.length)
    if (incomplete.length) {
      setSaveError('请先为选中的图片补齐角色，再确认方案。')
      return
    }
    setSaving(true)
    try {
      const saved = await saveDraft()
      const confirmed = await api.confirmPlan(saved.id)
      onSaved(confirmed)
    } catch (e) {
      setSaveError(e.message || '确认失败，输入已保留')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="flex items-center justify-between border-b border-[var(--border-whisper)] bg-[var(--bg-surface)] px-4 py-3">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onBack}
            className="p-1 text-[var(--text-3)] hover:text-[var(--text-1)]"
            aria-label="返回列表"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <h3 className="m-0 text-[13px] font-semibold text-[var(--text-1)]">
            {readOnly ? '查看已确认方案' : isNew ? '新建方案' : '编辑方案'}
          </h3>
          {plan?.status === 'confirmed' && <Badge type="success">已确认</Badge>}
          {plan?.status === 'draft' && !isNew && <Badge>草稿</Badge>}
        </div>
        {!readOnly && (
          <div className="flex gap-2">
            <Button size="sm" variant="secondary" onClick={onBack}>
              取消修改
            </Button>
            <Button size="sm" variant="secondary" onClick={handleSave} loading={saving}>
              <Save className="w-3.5 h-3.5" />
              保存草稿
            </Button>
            <Button size="sm" variant="secondary" onClick={handleSkillRun} loading={running}>
              <Sparkles className="w-3.5 h-3.5" />
              AI 生成方案
            </Button>
            <Button size="sm" onClick={handleConfirm} loading={saving}>
              <CheckCircle2 className="w-3.5 h-3.5" />
              确认方案
            </Button>
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {notice && (
          <div className="mb-3 flex items-start gap-2 rounded-[var(--radius-sm)] border border-[color-mix(in_srgb,var(--warning)_25%,transparent)] bg-[var(--warning-soft)] p-2.5">
            <AlertCircle className="mt-0.5 w-3.5 h-3.5 shrink-0 text-[var(--warning)]" />
            <p className="m-0 flex-1 text-[11.5px] text-[var(--warning)]">{notice}</p>
            <button type="button" onClick={() => setNotice('')} aria-label="关闭提示">
              <X className="w-3.5 h-3.5 text-[var(--warning)]" />
            </button>
          </div>
        )}

        <div className="mb-3 grid grid-cols-1 gap-3 md:grid-cols-2">
          <div>
            <label className="mb-1 block text-[12.5px] font-semibold text-[var(--text-1)]">
              方案名称
            </label>
            <input
              className="field-input"
              value={name}
              disabled={readOnly}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div>
            <label className="mb-1 block text-[12.5px] font-semibold text-[var(--text-1)]">
              方案族 family
            </label>
            <select
              className="field-input"
              value={family}
              disabled={readOnly}
              onChange={(e) => setFamily(e.target.value)}
            >
              {FAMILY_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value} disabled={!opt.enabled}>
                  {opt.label}
                  {opt.enabled ? '' : '（待实现）'}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="mb-3 grid grid-cols-1 gap-3 md:grid-cols-2">
          <div>
            <label className="mb-1 block text-[12.5px] font-semibold text-[var(--text-1)]">
              制图要求
            </label>
            <textarea
              className="field-input min-h-[64px] h-auto py-2 text-[12.5px] resize-y"
              value={drawingRequest}
              disabled={readOnly}
              onChange={(e) => setDrawingRequest(e.target.value)}
              placeholder="例如：简洁背景，完整展示商品"
            />
          </div>
          <div>
            <label className="mb-1 block text-[12.5px] font-semibold text-[var(--text-1)]">
              生图提示词
            </label>
            <textarea
              className="field-input min-h-[64px] h-auto py-2 text-[12.5px] resize-y"
              value={prompt}
              disabled={readOnly}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="多行文本，手工填写本轮测试"
            />
          </div>
        </div>

        <div className="mb-2 flex items-center justify-between">
          <h4 className="m-0 text-[12.5px] font-semibold text-[var(--text-1)]">
            使用的参考图
            <span className="ml-1.5 font-normal text-[var(--text-3)] tabular-nums">
              {usage.length}
            </span>
          </h4>
          <p className="m-0 text-[11px] text-[var(--text-3)]">
            勾选顺序即本次使用顺序；最多一张「主体依据」
          </p>
        </div>

        {references.length === 0 && (
          <EmptyState
            icon={<ImagePlus className="w-8 h-8" />}
            title="还没有参考图"
            desc="先在「资料与参考图」上传，再回到方案里选用。"
          />
        )}

        <div className="space-y-2">
          {references.map((ref) => {
            const item = usage.find((u) => u.refImageId === ref.id)
            const selected = Boolean(item)
            return (
              <div
                key={ref.id}
                className={`rounded-[var(--radius-md)] border p-2.5 ${
                  selected
                    ? 'border-[var(--accent)] bg-[var(--accent-soft)]'
                    : 'border-[var(--border-whisper)]'
                }`}
              >
                <div className="flex items-start gap-2.5">
                  {!readOnly && (
                    <input
                      type="checkbox"
                      checked={selected}
                      onChange={() => toggleSelect(ref.id)}
                      className="mt-1 accent-[var(--accent)]"
                      aria-label={`选择参考图 ${ref.id}`}
                    />
                  )}
                  <img
                    src={ref.url}
                    alt=""
                    className="h-14 w-14 rounded-[var(--radius-sm)] bg-[var(--bg-subtle)] object-contain"
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span className="text-[11.5px] font-medium text-[var(--text-1)]">
                        {PRODUCT_RELATION_LABELS[ref.productRelation] ||
                          ref.productRelation ||
                          '不确定'}
                      </span>
                      <span className="text-[11px] text-[var(--text-3)]">
                        · {AI_STATUS_LABELS[ref.aiStatus] || ref.aiStatus || '不确定'}
                      </span>
                      {selected && (
                        <span className="ml-auto text-[11px] text-[var(--text-3)]">
                          使用序 {usage.findIndex((u) => u.refImageId === ref.id) + 1}
                        </span>
                      )}
                    </div>
                    <p className="m-0 mt-0.5 truncate text-[11px] text-[var(--text-3)]">
                      {ref.desc || '无备注'}
                    </p>
                  </div>
                  {selected && !readOnly && (
                    <div className="flex flex-col gap-0.5">
                      <button
                        type="button"
                        className="text-[10px] text-[var(--text-3)] hover:text-[var(--text-1)]"
                        onClick={() => moveItem(ref.id, -1)}
                      >
                        ↑
                      </button>
                      <button
                        type="button"
                        className="text-[10px] text-[var(--text-3)] hover:text-[var(--text-1)]"
                        onClick={() => moveItem(ref.id, 1)}
                      >
                        ↓
                      </button>
                    </div>
                  )}
                </div>

                {selected && (
                  <div className="mt-2.5 border-t border-[var(--border-whisper)] pt-2.5">
                    <div className="mb-2 flex flex-wrap gap-1.5">
                      {PLAN_ROLE_OPTIONS.map((role) => {
                        const checked = item.roles?.includes(role.value)
                        return (
                          <label
                            key={role.value}
                            className={`flex cursor-pointer items-center rounded-[var(--radius-xs)] border px-2 py-1 text-[11px] ${
                              checked
                                ? 'border-[var(--accent)] bg-white text-[var(--accent-text)] font-medium'
                                : 'border-[var(--border-whisper)] text-[var(--text-2)]'
                            }`}
                          >
                            <input
                              type="checkbox"
                              checked={checked}
                              disabled={readOnly}
                              onChange={() => toggleRole(ref.id, role.value)}
                              className="mr-1 accent-[var(--accent)]"
                            />
                            {role.label}
                          </label>
                        )
                      })}
                    </div>
                    <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                      <div>
                        <label className="mb-0.5 block text-[11px] text-[var(--text-3)]">
                          参考什么
                        </label>
                        <input
                          className="field-input text-[12px]"
                          value={item.useFor}
                          disabled={readOnly}
                          onChange={(e) =>
                            updateItem(ref.id, { useFor: e.target.value })
                          }
                          placeholder="例如：只参考接口形状"
                        />
                      </div>
                      <div>
                        <label className="mb-0.5 block text-[11px] text-[var(--text-3)]">
                          忽略什么
                        </label>
                        <input
                          className="field-input text-[12px]"
                          value={item.ignore}
                          disabled={readOnly}
                          onChange={(e) =>
                            updateItem(ref.id, { ignore: e.target.value })
                          }
                          placeholder="例如：忽略背景、促销文案"
                        />
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>

        <div className="mt-4 rounded-[var(--radius-md)] border border-[var(--border-whisper)] bg-[var(--bg-surface)] p-3">
          <div className="mb-1.5 flex items-center gap-1.5">
            <FileText className="w-3.5 h-3.5 text-[var(--text-3)]" />
            <h4 className="m-0 text-[12px] font-semibold text-[var(--text-1)]">
              本次参考说明
            </h4>
          </div>
          <p className="m-0 text-[12px] leading-relaxed text-[var(--text-2)]">
            {summary || '选中参考图并配置角色后，这里会生成可读的参考指令。'}
          </p>
        </div>

        {(runResult || designNotes || (openQuestions?.length > 0)) && (
          <div className="mt-4 rounded-[var(--radius-md)] border border-[var(--border-whisper)] bg-[var(--bg-surface)] p-3">
            <div className="mb-2 flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-[var(--accent)]" />
                <h4 className="m-0 text-[12px] font-semibold text-[var(--text-1)]">
                  AI 生成结果
                </h4>
                {runResult && (
                  <Badge type={runResult.status === 'success' ? 'success' : 'error'}>
                    {runResult.status === 'success' ? '成功' : '失败'}
                  </Badge>
                )}
              </div>
              {!readOnly && runResult?.status === 'success' && !runResult.adoptedAt && (
                <Button size="sm" onClick={handleAdopt} loading={adopting}>
                  采纳到草稿
                </Button>
              )}
            </div>

            {runResult?.status === 'failed' && (
              <p role="alert" className="field-error m-0 mb-2">
                {runResult.error || '生成失败'}
              </p>
            )}

            {(() => {
              const questions =
                runResult?.openQuestions?.length > 0
                  ? runResult.openQuestions
                  : openQuestions || []
              const notes = runResult?.designNotes || designNotes
              return (
                <>
                  {questions.length > 0 && (
                    <div className="mb-2 rounded-[var(--radius-sm)] border border-[color-mix(in_srgb,var(--warning)_25%,transparent)] bg-[var(--warning-soft)] p-2.5">
                      <div className="flex items-start gap-2">
                        <AlertCircle className="mt-0.5 w-3.5 h-3.5 shrink-0 text-[var(--warning)]" />
                        <div className="flex-1">
                          <p className="m-0 text-[11.5px] font-semibold text-[var(--warning)]">
                            待确认问题（不阻断采纳）
                          </p>
                          <ul className="m-0 mt-1 list-disc pl-4 text-[11.5px] text-[var(--warning)]">
                            {questions.map((q, i) => (
                              <li key={i}>{q}</li>
                            ))}
                          </ul>
                        </div>
                      </div>
                    </div>
                  )}

                  {notes && (
                    <div className="mb-2">
                      <p className="m-0 mb-0.5 text-[11px] font-semibold text-[var(--text-3)]">
                        设计说明
                      </p>
                      <p className="m-0 whitespace-pre-wrap text-[12px] leading-relaxed text-[var(--text-2)]">
                        {notes}
                      </p>
                    </div>
                  )}
                </>
              )
            })()}

            {runResult?.refUsageNotes && (
              <div className="mb-2">
                <p className="m-0 mb-0.5 text-[11px] font-semibold text-[var(--text-3)]">
                  参考图使用说明
                </p>
                <p className="m-0 whitespace-pre-wrap text-[12px] leading-relaxed text-[var(--text-2)]">
                  {runResult.refUsageNotes}
                </p>
              </div>
            )}

            {runResult?.generatedPrompt && (
              <div>
                <p className="m-0 mb-0.5 text-[11px] font-semibold text-[var(--text-3)]">
                  生成的提示词
                </p>
                <p className="m-0 whitespace-pre-wrap rounded-[var(--radius-sm)] bg-[var(--bg-subtle)] p-2 text-[12px] leading-relaxed text-[var(--text-2)]">
                  {runResult.generatedPrompt}
                </p>
              </div>
            )}
          </div>
        )}

        {saveError && (
          <p role="alert" className="field-error mt-3">
            {saveError}
          </p>
        )}
      </div>
    </div>
  )
}

export default function ImagePlansPanel({ productId, references, onOpenReferences }) {
  const [plans, setPlans] = useState([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(null) // null | {mode:'new'} | {mode:'edit', plan} | {mode:'view', plan}
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const list = await api.listPlans(productId)
      setPlans(list)
    } catch (e) {
      setError(e.message || '加载失败')
    } finally {
      setLoading(false)
    }
  }, [productId])

  useEffect(() => {
    load()
  }, [load])

  if (editing) {
    return (
      <PlanEditor
        productId={productId}
        references={references}
        plan={editing.plan}
        isNew={editing.mode === 'new'}
        readOnly={editing.mode === 'view'}
        onBack={() => setEditing(null)}
        onSaved={() => {
          setEditing(null)
          load()
        }}
      />
    )
  }

  const handleCopyFrom = async (sourcePlan) => {
    setError('')
    try {
      const created = await api.createPlanFrom(productId, sourcePlan)
      setEditing({ mode: 'edit', plan: created })
      load()
    } catch (e) {
      setError(e.message || '复制失败')
    }
  }

  return (
    <div className="h-full overflow-y-auto p-5 lg:p-6">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="m-0 text-[12.5px] font-semibold text-[var(--text-2)]">
          图片方案
          <span className="ml-1.5 font-normal text-[var(--text-3)] tabular-nums">
            {plans.length}
          </span>
        </h2>
        <Button size="sm" onClick={() => setEditing({ mode: 'new' })}>
          <Plus className="w-3.5 h-3.5" />
          新建方案
        </Button>
      </div>

      {error && (
        <p role="alert" className="field-error mb-3">
          {error}
        </p>
      )}

      {loading ? (
        <p className="text-[12px] text-[var(--text-3)]">加载中…</p>
      ) : plans.length === 0 ? (
        <EmptyState
          icon={<ImageIcon className="w-8 h-8" />}
          title="还没有图片方案"
          desc="新建方案，选用参考图并配置本次角色。"
          action={{
            label: '新建方案',
            onClick: () => setEditing({ mode: 'new' }),
          }}
        />
      ) : (
        <ul className="m-0 list-none space-y-2 p-0">
          {plans.map((plan) => (
            <li key={plan.id} className="flex items-stretch gap-2">
              <button
                type="button"
                onClick={() =>
                  setEditing(
                    plan.status === 'confirmed'
                      ? { mode: 'view', plan }
                      : { mode: 'edit', plan },
                  )
                }
                className="flex flex-1 items-center justify-between rounded-[var(--radius-md)] border border-[var(--border-whisper)] bg-[var(--bg-raised)] px-3.5 py-3 text-left hover:border-[var(--border-quiet)]"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-[13px] font-medium text-[var(--text-1)]">
                      {plan.name}
                    </span>
                    <Badge>{plan.family || 'main'}</Badge>
                    {plan.status === 'confirmed' ? (
                      <Badge type="success">已确认</Badge>
                    ) : (
                      <Badge>草稿</Badge>
                    )}
                    {plan.basedOnPlanId && <Badge>副本</Badge>}
                  </div>
                  <p className="m-0 mt-0.5 text-[11px] text-[var(--text-3)]">
                    {plan.refImageIds?.length || 0} 张参考图
                    {plan.usageSummary ? ` · ${plan.usageSummary}` : ''}
                  </p>
                </div>
                <span className="text-[11px] text-[var(--text-3)]">
                  {plan.status === 'confirmed' ? '查看' : '继续编辑'}
                </span>
              </button>
              {plan.status === 'confirmed' && (
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => handleCopyFrom(plan)}
                  title="基于此方案再生成新草稿"
                >
                  <Copy className="w-3.5 h-3.5" />
                  复制草稿
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
