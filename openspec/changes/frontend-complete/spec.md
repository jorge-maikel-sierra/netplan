# Frontend Complete Specification

## 1. Auth Module

### REQ-AUTH-001: Login page
The system MUST provide a login form with email and password fields, and MUST redirect to `/projects` on success.

- **GIVEN** an unauthenticated user at `/login`
- **WHEN** they submit valid credentials
- **THEN** they are redirected to `/projects`
- **AND** the JWT session is stored by supabase-js

#### Scenario: Login failure
- **GIVEN** an unauthenticated user at `/login`
- **WHEN** they submit invalid credentials
- **THEN** an error message in Spanish is shown (e.g., "Email o contraseña incorrectos")
- **AND** the URL stays at `/login`

### REQ-AUTH-002: Signup page
The system MUST provide a signup form with email, password, and password confirmation.

- **GIVEN** a new user at `/signup`
- **WHEN** they submit matching passwords and valid email
- **THEN** a success message is shown: "Revisá tu email para confirmar la cuenta"
- **AND** they are NOT automatically redirected (email confirmation required)

#### Scenario: Password mismatch
- **GIVEN** a user at `/signup` with non-matching password fields
- **WHEN** they submit
- **THEN** an inline error is shown: "Las contraseñas no coinciden"

### REQ-AUTH-003: Protected routes
The system MUST redirect unauthenticated users to `/login` for any route except `/login` and `/signup`.

- **GIVEN** an unauthenticated user visits `/projects`
- **WHEN** the route resolves
- **THEN** they are redirected to `/login` with the original URL preserved

#### Scenario: Session refresh on page load
- **GIVEN** a user with an existing Supabase session (e.g., from `localStorage`)
- **WHEN** they load any protected route
- **THEN** they see the page without being redirected to login

### REQ-AUTH-004: Logout
The system MUST provide a logout button in the navigation that calls `supabase.auth.signOut()` and redirects to `/login`.

- **GIVEN** an authenticated user
- **WHEN** they click "Cerrar sesión"
- **THEN** they are redirected to `/login`
- **AND** the protected routes no longer render

## 2. Projects Module

### REQ-PRJ-001: Project list page
The system MUST display a list of all projects for the current organization at `/projects`, ordered by `created_at` DESC.

- **GIVEN** an authenticated user with 3 projects in their org
- **WHEN** they visit `/projects`
- **THEN** 3 project cards/rows are shown with name, node count, and creation date
- **AND** each card links to `/projects/{id}`

#### Scenario: Empty state
- **GIVEN** an authenticated user with zero projects
- **WHEN** they visit `/projects`
- **THEN** a message is shown: "Todavía no tenés proyectos. Crea uno nuevo."
- **AND** a "Crear proyecto" call-to-action button is visible

### REQ-PRJ-002: Create project
The system MUST provide a modal or inline form to create a project with a `name` field (3-100 chars).

- **GIVEN** an authenticated user on the projects page
- **WHEN** they click "Crear proyecto", fill the name, and confirm
- **THEN** the new project appears in the list
- **AND** the user is optionally navigated to the new project's detail page

#### Scenario: Free tier limit
- **GIVEN** an organization on the `free` plan with 3 existing projects
- **WHEN** they attempt to create a 4th project
- **THEN** a 403 error from the backend is shown as: "Alcanzaste el límite de proyectos gratuitos. Actualizá tu plan."
- **AND** an "Actualizar plan" link/button is shown

#### Scenario: Validation error
- **GIVEN** the user submits a project name with 0 characters
- **WHEN** the form validates
- **THEN** an inline error is shown: "El nombre debe tener entre 3 y 100 caracteres"
- **AND** the form is NOT submitted

## 3. Map Module

### REQ-MAP-001: Leaflet map display
The system MUST render a Leaflet map centered on the project's nodes, or at a default lat/lng if none exist, on the project detail page `/projects/{id}`.

- **GIVEN** a project with 5 nodes at various coordinates
- **WHEN** the detail page loads
- **THEN** a Leaflet map is rendered with OpenStreetMap tiles
- **AND** the map auto-fits the bounds of all nodes (or shows Argentina/CABA at zoom 4 if no nodes)

#### Scenario: Map DOES NOT re-initialize on re-render
- **GIVEN** the map is already rendered
- **WHEN** a React state change triggers a re-render
- **THEN** the map instance is reused (not re-created)
- **AND** `useRef` is used for the map instance to prevent Leaflet re-init

### REQ-MAP-002: Node markers
The system MUST show a draggable marker on the map for each node in the project.

- **GIVEN** a project with nodes A, B, C
- **WHEN** the map loads
- **THEN** each node is displayed as a Leaflet marker (default icon) at its lat/lng
- **AND** clicking a marker shows a popup with the node name and type

#### Scenario: Marker drag updates coordinates
- **GIVEN** a node marker on the map
- **WHEN** the user drags it to a new position
- **THEN** the new lat/lng are shown in the popup
- **AND** a "Guardar" button appears to persist the new position via PATCH to the backend

### REQ-MAP-003: Edge lines
The system MUST draw lines between connected nodes on the map.

- **GIVEN** a project with edges A-B and B-C
- **WHEN** the map loads
- **THEN** each edge is drawn as a polyline connecting its two node markers
- **AND** the polyline color reflects the constraint type (green=normal, blue=mandatory, red=forbidden)

## 4. MST Module

