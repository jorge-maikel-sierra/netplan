import { Link, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function Navbar() {
  const { user, signOut } = useAuth()
  const location = useLocation()

  // Show back arrow on project detail pages: /projects/:id (but not /projects)
  const isDetailPage = /^\/projects\/[^/]+$/.test(location.pathname)

  return (
    <nav className="bg-white border-b border-gray-200 px-4 sm:px-6 py-3 flex items-center justify-between">
      <div className="flex items-center gap-3">
        {isDetailPage && (
          <Link
            to="/projects"
            className="text-gray-500 hover:text-gray-700 transition-colors"
            aria-label="Volver a proyectos"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </Link>
        )}
        <Link to="/projects" className="text-xl font-bold text-blue-600">
          NetPlan
        </Link>
      </div>

      <div className="flex items-center gap-2 sm:gap-4">
        <span className="text-sm text-gray-600 hidden sm:block truncate max-w-[200px]">
          {user?.email}
        </span>
        <button
          onClick={signOut}
          className="text-sm text-gray-500 hover:text-red-600 transition-colors"
        >
          Cerrar sesión
        </button>
      </div>
    </nav>
  )
}
