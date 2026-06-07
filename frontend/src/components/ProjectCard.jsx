import { Link } from 'react-router-dom'

export default function ProjectCard({ project }) {
  const createdDate = new Date(project.created_at).toLocaleDateString('es-AR', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })

  return (
    <Link
      to={`/projects/${project.id}`}
      className="block bg-white rounded-lg border border-gray-200 p-5 hover:shadow-md transition-shadow"
    >
      <h3 className="text-lg font-semibold text-gray-900 mb-2 truncate">
        {project.name}
      </h3>
      <div className="text-sm text-gray-500 space-y-1">
        {project.node_count !== undefined && (
          <p>{project.node_count} nodos</p>
        )}
        <p>Creado el {createdDate}</p>
      </div>
    </Link>
  )
}