### REQ-MST-FRONT-001: Calculate MST button
The system MUST provide a "Calcular MST" button on the project detail page that calls `POST /api/v1/projects/{id}/mst/calculate`.

- **GIVEN** a project with at least 2 connected nodes
- **WHEN** the user clicks "Calcular MST"
- **THEN** a loading spinner is shown while the request is in flight
- **AND** on success, the result panel appears with total cost and highlighted MST edges

#### Scenario: Disconnected graph error
- **GIVEN** a project with disconnected subgraphs
- **WHEN** the user clicks "Calcular MST"
- **THEN** the error is shown in Spanish: "El grafo tiene subgrafos no conectados. Agregá más conexiones."
- **AND** the unreachable nodes are listed if provided by the API

#### Scenario: Insufficient nodes
- **GIVEN** a project with 0 or 1 node
- **WHEN** the user clicks "Calcular MST"
- **THEN** the error is shown in Spanish: "Se requieren al menos 2 nodos para calcular el MST"

### REQ-MST-FRONT-002: MST result display
The system MUST display the MST result showing total cost and the list of MST edges on the project page.

- **GIVEN** a successful MST calculation
- **WHEN** the result panel renders
- **THEN** the total cost is displayed prominently (e.g., "Costo total: $1,250")
- **AND** each MST edge is listed showing node_a → node_b, cost, and type
- **AND** the MST edges are highlighted on the map (thicker line, distinct color)

#### Scenario: Latest result on page load
- **GIVEN** a project that has a previous MST result
- **WHEN** the detail page loads
- **THEN** the result panel renders with the latest MST result
- **AND** MST edges are highlighted on the map immediately

## 5. Export Module

### REQ-EXP-FRONT-001: Excel download
The system MUST provide a "Descargar Excel" button that triggers a download via `GET /api/v1/projects/{id}/export/excel`.

- **GIVEN** an authenticated user on a project detail page
- **WHEN** they click "Descargar Excel"
- **THEN** the browser downloads the generated `.xlsx` file
- **AND** a loading indicator is shown during download

#### Scenario: Download error
- **GIVEN** a network error during Excel download
- **WHEN** the request fails
- **THEN** an error is shown in Spanish: "Error al generar el archivo Excel. Intentá de nuevo."

### REQ-EXP-FRONT-002: PDF export
The system MUST provide a "Descargar PDF" button that captures the map canvas, sends it to `POST /api/v1/projects/{id}/export/pdf`, and downloads the result.

- **GIVEN** an authenticated user on a project detail page with MST result
- **WHEN** they click "Descargar PDF"
- **THEN** the map is rendered to a base64 PNG via canvas export
- **AND** the image is sent to the backend PDF endpoint
- **AND** the browser downloads the generated `.pdf` file

#### Scenario: PDF export without MST
- **GIVEN** a project with nodes but NO MST result
- **WHEN** the user clicks "Descargar PDF"
- **THEN** the PDF is generated with nodes and edges but without the MST cost summary

## Error Handling

### REQ-ERR-001: Spanish error messages
The system MUST map ALL API error codes to user-facing messages in Spanish. Raw API errors MUST NOT be displayed to the user.

| API Error Code | User-Facing Message (Spanish) |
|---------------|------------------------------|
| `PROJECT_NOT_FOUND` | "Proyecto no encontrado" |
| `FREE_TIER_LIMIT` | "Alcanzaste el límite de proyectos gratuitos. Actualizá tu plan." |
| `INSUFFICIENT_NODES` | "Se requieren al menos 2 nodos para calcular el MST" |
| `DISCONNECTED_GRAPH` | "El grafo tiene subgrafos no conectados. Agregá más conexiones." |
| `MANDATORY_CYCLE` | "Las aristas obligatorias forman un ciclo. Revisá las restricciones." |
| `RATE_LIMITED` | "Demasiadas solicitudes. Esperá unos segundos y volvé a intentar." |
| `INVALID_TOKEN` | "Sesión expirada. Iniciá sesión de nuevo." |
| `NETWORK_ERROR` | "Error de conexión. Verificá tu internet e intentá de nuevo." |
| Generic 500 | "Error del servidor. Si el problema persiste, contactá a soporte." |

### REQ-ERR-002: 401 auto-redirect
The system MUST redirect to `/login` when any API call returns 401.

- **GIVEN** an authenticated user whose session expires
- **WHEN** any API call returns 401
- **THEN** the Axios interceptor calls `supabase.auth.signOut()`
- **AND** the user is redirected to `/login`
- **AND** no error popup is shown (silent redirect)

## Navigation Layout

### REQ-NAV-001: App shell
The system MUST provide a responsive app shell with a top navigation bar and the current route rendered below it.

- **GIVEN** an authenticated user on any page
- **THEN** the top bar shows "NetPlan" (logo/name) on the left
- **AND** the logout button is on the right
- **AND** on `/projects/{id}`, a back arrow links to `/projects`
- **AND** the layout is responsive: sidebar/hamburger on mobile, sidebar visible on desktop

## UI Language

### REQ-LANG-001: All UI in Spanish
The system MUST render all user-facing strings in Spanish (Rioplatense). English MUST NOT be shown except in code/technical contexts.

- **GIVEN** any page or component
- **WHEN** the user sees text
- **THEN** it is in Spanish (e.g., "Crear proyecto", not "Create project"; "Cerrar sesión", not "Logout")
