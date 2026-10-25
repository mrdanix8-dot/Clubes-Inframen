# Portal de Clubes INFRAMEN

Sistema web completo para la gestión de clubes estudiantiles del Instituto Nacional General Francisco Menéndez.

## Características

- **Login / Registro** para Estudiantes y Docentes (Director, Subdirector, Coordinador, Docente)
- **Catálogo de clubes** con filtros, fotos, cupos, horarios y requisitos
- **Inscripción en línea** (requiere promedio ≥ 7.0)
- **Mi Club**: ver inscripciones, anuncios, notificaciones y solicitar permisos
- **Agenda y eventos cívicos**
- **Panel Docente**:
  - Crear clubes (con foto)
  - Publicar anuncios (con notificación automática)
  - Editar horarios
  - Enviar notificaciones
  - Ver promedios de estudiantes
  - Gestionar permisos PDF
- **Modo claro / oscuro**
- **Responsive** (celular, tablet, desktop)
- **Animaciones** suaves en imágenes y tarjetas

## Cómo ejecutarlo en Visual Studio Code

1. Abre la carpeta `clubes-inframen` en VS Code.
2. Abre una terminal integrada (`Ctrl + Ñ` o Terminal → New Terminal).
3. Instala las dependencias:

```bash
pip install -r requirements.txt
```

4. Ejecuta el servidor:

```bash
python app.py
```

5. Abre el navegador en: **http://127.0.0.1:5000**

### Credenciales de prueba (Administrador)

- **NIE:** `ADMIN00001`
- **Contraseña:** `admin123`

## Estructura de archivos

```
clubes-inframen/
├── app.py                  ← Backend Flask + SQLite
├── requirements.txt
├── clubes_inframen.db      ← Se crea automáticamente
├── static/
│   ├── css/style.css
│   ├── js/main.js
│   └── uploads/            ← Fotos de clubes y PDFs
└── templates/
    ├── base.html
    ├── login.html
    ├── catalogo.html
    ├── club_detalle.html
    ├── mi_club.html
    ├── agenda.html
    └── gestion.html
```

## Sobre Netlify y persistencia de datos

**Netlify** es para sitios estáticos. Si subes solo HTML/CSS/JS:

- Los usuarios **no se guardan** (se pierden al refrescar).
- Las imágenes **no se guardan**.

Para que todo funcione de verdad necesitas un servidor con Python (Render, Railway, PythonAnywhere, etc.) o una solución como Supabase + frontend estático.

Este proyecto usa **SQLite** (archivo `clubes_inframen.db`) y la carpeta `static/uploads`. Ambos se mantienen mientras el servidor esté corriendo.

## Tecnologías

- Python 3 + Flask
- SQLite
- HTML5 + CSS3 (custom, sin frameworks)
- JavaScript vanilla
