import { Navigate, Route, Routes } from 'react-router-dom'
import AppLayout from './components/layout/AppLayout.jsx'
import FolderListPage from './pages/FolderListPage.jsx'
import ProductListPage from './pages/ProductListPage.jsx'
import ProductDetailPage from './pages/ProductDetailPage.jsx'

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<Navigate to="/folders" replace />} />
        <Route path="folders" element={<FolderListPage />} />
        <Route path="folders/:folderId" element={<ProductListPage />} />
        <Route
          path="folders/:folderId/products/:productId"
          element={<ProductDetailPage />}
        />
        <Route path="*" element={<Navigate to="/folders" replace />} />
      </Route>
    </Routes>
  )
}
