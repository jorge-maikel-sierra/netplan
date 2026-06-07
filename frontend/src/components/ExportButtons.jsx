import { useState } from 'react'
import api from '../services/api'
import { getErrorMessage } from '../utils/errorMap'

function triggerBlobDownload(blob, filename) {
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}

export default function ExportButtons({ projectId, projectName, mapRef, onMessage }) {
  const [loading, setLoading] = useState({ excel: false, pdf: false })

  const safeName = (projectName ?? 'proyecto')
    .toLowerCase()
    .replace(/\s+/g, '-')
    .replace(/[^a-z0-9-_]/g, '')

  const onExportExcel = async () => {
    if (!projectId) return
    setLoading((prev) => ({ ...prev, excel: true }))
    onMessage?.(null)

    try {
      const response = await api.get(`/projects/${projectId}/export/excel`, {
        responseType: 'blob',
      })
      triggerBlobDownload(response.data, `${safeName || 'proyecto'}-export.xlsx`)
      onMessage?.('Excel generado y descargado correctamente.')
    } catch (err) {
      const { message } = getErrorMessage(err)
      onMessage?.(message ?? 'Error al generar el archivo Excel. Intentá de nuevo.')
    } finally {
      setLoading((prev) => ({ ...prev, excel: false }))
    }
  }

  const onExportPdf = async () => {
    if (!projectId) return
    setLoading((prev) => ({ ...prev, pdf: true }))
    onMessage?.(null)

    try {
      const mapBase64 = await mapRef?.current?.getMapBase64?.()

      const response = await api.post(
        `/projects/${projectId}/export/pdf`,
        { map_image_base64: mapBase64 ?? '' },
        { responseType: 'blob' }
      )

      triggerBlobDownload(response.data, `${safeName || 'proyecto'}-reporte.pdf`)
      onMessage?.('PDF generado y descargado correctamente.')
    } catch (err) {
      if (err instanceof Error && !err.response) {
        onMessage?.('No se pudo capturar la imagen del mapa. Intentá de nuevo.')
        return
      }
      const { message } = getErrorMessage(err)
      onMessage?.(message ?? 'Error al generar el archivo PDF. Intentá de nuevo.')
    } finally {
      setLoading((prev) => ({ ...prev, pdf: false }))
    }
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
      <button
        type="button"
        onClick={onExportExcel}
        disabled={loading.excel || loading.pdf}
        className="bg-teal-600 text-white px-3 py-2 rounded-md text-sm hover:bg-teal-700 disabled:opacity-50"
      >
        {loading.excel ? 'Descargando Excel...' : 'Descargar Excel'}
      </button>
      <button
        type="button"
        onClick={onExportPdf}
        disabled={loading.pdf || loading.excel}
        className="bg-fuchsia-600 text-white px-3 py-2 rounded-md text-sm hover:bg-fuchsia-700 disabled:opacity-50"
      >
        {loading.pdf ? 'Generando PDF...' : 'Descargar PDF'}
      </button>
    </div>
  )
}
