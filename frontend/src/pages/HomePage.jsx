import { Link } from 'react-router-dom'

export default function HomePage() {
  return (
    <div className="min-h-screen bg-gray-50">
      {/* Hero section */}
      <div className="flex flex-col items-center justify-center min-h-[80vh] px-4 text-center">
        <div className="bg-white p-10 rounded-lg shadow-md w-full max-w-lg">
          <h1 className="text-3xl font-bold text-gray-900 mb-4">NetPlan</h1>
          <p className="text-gray-600 mb-8 leading-relaxed">
            Planificá tu infraestructura de red con algoritmos de árbol de
            expansión mínima (MST). Optimizá costos, respetá restricciones y
            visualizá tu topología en un mapa interactivo.
          </p>

          <Link
            to="/signup"
            className="inline-block w-full bg-blue-600 text-white py-3 px-4 rounded-md hover:bg-blue-700 transition-colors text-center font-medium cursor-pointer"
          >
            Comenzá gratis
          </Link>

          <p className="text-center text-sm text-gray-600 mt-4">
            ¿Ya tenés cuenta?{' '}
            <Link to="/login" className="text-blue-600 hover:underline">
              Iniciá sesión
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
