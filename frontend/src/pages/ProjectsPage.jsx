import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../services/api'
import ProjectCard from '../components/ProjectCard'
import { getErrorMessage } from '../utils/errorMap'

export default function ProjectsPage() {
  const [projects, setProjects] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Create modal state
  const [showModal, setShowModal] = useState(false)
  const [newName, setNewName] = useState('')
  const [createLoading, setCreateLoading] = useState(false)
  const [createError, setCreateError] = useState(null)
  const [freeTier, setFreeTier] = useState(false)

  const navigate = useNavigate()

  const fetchProjects = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      const { data } = await api.get('/projects')
      setProjects(data || [])
    } catch (err) {
      const { message } = getErrorMessage(err)
      setError(message ?? 'Error al cargar los proyectos. Intentá de nuevo.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchProjects()
  }, [fetchProjects])

  const openModal = () => {
    setNewName('')
    setCreateError(null)
    setFreeTier(false)
    setShowModal(true)
  }

  const closeModal = () => {
    setShowModal(false)
    setNewName('')
    setCreateError(null)
    setFreeTier(false)
  }

  const handleCreate = async (e) => {
    e.preventDefault()

    const trimmed = newName.trim()
    if (trimmed.length < 3 || trimmed.length > 100) {
      setCreateError('El nombre debe tener entre 3 y 100 caracteres')
      return
    }

    setCreateLoading(true)
    setCreateError(null)
    setFreeTier(false)

    try {
      const { data } = await api.post('/projects', { name: trimmed })
      closeModal()
      navigate(`/projects/${data.id}`)
    } catch (err) {
      const { message, code } = getErrorMessage(err)
      setCreateError(message)
      if (code === 'FREE_TIER_LIMIT') {
        setFreeTier(true)
      }
    } finally {
      setCreateLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    )
  }

  return (
    <div>
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Mis Proyectos</h1>
        <button
          onClick={openModal}
          className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 transition-colors cursor-pointer w-full sm:w-auto"
        >
          + Crear proyecto
        </button>
      </div>

      {/* Fetch error */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-6">
          {error}
        </div>
      )}

      {/* Empty state */}
      {!error && projects.length === 0 && (
        <div className="text-center py-16">
          <p className="text-gray-500 text-lg mb-4">
            Todavía no tenés proyectos. Crea uno nuevo.
          </p>
          <button
            onClick={openModal}
            className="bg-blue-600 text-white px-6 py-2 rounded-md hover:bg-blue-700 transition-colors cursor-pointer"
          >
            Crear proyecto
          </button>
        </div>
      )}

      {/* Project grid */}
      {projects.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((project) => (
            <ProjectCard key={project.id} project={project} />
          ))}
        </div>
      )}

      {/* Create project modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <h2 className="text-xl font-bold mb-4">Nuevo proyecto</h2>

            {/* Validation / API error (non-free-tier) */}
            {createError && !freeTier && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
                {createError}
              </div>
            )}

            {/* Free tier limit banner */}
            {freeTier && (
              <div className="bg-yellow-50 border border-yellow-200 text-yellow-800 px-4 py-3 rounded mb-4">
                <p className="mb-2">
                  Alcanzaste el límite de proyectos gratuitos. Actualizá tu plan.
                </p>
                <a
                  href="#"
                  className="text-blue-600 hover:underline font-medium"
                  onClick={(e) => {
                    e.preventDefault()
                    // TODO: redirect to billing/plan page when implemented
                  }}
                >
                  Actualizar plan
                </a>
              </div>
            )}

            <form onSubmit={handleCreate}>
              <div className="mb-4">
                <label
                  htmlFor="project-name"
                  className="block text-sm font-medium text-gray-700 mb-1"
                >
                  Nombre del proyecto
                </label>
                <input
                  id="project-name"
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Ej: Red troncal"
                  autoFocus
                  maxLength={100}
                />
              </div>

              <div className="flex justify-end gap-3">
                <button
                  type="button"
                  onClick={closeModal}
                  className="px-4 py-2 text-gray-700 hover:text-gray-900 transition-colors cursor-pointer"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={createLoading}
                  className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 disabled:opacity-50 transition-colors cursor-pointer"
                >
                  {createLoading ? 'Creando...' : 'Crear'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
