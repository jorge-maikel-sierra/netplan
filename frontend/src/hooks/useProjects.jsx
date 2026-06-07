import { useCallback, useReducer } from 'react'
import api from '../services/api'
import { getErrorMessage } from '../utils/errorMap'

const initialState = {
  project: null,
  nodes: [],
  edges: [],
  mstResult: null,
  loading: false,
  error: null,
}

const ACTIONS = {
  SET_LOADING: 'SET_LOADING',
  SET_ERROR: 'SET_ERROR',
  LOAD_PROJECT: 'LOAD_PROJECT',
  SET_NODES: 'SET_NODES',
  ADD_NODE: 'ADD_NODE',
  UPDATE_NODE: 'UPDATE_NODE',
  DELETE_NODE: 'DELETE_NODE',
  SET_EDGES: 'SET_EDGES',
  ADD_EDGE: 'ADD_EDGE',
  DELETE_EDGE: 'DELETE_EDGE',
  SET_MST_RESULT: 'SET_MST_RESULT',
}

function toActionError(err, fallbackMessage) {
  const { message, code } = getErrorMessage(err)
  return {
    message: message ?? fallbackMessage,
    code,
    detail: err?.response?.data?.detail ?? null,
    unreachableNodes: err?.response?.data?.unreachable_nodes ?? [],
  }
}

function projectsReducer(state, action) {
  switch (action.type) {
    case ACTIONS.SET_LOADING:
      return { ...state, loading: action.payload }

    case ACTIONS.SET_ERROR:
      return { ...state, error: action.payload }

    case ACTIONS.LOAD_PROJECT:
      return {
        ...state,
        project: action.payload.project,
        nodes: action.payload.nodes,
        edges: action.payload.edges,
        mstResult: action.payload.mstResult,
      }

    case ACTIONS.SET_NODES:
      return { ...state, nodes: action.payload }

    case ACTIONS.ADD_NODE:
      return {
        ...state,
        nodes: [...state.nodes, action.payload],
        mstResult: null,
      }

    case ACTIONS.UPDATE_NODE:
      return {
        ...state,
        nodes: state.nodes.map((node) => (node.id === action.payload.id ? action.payload : node)),
      }

    case ACTIONS.DELETE_NODE:
      return {
        ...state,
        nodes: state.nodes.filter((node) => node.id !== action.payload),
        edges: state.edges.filter(
          (edge) => edge.node_a_id !== action.payload && edge.node_b_id !== action.payload
        ),
        mstResult: null,
      }

    case ACTIONS.SET_EDGES:
      return { ...state, edges: action.payload }

    case ACTIONS.ADD_EDGE:
      return {
        ...state,
        edges: state.edges.some((edge) => edge.id === action.payload.id)
          ? state.edges.map((edge) => (edge.id === action.payload.id ? action.payload : edge))
          : [...state.edges, action.payload],
        mstResult: null,
      }

    case ACTIONS.DELETE_EDGE:
      return {
        ...state,
        edges: state.edges.filter((edge) => edge.id !== action.payload),
        mstResult: null,
      }

    case ACTIONS.SET_MST_RESULT:
      return { ...state, mstResult: action.payload }

    default:
      return state
  }
}

