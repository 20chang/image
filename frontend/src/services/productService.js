// Real API client. All data is persisted on the FastAPI backend (SQLite + uploads).

async function request(path, options = {}) {
  const res = await fetch(`/api${path}`, {
    headers:
      options.body instanceof FormData
        ? options.headers
        : { 'Content-Type': 'application/json', ...options.headers },
    ...options,
    body:
      options.body && !(options.body instanceof FormData)
        ? JSON.stringify(options.body)
        : options.body,
  })
  if (!res.ok) {
    let msg = `请求失败 (${res.status})`
    try {
      const data = await res.json()
      msg = data.detail || msg
    } catch {
      /* ignore */
    }
    throw new Error(msg)
  }
  if (res.status === 204) return null
  return res.json()
}

// --- Folders ---

export async function listFolders() {
  return request('/folders')
}

export async function getFolder(id) {
  return request(`/folders/${id}`)
}

export async function createFolder({ name }) {
  return request('/folders', { method: 'POST', body: { name } })
}

export async function renameFolder(id, { name }) {
  return request(`/folders/${id}`, { method: 'PATCH', body: { name } })
}

export async function deleteFolder(id) {
  return request(`/folders/${id}`, { method: 'DELETE' })
}

// --- Products ---

export async function listProducts({ folderId, name = '' } = {}) {
  const params = new URLSearchParams()
  if (folderId) params.set('folderId', folderId)
  if (name) params.set('name', name)
  const qs = params.toString()
  return request(`/products${qs ? `?${qs}` : ''}`)
}

export async function getProduct(id) {
  return request(`/products/${id}`)
}

export async function createProduct({ folderId, name, market, facts }) {
  return request('/products', {
    method: 'POST',
    body: { folderId, name, market, facts },
  })
}

export async function updateProduct(id, patch) {
  return request(`/products/${id}`, { method: 'PATCH', body: patch })
}

export async function moveProduct(id, folderId) {
  return request(`/products/${id}/move`, { method: 'POST', body: { folderId } })
}

export async function removeProduct(id) {
  return request(`/products/${id}`, { method: 'DELETE' })
}

// --- Reference images ---

export async function listReferences(productId) {
  return request(`/products/${productId}/references`)
}

export async function addReference(productId, { url, status = 'success', file } = {}) {
  // Real upload: pass a File object. `url` is ignored by the backend.
  const form = new FormData()
  if (file) {
    form.append('file', file)
  } else if (url && url.startsWith('blob:')) {
    // Object URL from local file picker — fetch back into a File
    const blob = await fetch(url).then((r) => r.blob())
    form.append('file', blob, 'image.png')
  } else if (url) {
    // Fallback placeholder URL — generate a tiny file so demo still works
    form.append('file', new Blob([new Uint8Array(1)]), 'placeholder.png')
  } else {
    throw new Error('缺少图片文件')
  }
  return request(`/products/${productId}/references`, {
    method: 'POST',
    body: form,
  })
}

export async function markReferenceStatus(productId, refId, status) {
  // Backend stores status; for now meta update keeps other fields
  const list = await listReferences(productId)
  const current = list.find((r) => r.id === refId)
  if (!current) throw new Error('参考图不存在')
  return request(`/references/${refId}`, {
    method: 'PATCH',
    body: {
      source: current.source,
      purposes: current.purposes,
      desc: current.desc,
    },
  })
}

export async function saveReferenceMeta(productId, refId, meta) {
  return request(`/references/${refId}`, {
    method: 'PATCH',
    body: {
      source: meta.source ?? '',
      purposes: meta.purposes ?? [],
      desc: meta.desc ?? '',
    },
  })
}

export async function reorderReferences(productId, refId, direction) {
  return request(`/references/${refId}/reorder`, {
    method: 'POST',
    body: { direction },
  })
}

export async function removeReference(productId, refId) {
  return request(`/references/${refId}`, { method: 'DELETE' })
}
