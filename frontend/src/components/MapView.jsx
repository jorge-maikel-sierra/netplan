import { forwardRef, useEffect, useImperativeHandle, useMemo, useRef, useState } from 'react'
import L from 'leaflet'
import html2canvas from 'html2canvas'
import 'leaflet/dist/leaflet.css'
import NodeMarkers from './NodeMarkers'
import EdgeLines from './EdgeLines'

const DEFAULT_CENTER = [-34.6037, -58.3816]
const DEFAULT_ZOOM = 4
function isValidCoordinate(lat, lng) {
  return Number.isFinite(lat) && Number.isFinite(lng)
}

function normalizeNode(node) {
  return {
    ...node,
    lat: Number(node.lat),
    lng: Number(node.lng),
  }
}

const MapView = forwardRef(function MapView(
  {
    nodes,
    edges,
    mstResult,
    onMapClick,
    selectedNodeId,
    selectedEdgeId,
    onNodeClick,
    onEdgeClick,
    onNodeDragStart,
    onNodeDragCancel,
    onNodeDragSave,
  },
  ref
) {
  const containerRef = useRef(null)
  const mapRef = useRef(null)
  const onMapClickRef = useRef(onMapClick)
  const [mapInstance, setMapInstance] = useState(null)

  const normalizedNodes = useMemo(
    () => (nodes ?? []).map(normalizeNode).filter((node) => isValidCoordinate(node.lat, node.lng)),
    [nodes]
  )

  useEffect(() => {
    onMapClickRef.current = onMapClick
  }, [onMapClick])

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    const map = L.map(containerRef.current).setView(DEFAULT_CENTER, DEFAULT_ZOOM)
    mapRef.current = map
    setMapInstance(map)

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap contributors',
      crossOrigin: 'anonymous',
    }).addTo(map)

    map.on('click', (event) => onMapClickRef.current?.(event.latlng))

    return () => {
      map.remove()
      mapRef.current = null
      setMapInstance(null)
    }
  }, [])

  useEffect(() => {
    const map = mapRef.current
    if (!map) return

    if (normalizedNodes.length > 0) {
      const bounds = L.latLngBounds(normalizedNodes.map((node) => [node.lat, node.lng]))
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 15 })
    } else {
      map.setView(DEFAULT_CENTER, DEFAULT_ZOOM)
    }
  }, [normalizedNodes])

  useImperativeHandle(
    ref,
    () => ({
      getMapBase64: async () => {
        const mapContainer = containerRef.current
        if (!mapContainer) {
          throw new Error('Mapa no disponible para exportar')
        }

        try {
          // Wait for map tiles to load
          await new Promise((resolve) => setTimeout(resolve, 500))

          // Capture the map container with html2canvas
          const canvas = await html2canvas(mapContainer, {
            useCORS: true,
            allowTaint: true,
            foreignObjectRendering: true,
            scale: 1,
            logging: false,
            removeContainer: false,
          })

          const dataUrl = canvas.toDataURL('image/png')
          const [, base64 = ''] = dataUrl.split(',')
          return base64
        } catch (error) {
          console.error('Error capturing map:', error)
          throw new Error('No se pudo capturar el mapa')
        }
      },
    }),
    []
  )

  return (
    <>
      <div ref={containerRef} className="h-full min-h-[420px] w-full rounded-lg" />

      <NodeMarkers
        map={mapInstance}
        nodes={nodes}
        selectedNodeId={selectedNodeId}
        onNodeClick={onNodeClick}
        onNodeDragStart={onNodeDragStart}
        onNodeDragCancel={onNodeDragCancel}
        onNodeDragSave={onNodeDragSave}
      />

      <EdgeLines
        map={mapInstance}
        nodes={nodes}
        edges={edges}
        mstResult={mstResult}
        selectedEdgeId={selectedEdgeId}
        onEdgeClick={onEdgeClick}
      />
    </>
  )
})

export default MapView
