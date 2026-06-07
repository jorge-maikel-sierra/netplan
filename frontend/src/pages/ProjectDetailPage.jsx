import { useEffect, useMemo, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import useProjects from '../hooks/useProjects'
import MapView from '../components/MapView'
import ExportButtons from '../components/ExportButtons'
import ImportButton from '../components/ImportButton'
import { getErrorMessage } from '../utils/errorMap'

const NODE_TYPE_LABELS = {
  city: 'Ciudad',
  tower: 'Torre',
  datacenter: 'Datacenter',
}

const CONSTRAINT_LABELS = {
  normal: 'Normal',
  mandatory: 'Obligatoria',
  forbidden: 'Prohibida',
}

function formatError(err, fallback) {
  if (!err) return fallback
  if (typeof err === 'string') return err

  if (err.message) {
    if (err.code === 'DISCONNECTED_GRAPH') {
      const base = 'El grafo tiene subgrafos no conectados. Agregá más conexiones.'
      const unreachable = Array.isArray(err.unreachableNodes) ? err.unreachableNodes : []

      if (unreachable.length > 0) {
        return `${base} Nodos no alcanzables: ${unreachable.join(', ')}.`
      }

      return base
    }

    if (err.code === 'INSUFFICIENT_NODES') {
      return 'Se requieren al menos 2 nodos para calcular el MST'
    }

    return err.message
  }

  const { message } = getErrorMessage(err)
  return message ?? fallback
}

function resolveEdgeNodes(edge, nodesById) {
  const nodeA = nodesById.get(edge.node_a_id)
  const nodeB = nodesById.get(edge.node_b_id)

  return {
    nodeA,
    nodeB,
    label: `${nodeA?.name ?? edge.node_a_id} → ${nodeB?.name ?? edge.node_b_id}`,
  }
}

export default function ProjectDetailPage() {
  const { id: projectId } = useParams()
  const {
    project,
    nodes,
    edges,
    mstResult,
    loading,
    error,
    loadProject,
    createNode,
    removeNode,
    updateNodePosition,
    createEdge,
    removeEdge,
    calculateMst,
    loadLatestMst,
  } = useProjects()

  const [selectedNodeId, setSelectedNodeId] = useState(null)
  const [selectedEdgeId, setSelectedEdgeId] = useState(null)
  const mapRef = useRef(null)
  const [newNode, setNewNode] = useState({ label: '', type: 'city', lat: null, lng: null })
  const [newEdge, setNewEdge] = useState({ nodeAId: '', nodeBId: '', cost: '', constraintType: 'normal' })
  const [panelMessage, setPanelMessage] = useState(null)
  const [actionLoading, setActionLoading] = useState({
    node: false,
    edge: false,
    deleteNode: false,
    deleteEdge: false,
    calculateMst: false,
    latestMst: false,
    draggingNode: false,
  })

  useEffect(() => {
    if (!projectId) return
    loadProject(projectId)
  }, [projectId, loadProject])

  useEffect(() => {
    if (!selectedNodeId) return
    const stillExists = nodes.some((node) => node.id === selectedNodeId)
    if (!stillExists) {
      setSelectedNodeId(null)
    }
  }, [nodes, selectedNodeId])

  useEffect(() => {
    if (!selectedEdgeId) return
    const stillExists = edges.some((edge) => edge.id === selectedEdgeId)
    if (!stillExists) {
      setSelectedEdgeId(null)
    }
  }, [edges, selectedEdgeId])

  const title = useMemo(() => {
    if (loading) return 'Cargando proyecto...'
    if (project?.name) return project.name
    return 'Detalle del proyecto'
  }, [loading, project])

  const nodesById = useMemo(() => new Map(nodes.map((node) => [node.id, node])), [nodes])

  const selectedNode = useMemo(
    () => nodes.find((node) => node.id === selectedNodeId) ?? null,
    [nodes, selectedNodeId]
  )

  const selectedEdge = useMemo(
    () => edges.find((edge) => edge.id === selectedEdgeId) ?? null,
    [edges, selectedEdgeId]
  )

  const mstEdges = useMemo(() => {
    if (!Array.isArray(mstResult?.mst_edges)) return []
    return mstResult.mst_edges
  }, [mstResult])

  const onMapClick = (latlng) => {
    if (!latlng) return
    setNewNode((prev) => ({
      ...prev,
      lat: Number(latlng.lat.toFixed(6)),
      lng: Number(latlng.lng.toFixed(6)),
    }))
    setPanelMessage('Ubicación seleccionada en el mapa. Completá etiqueta y tipo para crear el nodo.')
  }

  const onCreateNode = async (event) => {
    event.preventDefault()
    if (!projectId) return

    const label = newNode.label.trim()
    if (!label) {
      setPanelMessage('Ingresá una etiqueta para el nodo.')
      return
    }

    if (newNode.lat === null || newNode.lng === null) {
      setPanelMessage('Hacé click en el mapa para elegir la ubicación del nodo.')
      return
    }

    setActionLoading((prev) => ({ ...prev, node: true }))
    setPanelMessage(null)
    try {
      const created = await createNode(projectId, {
        name: label,
        type: newNode.type,
        lat: newNode.lat,
        lng: newNode.lng,
      })
      setSelectedNodeId(created.id)
      setNewNode({ label: '', type: 'city', lat: null, lng: null })
      setPanelMessage('Nodo creado correctamente.')
    } catch (err) {
      setPanelMessage(formatError(err, 'No pudimos crear el nodo. Intentá de nuevo.'))
    } finally {
      setActionLoading((prev) => ({ ...prev, node: false }))
    }
  }

  const onDeleteNode = async () => {
    if (!projectId || !selectedNodeId) return
    setActionLoading((prev) => ({ ...prev, deleteNode: true }))
    setPanelMessage(null)
    try {
      await removeNode(projectId, selectedNodeId)
      setSelectedNodeId(null)
      setSelectedEdgeId(null)
      setPanelMessage('Nodo eliminado correctamente.')
    } catch (err) {
      setPanelMessage(formatError(err, 'No pudimos eliminar el nodo. Intentá de nuevo.'))
    } finally {
      setActionLoading((prev) => ({ ...prev, deleteNode: false }))
    }
  }

  const onCreateEdge = async (event) => {
    event.preventDefault()
    if (!projectId) return

    if (!newEdge.nodeAId || !newEdge.nodeBId) {
      setPanelMessage('Seleccioná nodo A y nodo B para crear la arista.')
      return
    }

    if (newEdge.nodeAId === newEdge.nodeBId) {
      setPanelMessage('Nodo A y nodo B deben ser distintos.')
      return
    }

    const parsedCost = Number(newEdge.cost)
    if (!Number.isFinite(parsedCost) || parsedCost < 0) {
      setPanelMessage('Ingresá un costo válido (mayor o igual a 0).')
      return
    }

    setActionLoading((prev) => ({ ...prev, edge: true }))
    setPanelMessage(null)
    try {
      const created = await createEdge(projectId, {
        node_a_id: newEdge.nodeAId,
        node_b_id: newEdge.nodeBId,
        cost: parsedCost,
        constraint_type: newEdge.constraintType,
      })
      setSelectedEdgeId(created.id)
      setNewEdge((prev) => ({ ...prev, cost: '', constraintType: 'normal' }))
      setPanelMessage('Arista creada/actualizada correctamente.')
    } catch (err) {
      setPanelMessage(formatError(err, 'No pudimos crear la arista. Intentá de nuevo.'))
    } finally {
      setActionLoading((prev) => ({ ...prev, edge: false }))
    }
  }

  const onDeleteEdge = async () => {
    if (!projectId || !selectedEdgeId) return
    setActionLoading((prev) => ({ ...prev, deleteEdge: true }))
    setPanelMessage(null)
    try {
      await removeEdge(projectId, selectedEdgeId)
      setSelectedEdgeId(null)
      setPanelMessage('Arista eliminada correctamente.')
    } catch (err) {
      setPanelMessage(formatError(err, 'No pudimos eliminar la arista. Intentá de nuevo.'))
    } finally {
      setActionLoading((prev) => ({ ...prev, deleteEdge: false }))
    }
  }

  const onCalculateMst = async () => {
    if (!projectId) return
    setActionLoading((prev) => ({ ...prev, calculateMst: true }))
    setPanelMessage(null)
    try {
      await calculateMst(projectId)
      setPanelMessage('MST calculado correctamente.')
    } catch (err) {
      setPanelMessage(formatError(err, 'No pudimos calcular el MST. Intentá de nuevo.'))
    } finally {
      setActionLoading((prev) => ({ ...prev, calculateMst: false }))
    }
  }

  const onLoadLatestMst = async () => {
    console.log('[onLoadLatestMst] Button clicked, projectId:', projectId)
    if (!projectId) return
    setActionLoading((prev) => ({ ...prev, latestMst: true }))
    setPanelMessage(null)
    try {
      const result = await loadLatestMst(projectId)
      if (!result) {
        setPanelMessage('Todavía no hay resultados de MST para este proyecto.')
        return
      }
      setPanelMessage('Se cargó el último resultado de MST.')
    } catch (err) {
      setPanelMessage(formatError(err, 'No pudimos cargar el último resultado de MST.'))
    } finally {
      setActionLoading((prev) => ({ ...prev, latestMst: false }))
    }
  }

  const handleExportMessage = (message) => {
    setPanelMessage(message)
  }

  const onNodeDragSave = async (nodeId, position) => {
    if (!projectId || !nodeId) return

    setActionLoading((prev) => ({ ...prev, draggingNode: true }))
    setPanelMessage(null)

    try {
      await updateNodePosition(projectId, nodeId, {
        lat: position.lat,
        lng: position.lng,
      })
      setSelectedNodeId(nodeId)
      setPanelMessage('Posición del nodo guardada correctamente.')
    } catch (err) {
      setPanelMessage(formatError(err, 'No pudimos guardar la posición del nodo. Intentá de nuevo.'))
      throw err
    } finally {
      setActionLoading((prev) => ({ ...prev, draggingNode: false }))
    }
  }

  const onNodeDragStart = (nodeId) => {
    setSelectedNodeId(nodeId)
    setSelectedEdgeId(null)
    setPanelMessage('Mové el nodo y usá "Guardar" en el popup para persistir la nueva posición.')
  }

  const onNodeDragCancel = () => {
    setPanelMessage('Se canceló el cambio de posición del nodo.')
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
        {error}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-bold text-gray-900">{title}</h1>
        <p className="text-sm text-gray-500 mt-1">
          Visualizá nodos y conexiones del proyecto.
        </p>
      </header>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <section className="xl:col-span-2 bg-white rounded-lg border border-gray-200 p-2 h-[520px]">
          <MapView
            ref={mapRef}
            nodes={nodes}
            edges={edges}
            mstResult={mstResult}
            onMapClick={onMapClick}
            selectedNodeId={selectedNodeId}
            selectedEdgeId={selectedEdgeId}
            onNodeClick={(nodeId) => {
              setSelectedNodeId(nodeId)
              setSelectedEdgeId(null)
              setNewEdge((prev) => ({ ...prev, nodeAId: nodeId }))
            }}
            onNodeDragStart={onNodeDragStart}
            onNodeDragCancel={onNodeDragCancel}
            onNodeDragSave={onNodeDragSave}
            onEdgeClick={(edgeId) => {
              setSelectedEdgeId(edgeId)
              setSelectedNodeId(null)
            }}
          />
        </section>

        <aside className="bg-white rounded-lg border border-gray-200 p-4 sm:p-5 space-y-6">
          <h2 className="text-lg font-semibold text-gray-900">Planificador</h2>

          {(panelMessage || error) && (
            <div
              className={`px-3 py-2 rounded text-sm ${
                error ? 'bg-red-50 border border-red-200 text-red-700' : 'bg-blue-50 border border-blue-200 text-blue-700'
              }`}
            >
              {panelMessage || error}
            </div>
          )}

          <section className="space-y-3">
            <h3 className="text-sm font-semibold text-gray-900">Agregar nodo (click en mapa)</h3>
            <form onSubmit={onCreateNode} className="space-y-3">
              <div>
                <label htmlFor="node-label" className="block text-xs font-medium text-gray-700 mb-1">
                  Etiqueta
                </label>
                <input
                  id="node-label"
                  type="text"
                  value={newNode.label}
                  onChange={(event) => setNewNode((prev) => ({ ...prev, label: event.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                  placeholder="Ej: Nodo A"
                />
              </div>
              <div>
                <label htmlFor="node-type" className="block text-xs font-medium text-gray-700 mb-1">
                  Tipo
                </label>
                <select
                  id="node-type"
                  value={newNode.type}
                  onChange={(event) => setNewNode((prev) => ({ ...prev, type: event.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                >
                  <option value="city">Ciudad</option>
                  <option value="tower">Torre</option>
                  <option value="datacenter">Datacenter</option>
                </select>
              </div>
              <p className="text-xs text-gray-500">
                {newNode.lat !== null && newNode.lng !== null
                  ? `Ubicación: ${newNode.lat}, ${newNode.lng}`
                  : 'Seleccioná ubicación haciendo click en el mapa.'}
              </p>
              <button
                type="submit"
                disabled={actionLoading.node}
                className="w-full bg-blue-600 text-white px-3 py-2 rounded-md text-sm hover:bg-blue-700 disabled:opacity-50"
              >
                {actionLoading.node ? 'Guardando nodo...' : 'Agregar nodo'}
              </button>
            </form>
          </section>

          <section className="space-y-3">
            <h3 className="text-sm font-semibold text-gray-900">Crear arista</h3>
            <form onSubmit={onCreateEdge} className="space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <div>
                  <label htmlFor="edge-node-a" className="block text-xs font-medium text-gray-700 mb-1">
                    Nodo A
                  </label>
                  <select
                    id="edge-node-a"
                    value={newEdge.nodeAId}
                    onChange={(event) => setNewEdge((prev) => ({ ...prev, nodeAId: event.target.value }))}
                    className="w-full px-2 py-2 border border-gray-300 rounded-md text-sm"
                  >
                    <option value="">Seleccionar</option>
                    {nodes.map((node) => (
                      <option key={node.id} value={node.id}>
                        {node.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label htmlFor="edge-node-b" className="block text-xs font-medium text-gray-700 mb-1">
                    Nodo B
                  </label>
                  <select
                    id="edge-node-b"
                    value={newEdge.nodeBId}
                    onChange={(event) => setNewEdge((prev) => ({ ...prev, nodeBId: event.target.value }))}
                    className="w-full px-2 py-2 border border-gray-300 rounded-md text-sm"
                  >
                    <option value="">Seleccionar</option>
                    {nodes.map((node) => (
                      <option key={node.id} value={node.id}>
                        {node.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <div>
                  <label htmlFor="edge-cost" className="block text-xs font-medium text-gray-700 mb-1">
                    Costo
                  </label>
                  <input
                    id="edge-cost"
                    type="number"
                    min="0"
                    step="0.01"
                    value={newEdge.cost}
                    onChange={(event) => setNewEdge((prev) => ({ ...prev, cost: event.target.value }))}
                    className="w-full px-2 py-2 border border-gray-300 rounded-md text-sm"
                    placeholder="0"
                  />
                </div>
                <div>
                  <label htmlFor="edge-constraint" className="block text-xs font-medium text-gray-700 mb-1">
                    Restricción
                  </label>
                  <select
                    id="edge-constraint"
                    value={newEdge.constraintType}
                    onChange={(event) =>
                      setNewEdge((prev) => ({ ...prev, constraintType: event.target.value }))
                    }
                    className="w-full px-2 py-2 border border-gray-300 rounded-md text-sm"
                  >
                    <option value="normal">Normal</option>
                    <option value="mandatory">Obligatoria</option>
                    <option value="forbidden">Prohibida</option>
                  </select>
                </div>
              </div>
              <button
                type="submit"
                disabled={actionLoading.edge}
                className="w-full bg-emerald-600 text-white px-3 py-2 rounded-md text-sm hover:bg-emerald-700 disabled:opacity-50"
              >
                {actionLoading.edge ? 'Guardando arista...' : 'Guardar arista'}
              </button>
            </form>
          </section>

          <section className="space-y-2 border-t border-gray-200 pt-4">
            <h3 className="text-sm font-semibold text-gray-900">Selección actual</h3>
            <div className="text-xs text-gray-600 space-y-1">
              <p>
                Nodo:{' '}
                {selectedNode
                  ? `${selectedNode.name} (${NODE_TYPE_LABELS[selectedNode.type] ?? selectedNode.type})`
                  : 'Ninguno'}
              </p>
              <p>
                Arista:{' '}
                {selectedEdge
                  ? `${resolveEdgeNodes(selectedEdge, nodesById).label} · ${selectedEdge.cost}`
                  : 'Ninguna'}
              </p>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <button
                type="button"
                disabled={!selectedNodeId || actionLoading.deleteNode}
                onClick={onDeleteNode}
                className="bg-red-600 text-white px-3 py-2 rounded-md text-xs hover:bg-red-700 disabled:opacity-50"
              >
                {actionLoading.deleteNode ? 'Eliminando...' : 'Eliminar nodo'}
              </button>
              <button
                type="button"
                disabled={!selectedEdgeId || actionLoading.deleteEdge}
                onClick={onDeleteEdge}
                className="bg-red-600 text-white px-3 py-2 rounded-md text-xs hover:bg-red-700 disabled:opacity-50"
              >
                {actionLoading.deleteEdge ? 'Eliminando...' : 'Eliminar arista'}
              </button>
            </div>
          </section>

          <section className="space-y-3 border-t border-gray-200 pt-4">
            <h3 className="text-sm font-semibold text-gray-900">MST</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <button
                type="button"
                onClick={onCalculateMst}
                disabled={actionLoading.calculateMst}
                className="bg-indigo-600 text-white px-3 py-2 rounded-md text-sm hover:bg-indigo-700 disabled:opacity-50"
              >
                {actionLoading.calculateMst ? 'Calculando...' : 'Calcular MST'}
              </button>
              <button
                type="button"
                onClick={onLoadLatestMst}
                disabled={actionLoading.latestMst}
                className="bg-slate-600 text-white px-3 py-2 rounded-md text-sm hover:bg-slate-700 disabled:opacity-50"
              >
                {actionLoading.latestMst ? 'Cargando...' : 'Ver último resultado'}
              </button>
            </div>

            {mstResult ? (
              <div className="bg-gray-50 border border-gray-200 rounded p-3 space-y-2">
                <p className="text-sm font-medium text-gray-900">
                  Costo total: <span className="font-bold">${Number(mstResult.total_cost ?? 0).toFixed(2)}</span>
                </p>
                <p className="text-xs text-gray-600">Cantidad de aristas: {mstEdges.length}</p>
                <div className="max-h-40 overflow-auto border border-gray-200 rounded bg-white">
                  {mstEdges.length === 0 ? (
                    <p className="text-xs text-gray-500 p-2">Sin aristas en el resultado.</p>
                  ) : (
                    <ul className="divide-y divide-gray-100">
                      {mstEdges.map((edge) => {
                        const nodeAName = nodesById.get(edge.node_a_id)?.name ?? edge.source_node_name ?? edge.node_a_id
                        const nodeBName = nodesById.get(edge.node_b_id)?.name ?? edge.node_b_id
                        return (
                          <li key={edge.edge_id} className="p-2 text-xs text-gray-700">
                            <div className="font-medium">
                              {nodeAName} → {nodeBName}
                            </div>
                            <div className="text-gray-500">
                              Costo: ${Number(edge.cost ?? 0).toFixed(2)} · Tipo:{' '}
                              {CONSTRAINT_LABELS[edge.type] ?? edge.type}
                            </div>
                          </li>
                        )
                      })}
                    </ul>
                  )}
                </div>
              </div>
            ) : (
              <p className="text-xs text-gray-500">Todavía no hay resultado de MST cargado.</p>
            )}
          </section>

          <section className="space-y-3 border-t border-gray-200 pt-4">
            <h3 className="text-sm font-semibold text-gray-900">Importar nodos</h3>
            <ImportButton
              projectId={projectId}
              onMessage={handleExportMessage}
            />
          </section>

          <section className="space-y-3 border-t border-gray-200 pt-4">
            <h3 className="text-sm font-semibold text-gray-900">Exportar</h3>
            <ExportButtons
              projectId={projectId}
              projectName={project?.name}
              mapRef={mapRef}
              onMessage={handleExportMessage}
            />
          </section>
        </aside>
      </div>
    </div>
  )
}