export default function useProjects() {
  const [state, dispatch] = useReducer(projectsReducer, initialState)

  const loadProject = useCallback(async (projectId) => {
    dispatch({ type: ACTIONS.SET_LOADING, payload: true })
    dispatch({ type: ACTIONS.SET_ERROR, payload: null })

    try {
      const { data } = await api.get(`/projects/${projectId}`)

      dispatch({
        type: ACTIONS.LOAD_PROJECT,
        payload: {
          project: data,
          nodes: data?.nodes ?? [],
          edges: data?.edges ?? [],
          mstResult: data?.last_result ?? null,
        },
      })
    } catch (err) {
      const actionError = toActionError(err, 'No pudimos cargar el proyecto. Intentá de nuevo.')
      dispatch({
        type: ACTIONS.SET_ERROR,
        payload: actionError.message,
      })
    } finally {
      dispatch({ type: ACTIONS.SET_LOADING, payload: false })
    }
  }, [])

  const setNodes = useCallback((nodes) => {
    dispatch({ type: ACTIONS.SET_NODES, payload: nodes })
  }, [])

  const addNode = useCallback((node) => {
    dispatch({ type: ACTIONS.ADD_NODE, payload: node })
  }, [])

  const updateNode = useCallback((node) => {
    dispatch({ type: ACTIONS.UPDATE_NODE, payload: node })
  }, [])

  const deleteNode = useCallback((nodeId) => {
    dispatch({ type: ACTIONS.DELETE_NODE, payload: nodeId })
  }, [])

  const setEdges = useCallback((edges) => {
    dispatch({ type: ACTIONS.SET_EDGES, payload: edges })
  }, [])

  const addEdge = useCallback((edge) => {
    dispatch({ type: ACTIONS.ADD_EDGE, payload: edge })
  }, [])

  const deleteEdge = useCallback((edgeId) => {
    dispatch({ type: ACTIONS.DELETE_EDGE, payload: edgeId })
  }, [])

  const setMstResult = useCallback((mstResult) => {
    dispatch({ type: ACTIONS.SET_MST_RESULT, payload: mstResult })
  }, [])

  const createNode = useCallback(async (projectId, payload) => {
    try {
      const { data } = await api.post(`/projects/${projectId}/nodes`, payload)
      dispatch({ type: ACTIONS.ADD_NODE, payload: data })
      dispatch({ type: ACTIONS.SET_ERROR, payload: null })
      return data
    } catch (err) {
      const actionError = toActionError(err, 'No pudimos crear el nodo. Intentá de nuevo.')
      dispatch({ type: ACTIONS.SET_ERROR, payload: actionError.message })
      throw actionError
    }
  }, [])

  const removeNode = useCallback(async (projectId, nodeId) => {
    try {
      await api.delete(`/projects/${projectId}/nodes/${nodeId}`)
      dispatch({ type: ACTIONS.DELETE_NODE, payload: nodeId })
      dispatch({ type: ACTIONS.SET_ERROR, payload: null })
    } catch (err) {
      const actionError = toActionError(err, 'No pudimos eliminar el nodo. Intentá de nuevo.')
      dispatch({ type: ACTIONS.SET_ERROR, payload: actionError.message })
      throw actionError
    }
  }, [])

  const updateNodePosition = useCallback(async (projectId, nodeId, payload) => {
    try {
      const { data } = await api.put(`/projects/${projectId}/nodes/${nodeId}`, payload)
      dispatch({ type: ACTIONS.UPDATE_NODE, payload: data })
      dispatch({ type: ACTIONS.SET_ERROR, payload: null })
      return data
    } catch (err) {
      const actionError = toActionError(err, 'No pudimos guardar la posición del nodo. Intentá de nuevo.')
      dispatch({ type: ACTIONS.SET_ERROR, payload: actionError.message })
      throw actionError
    }
  }, [])

  const createEdge = useCallback(async (projectId, payload) => {
    try {
      const { data } = await api.post(`/projects/${projectId}/edges`, payload)
      dispatch({ type: ACTIONS.ADD_EDGE, payload: data })
      dispatch({ type: ACTIONS.SET_ERROR, payload: null })
      return data
    } catch (err) {
      const actionError = toActionError(err, 'No pudimos crear la arista. Intentá de nuevo.')
      dispatch({ type: ACTIONS.SET_ERROR, payload: actionError.message })
      throw actionError
    }
  }, [])

  const removeEdge = useCallback(async (projectId, edgeId) => {
    try {
      await api.delete(`/projects/${projectId}/edges/${edgeId}`)
      dispatch({ type: ACTIONS.DELETE_EDGE, payload: edgeId })
      dispatch({ type: ACTIONS.SET_ERROR, payload: null })
    } catch (err) {
      const actionError = toActionError(err, 'No pudimos eliminar la arista. Intentá de nuevo.')
      dispatch({ type: ACTIONS.SET_ERROR, payload: actionError.message })
      throw actionError
    }
  }, [])

  const calculateMst = useCallback(async (projectId) => {
    try {
      const { data } = await api.post(`/projects/${projectId}/mst/calculate`)
      dispatch({ type: ACTIONS.SET_MST_RESULT, payload: data })
      dispatch({ type: ACTIONS.SET_ERROR, payload: null })
      return data
    } catch (err) {
      const actionError = toActionError(err, 'No pudimos calcular el MST. Intentá de nuevo.')
      dispatch({ type: ACTIONS.SET_ERROR, payload: actionError.message })
      throw actionError
    }
  }, [])

  const loadLatestMst = useCallback(async (projectId) => {
    console.log('[loadLatestMst] Called with projectId:', projectId)
    try {
      console.log('[loadLatestMst] Making API call...')
      const { data } = await api.get(`/projects/${projectId}/mst/latest`)
      console.log('[loadLatestMst] Success:', data)
      dispatch({ type: ACTIONS.SET_MST_RESULT, payload: data })
      dispatch({ type: ACTIONS.SET_ERROR, payload: null })
      return data
    } catch (err) {
      console.log('[loadLatestMst] Error:', err)
      const apiCode = err?.response?.data?.error
      console.log('[loadLatestMst] apiCode:', apiCode)

      if (apiCode === 'NO_RESULT') {
        dispatch({ type: ACTIONS.SET_MST_RESULT, payload: null })
        return null
      }

      const actionError = toActionError(err, 'No pudimos cargar el último resultado de MST.')
      dispatch({ type: ACTIONS.SET_ERROR, payload: actionError.message })
      throw actionError
    }
  }, [])

  return {
    ...state,
    loadProject,
    setNodes,
    addNode,
    updateNode,
    deleteNode,
    createNode,
    removeNode,
    updateNodePosition,
    setEdges,
    addEdge,
    deleteEdge,
    createEdge,
    removeEdge,
    setMstResult,
    calculateMst,
    loadLatestMst,
  }
}
