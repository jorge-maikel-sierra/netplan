import { useRef, useState } from 'react'
import api from '../services/api'
import { getErrorMessage } from '../utils/errorMap'

export default function ImportButton({ projectId, onMessage }) {
  const fileInputRef = useRef(null)
  const [loading, setLoading] = useState(false)

  const handleFileChange = async (event) => {
    const file = event.target.files?.[0]
    if (!file) return

    // Validate file type
    if (!file.name.endsWith('.xlsx')) {
      onMessage?.('Solo se permiten archivos .xlsx')
      return
    }

    if (!projectId) return

    setLoading(true)
    onMessage?.(null)

    try {
      const formData = new FormData()
      formData.append('file', file)

      const response = await api.post(`/projects/${projectId}/nodes/import`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })

      const { imported, skipped } = response.data
      const message = `${imported} importados, ${skipped} omitidos`
      onMessage?.(message)

      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    } catch (err) {
      const { message } = getErrorMessage(err)
      onMessage?.(message ?? 'Error al importar el archivo. Intentá de nuevo.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-2">
      <input
        ref={fileInputRef}
        type="file"
        accept=".xlsx"
        onChange={handleFileChange}
        className="hidden"
        id="import-file-input"
      />
      <button
        type="button"
        onClick={() => fileInputRef.current?.click()}
        disabled={loading}
        className="w-full bg-amber-600 text-white px-3 py-2 rounded-md text-sm hover:bg-amber-700 disabled:opacity-50"
      >
        {loading ? 'Importando...' : 'Importar nodos (.xlsx)'}
      </button>
    </div>
  )
}
