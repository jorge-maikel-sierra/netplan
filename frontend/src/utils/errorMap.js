const ERROR_MAP = {
  PROJECT_NOT_FOUND: 'Proyecto no encontrado',
  FREE_TIER_LIMIT: 'Alcanzaste el límite de proyectos gratuitos. Actualizá tu plan.',
  INSUFFICIENT_NODES: 'Se requieren al menos 2 nodos para calcular el MST',
  DISCONNECTED_GRAPH: null, // use backend's detail field (already in Spanish)
  MANDATORY_CYCLE: 'Las aristas obligatorias forman un ciclo. Revisá las restricciones.',
  RATE_LIMITED: 'Demasiadas solicitudes. Esperá unos segundos y volvé a intentar.',
  INVALID_TOKEN: 'Sesión expirada. Iniciá sesión de nuevo.',
  INVALID_MAP_IMAGE: 'La imagen del mapa no es válida. Intentá exportar de nuevo.',
  NETWORK_ERROR: 'Error de conexión. Verificá tu internet e intentá de nuevo.',
  CLIENT_ERROR: 'No pudimos procesar la solicitud. Revisá los datos e intentá de nuevo.',
  GENERIC: 'Error del servidor. Si el problema persiste, contactá a soporte.',
}

/**
 * Maps an Axios error to a user-facing Spanish message and optional error code.
 * @param {import('axios').AxiosError} error
 * @returns {{ message: string|null, code: string|null }}
 */
export function getErrorMessage(error) {
  if (!error) return { message: null, code: null }

  // Network error — no response received
  if (!error.response) {
    return { message: ERROR_MAP.NETWORK_ERROR, code: 'NETWORK_ERROR' }
  }

  const { data, status } = error.response
  const errorCode = data?.error

  // Known error code from ERROR_MAP
  if (errorCode && errorCode in ERROR_MAP) {
    const msg = ERROR_MAP[errorCode]
    return {
      message: msg ?? data?.detail ?? ERROR_MAP.GENERIC,
      code: errorCode,
    }
  }

  // Fallback by status code
  if (status >= 500) {
    return { message: ERROR_MAP.GENERIC, code: null }
  }

  if (status >= 400) {
    return { message: ERROR_MAP.CLIENT_ERROR, code: errorCode || null }
  }

  return { message: ERROR_MAP.GENERIC, code: errorCode || null }
}

export default ERROR_MAP
