import { useEffect, useMemo, useRef } from 'react'
import L from 'leaflet'

const NODE_TYPE_COLORS = {
  city: {
    stroke: '#1d4ed8',
    fill: '#3b82f6',
  },
  tower: {
    stroke: '#0f766e',
    fill: '#14b8a6',
  },
  datacenter: {
    stroke: '#7c3aed',
    fill: '#8b5cf6',
  },
}

const SELECTED_STYLE = {
  stroke: '#f59e0b',
  fill: '#fbbf24',
}

function resolveNodeStyle(type, isSelected) {
  if (isSelected) return SELECTED_STYLE
  return NODE_TYPE_COLORS[type] ?? NODE_TYPE_COLORS.city
}

function createNodeIcon(style) {
  return L.divIcon({
    className: 'netplan-node-marker-icon',
    html: `<span style="display:block;width:14px;height:14px;border-radius:9999px;background:${style.fill};border:2px solid ${style.stroke};box-sizing:border-box;"></span>`,
    iconSize: [14, 14],
    iconAnchor: [7, 7],
    popupAnchor: [0, -7],
  })
}

export default function NodeMarkers({
  map,
  nodes,
  selectedNodeId,
  onNodeClick,
  onNodeDragStart,
  onNodeDragCancel,
  onNodeDragSave,
}) {
  const layerRef = useRef(null)
  const pendingByNodeRef = useRef({})

  const normalizedNodes = useMemo(
    () =>
      (nodes ?? [])
        .map((node) => ({
          ...node,
          lat: Number(node.lat),
          lng: Number(node.lng),
        }))
        .filter((node) => Number.isFinite(node.lat) && Number.isFinite(node.lng)),
    [nodes]
  )

  useEffect(() => {
    if (!map) return

    const layer = L.layerGroup().addTo(map)
    layerRef.current = layer

    return () => {
      map.removeLayer(layer)
      layerRef.current = null
    }
  }, [map])

  useEffect(() => {
    const layer = layerRef.current
    if (!layer) return

    layer.clearLayers()

    normalizedNodes.forEach((node) => {
      const isSelected = selectedNodeId === node.id
      const style = resolveNodeStyle(node.type, isSelected)

      const marker = L.marker([node.lat, node.lng], {
        draggable: true,
        icon: createNodeIcon(style),
      })
      marker.setZIndexOffset(isSelected ? 1000 : 0)

      const renderPopup = (pending = null) => {
        const displayLat = pending?.lat ?? node.lat
        const displayLng = pending?.lng ?? node.lng

        return `
          <div class="space-y-1 min-w-[180px]">
            <strong>${node.name ?? 'Nodo'}</strong><br/>
            <span>Tipo: ${node.type ?? 'city'}</span><br/>
            <span>Lat: ${Number(displayLat).toFixed(6)}</span><br/>
            <span>Lng: ${Number(displayLng).toFixed(6)}</span><br/>
            ${
              pending
                ? '<div class="mt-2 flex gap-2"><button type="button" data-action="save" class="rounded bg-blue-600 px-2 py-1 text-xs text-white">Guardar</button><button type="button" data-action="cancel" class="rounded bg-gray-200 px-2 py-1 text-xs">Cancelar</button></div>'
                : ''
            }
          </div>
        `
      }

      marker.bindPopup(renderPopup())

      marker.on('click', () => {
        onNodeClick?.(node.id)
      })

      marker.on('dragstart', () => {
        onNodeDragStart?.(node.id)
      })

      marker.on('dragend', () => {
        const { lat, lng } = marker.getLatLng()
        const nextPending = {
          lat: Number(lat.toFixed(6)),
          lng: Number(lng.toFixed(6)),
        }
        pendingByNodeRef.current[node.id] = nextPending
        marker.setPopupContent(renderPopup(nextPending))
        marker.openPopup()
      })

      marker.on('popupopen', (event) => {
        const popupElement = event?.popup?._contentNode
        if (!popupElement) return

        const saveButton = popupElement.querySelector('[data-action="save"]')
        const cancelButton = popupElement.querySelector('[data-action="cancel"]')

        if (saveButton) {
          saveButton.onclick = async () => {
            const pending = pendingByNodeRef.current[node.id]
            if (!pending) return
            try {
              await onNodeDragSave?.(node.id, pending)
              delete pendingByNodeRef.current[node.id]
              marker.setPopupContent(renderPopup())
              marker.openPopup()
            } catch {
              marker.setLatLng([node.lat, node.lng])
              delete pendingByNodeRef.current[node.id]
              marker.setPopupContent(renderPopup())
              marker.openPopup()
            }
          }
        }

        if (cancelButton) {
          cancelButton.onclick = () => {
            delete pendingByNodeRef.current[node.id]
            marker.setLatLng([node.lat, node.lng])
            marker.setPopupContent(renderPopup())
            marker.openPopup()
            onNodeDragCancel?.(node.id)
          }
        }
      })

      marker.addTo(layer)
    })
  }, [
    normalizedNodes,
    onNodeClick,
    selectedNodeId,
    onNodeDragStart,
    onNodeDragCancel,
    onNodeDragSave,
  ])

  return null
}
