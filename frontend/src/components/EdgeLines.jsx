import { useEffect, useMemo, useRef } from 'react'
import L from 'leaflet'

const MST_COLOR = '#06b6d4'
const SELECTED_COLOR = '#f59e0b'

function getConstraintColor(constraintType) {
  if (constraintType === 'mandatory') return '#2563eb'
  if (constraintType === 'forbidden') return '#dc2626'
  return '#16a34a'
}

function extractMstEdgeIds(mstResult) {
  if (!mstResult) return new Set()

  if (Array.isArray(mstResult.edge_ids)) {
    return new Set(mstResult.edge_ids)
  }

  if (Array.isArray(mstResult.mst_edges)) {
    return new Set(
      mstResult.mst_edges
        .map((edge) => edge.edge_id ?? edge.id)
        .filter((id) => id !== undefined && id !== null)
    )
  }

  return new Set()
}

export default function EdgeLines({
  map,
  edges,
  nodes,
  mstResult,
  selectedEdgeId,
  onEdgeClick,
}) {
  const layerRef = useRef(null)

  const nodesById = useMemo(() => {
    const normalized = (nodes ?? []).map((node) => ({
      ...node,
      lat: Number(node.lat),
      lng: Number(node.lng),
    }))
    return new Map(normalized.map((node) => [node.id, node]))
  }, [nodes])

  const mstEdgeIds = useMemo(() => extractMstEdgeIds(mstResult), [mstResult])

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

    ;(edges ?? []).forEach((edge) => {
      const nodeA = nodesById.get(edge.node_a_id)
      const nodeB = nodesById.get(edge.node_b_id)
      if (!nodeA || !nodeB) return

      const isSelected = edge.id === selectedEdgeId
      const isMstEdge = mstEdgeIds.has(edge.id)

      const line = L.polyline(
        [
          [nodeA.lat, nodeA.lng],
          [nodeB.lat, nodeB.lng],
        ],
        {
          color: isSelected ? SELECTED_COLOR : isMstEdge ? MST_COLOR : getConstraintColor(edge.constraint_type),
          weight: isSelected ? 6 : isMstEdge ? 5 : 3,
          opacity: 0.85,
        }
      )

      line.on('click', () => onEdgeClick?.(edge.id))
      line.addTo(layer)
    })
  }, [edges, mstEdgeIds, nodesById, onEdgeClick, selectedEdgeId])

  return null
}
