from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, send_from_directory, jsonify
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3
import os
from datetime import datetime
from functools import wraps
import re

app = Flask(__name__)
app.secret_key = "inframen-clubes-2025-clave-secreta-cambiar"
app.config["UPLOAD_FOLDER"] = os.path.join("static", "uploads")
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

ALLOWED_IMG = {"png", "jpg", "jpeg", "gif", "webp"}
ALLOWED_PDF = {"pdf"}

def allowed_file(filename, tipos):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in tipos

def validar_nie(nie, es_docente=False):
    """NIE/ID: solo alfanumérico, longitud limitada."""
    nie = (nie or "").strip()
    if not nie:
        return False, "El identificador es obligatorio."
    if len(nie) < 4 or len(nie) > 20:
        return False, "El NIE/ID debe tener entre 4 y 20 caracteres."
    if es_docente:
        # ID maestro: letras, números y guiones
        if not re.match(r"^[A-Za-z0-9\-]+$", nie):
            return False, "El ID del maestro solo puede contener letras, números y guiones."
    else:
        # NIE estudiante: preferir solo números
        if not re.match(r"^[0-9]+$", nie):
            return False, "El NIE del estudiante solo puede contener números."
    return True, nie

def validar_nombre(nombre):
    nombre = (nombre or "").strip()
    if not nombre:
        return False, "El nombre es obligatorio."
    if len(nombre) < 3 or len(nombre) > 60:
        return False, "El nombre debe tener entre 3 y 60 caracteres."
    # Letras, espacios y acentos
    if not re.match(r"^[A-Za-zÁÉÍÓÚáéíóúÑñÜü\s\.\-]+$", nombre):
        return False, "El nombre solo puede contener letras y espacios (sin números)."
    return True, nombre

def es_admin_general():
    """Director o subdirector: acceso total."""
    return session.get("rol") == "docente" and (session.get("cargo") or "").lower() in ("director", "subdirector")


def club_permitido(club_id):
    """True si el usuario puede gestionar ese club."""
    if es_admin_general():
        return True
    conn = get_db()
    row = conn.execute("SELECT docente_id FROM clubes WHERE id = ?", (club_id,)).fetchone()
    conn.close()
    if not row:
        return False
    return row["docente_id"] == session.get("user_id") or row["docente_id"] is None

def es_docente_limitado():
    """Docente o coordinador: un solo club."""
    return session.get("rol") == "docente" and (session.get("cargo") or "").lower() in ("docente", "coordinador", "")


def get_db():
    conn = sqlite3.connect("clubes_inframen.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nie TEXT UNIQUE NOT NULL,
            nombre TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            rol TEXT NOT NULL,                -- estudiante | docente
            cargo TEXT,                       -- director, subdirector, coordinador, docente
            seccion TEXT,                     -- 1ero, 2do, 3ero
            bachillerato TEXT,                -- General, Técnico Software, etc.
            edad INTEGER,
            promedio REAL DEFAULT 0.0,
            email TEXT,
            foto TEXT,
            boleta_pdf TEXT,
            creado TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Migración suave si la tabla ya existía sin boleta_pdf
    try:
        c.execute("ALTER TABLE usuarios ADD COLUMN boleta_pdf TEXT")
    except Exception:
        pass

    c.execute("""
        CREATE TABLE IF NOT EXISTS clubes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            categoria TEXT NOT NULL,
            descripcion TEXT,
            horario TEXT,
            lugar TEXT,
            requisitos TEXT,
            capacidad INTEGER DEFAULT 20,
            inscritos INTEGER DEFAULT 0,
            docente_id INTEGER,
            foto TEXT,
            turno TEXT,
            activo INTEGER DEFAULT 1,
            creado TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (docente_id) REFERENCES usuarios(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS inscripciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            estudiante_id INTEGER NOT NULL,
            club_id INTEGER NOT NULL,
            estado TEXT DEFAULT 'aceptado',
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(estudiante_id, club_id),
            FOREIGN KEY (estudiante_id) REFERENCES usuarios(id),
            FOREIGN KEY (club_id) REFERENCES clubes(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS anuncios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            club_id INTEGER,
            titulo TEXT NOT NULL,
            contenido TEXT NOT NULL,
            autor_id INTEGER,
            urgente INTEGER DEFAULT 0,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (club_id) REFERENCES clubes(id),
            FOREIGN KEY (autor_id) REFERENCES usuarios(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS permisos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            estudiante_id INTEGER,
            club_id INTEGER,
            motivo TEXT,
            fecha_inicio TEXT,
            fecha_fin TEXT,
            archivo_pdf TEXT,
            estado TEXT DEFAULT 'pendiente',
            emitido_por INTEGER,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (estudiante_id) REFERENCES usuarios(id),
            FOREIGN KEY (club_id) REFERENCES clubes(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS eventos_club (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            club_id INTEGER,
            titulo TEXT NOT NULL,
            descripcion TEXT,
            fecha TEXT,
            hora TEXT,
            lugar TEXT,
            creado_por INTEGER,
            creado TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (club_id) REFERENCES clubes(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS notificaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            titulo TEXT,
            mensaje TEXT,
            leida INTEGER DEFAULT 0,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        )
    """)

    # Admin de prueba
    c.execute("SELECT id FROM usuarios WHERE nie = ?", ("ADMIN00001",))
    if not c.fetchone():
        c.execute("""
            INSERT INTO usuarios (nie, nombre, password_hash, rol, cargo)
            VALUES (?, ?, ?, ?, ?)
        """, (
            "ADMIN00001",
            "David Elias - Administrador",
            generate_password_hash("admin123"),
            "docente",
            "director"
        ))

    # Clubes de ejemplo (inspirados en tus capturas)
    # foto: nombre de archivo en static/img/ o static/uploads/
    clubes_demo = [
        ("Fútbol Sala (Futsal)", "Deportes",
         "Entrenamiento táctico intensivo y competencia en ligas intercolegiales de San Salvador.",
         "Martes y Jueves · 2:00 PM – 4:00 PM", "Cancha techada INFRAMEN",
         "Promedio ≥ 7.0 · Conducta Muy Buena", 25, "Matutino", "futsal"),
        ("Fútbol 11", "Deportes",
         "Plantilla representativa del instituto para el Torneo Estudiantil Nacional INDES.",
         "Lun, Mié y Vie · 3:00 PM – 5:30 PM", "Campo Central INFRAMEN",
         "Prueba física obligatoria · Promedio ≥ 7.0", 30, "Vespertino", "futbol11"),
        ("Voleibol INFRAMEN", "Deportes",
         "Fundamentos de saque, recepción y táctica de conjunto con alta disciplina formativa.",
         "Martes y Viernes · 1:30 PM – 3:30 PM", "Gimnasio Polideportivo",
         "Promedio ≥ 7.0 · Constancia Médica", 20, "Matutino", "voleibol"),
        ("Banda de Paz INFRAMEN", "Música y Banda",
         "La legendaria y galardonada banda estudiantil. Formación en lectura musical, sincronización cívica, percusión, trompetas, trombones, saxofones y liras.",
         "Lun a Jue · 2:00 PM – 5:00 PM", "Plaza Cívica & Auditorio",
         "Promedio ≥ 7.0 · No requiere instrumento propio", 45, "Vespertino", "banda.jpg"),
        ("Cachiporras & Bastoneras", "Arte y Tradición",
         "Coreografías sincronizadas de marcha, destreza de bastón y disciplina escénica patriótica.",
         "Lun, Mié y Vie · 2:00 PM – 4:30 PM", "Patio de Honor Central",
         "Promedio ≥ 7.0 · Coordinación psicomotriz", 25, "Matutino", "cachiporras.jpg"),
        ("Muralismo & Pintura", "Arte y Tradición",
         "Técnicas de dibujo anatómico, óleo, acrílico y diseño de murales cívicos en el campus.",
         "Miércoles y Viernes · 1:30 PM – 4:00 PM", "Taller de Artes Gráficas",
         "Promedio ≥ 7.0 · Portafolio de bosquejos", 15, "Vespertino", "muralismo"),
        ("Cruz Roja Escolar & Vol.", "Voluntariado y Liderazgo",
         "Primeros auxilios, prevención de riesgos y voluntariado comunitario para graduación.",
         "Sábados · 8:00 AM – 12:00 MD", "Sala de Proyectos Cívicos",
         "Promedio ≥ 7.0 · Servicio Social 150 hrs", 30, "Matutino", "cruzroja"),
        ("Danza Folklórica", "Arte y Tradición",
         "Tradiciones de El Salvador a través de la danza. Trajes típicos y presentaciones oficiales.",
         "Martes y Jueves · 3:00 PM – 5:00 PM", "Salón de Danza",
         "Promedio ≥ 7.0", 20, "Vespertino", "danza"),
    ]

    for cl in clubes_demo:
        c.execute("SELECT id FROM clubes WHERE nombre = ?", (cl[0],))
        if not c.fetchone():
            c.execute("""
                INSERT INTO clubes
                (nombre, categoria, descripcion, horario, lugar, requisitos, capacidad, turno, foto)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, cl)
        else:
            # Actualizar fotos locales si ya existen
            if cl[0] == "Banda de Paz INFRAMEN":
                c.execute("UPDATE clubes SET foto = ? WHERE nombre = ?", ("banda.jpg", cl[0]))
            elif cl[0] == "Cachiporras & Bastoneras":
                c.execute("UPDATE clubes SET foto = ? WHERE nombre = ?", ("cachiporras.jpg", cl[0]))
            elif cl[0] == "Cachiporras & Bastoneras":
                c.execute("UPDATE clubes SET foto = ? WHERE nombre = ?", ("banda.jpg", cl[0]))

    conn.commit()
    conn.close()
    print("Base de datos inicializada correctamente.")

# -------------------- Decoradores --------------------
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Debes iniciar sesión.", "error")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def docente_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("rol") != "docente":
            flash("Acceso exclusivo para docentes / administración.", "error")
            return redirect(url_for("catalogo"))
        return f(*args, **kwargs)
    return decorated

# -------------------- Rutas de autenticación --------------------
@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("catalogo"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        nie = request.form.get("nie", "").strip()
        password = request.form.get("password", "")
        rol_form = request.form.get("rol", "estudiante")

        conn = get_db()
        user = conn.execute("SELECT * FROM usuarios WHERE nie = ?", (nie,)).fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            if rol_form == "docente" and user["rol"] != "docente":
                flash("Esta cuenta no tiene permisos de docente.", "error")
                return render_template("login.html")
            session.clear()
            session["user_id"] = user["id"]
            session["nombre"] = user["nombre"]
            session["rol"] = user["rol"]
            session["cargo"] = user["cargo"] or ""
            session["nie"] = user["nie"]
            session["foto"] = user["foto"] or ""
            flash(f"¡Bienvenido/a, {user['nombre']}!", "success")
            return redirect(url_for("catalogo"))
        flash("NIE o contraseña incorrectos.", "error")
    return render_template("login.html")

@app.route("/registro", methods=["POST"])
def registro():
    nie = request.form.get("nie", "").strip()
    nombre = request.form.get("nombre", "").strip()
    password = request.form.get("password", "")
    rol = request.form.get("rol", "estudiante")
    cargo = request.form.get("cargo", "")
    seccion = request.form.get("seccion", "")
    bachillerato = request.form.get("bachillerato", "")
    edad = request.form.get("edad") or None
    promedio = float(request.form.get("promedio") or 0)

    if not all([nie, nombre, password]):
        flash("Completa los campos obligatorios (NIE, Nombre y Contraseña).", "error")
        return redirect(url_for("login"))

    # Foto de perfil (opcional)
    foto_nombre = None
    if "foto" in request.files:
        f = request.files["foto"]
        if f and f.filename and allowed_file(f.filename, ALLOWED_IMG):
            ext = f.filename.rsplit(".", 1)[1].lower()
            foto_nombre = secure_filename(f"perfil_{nie}_{datetime.now().strftime('%Y%m%d%H%M%S')}.{ext}")
            f.save(os.path.join(app.config["UPLOAD_FOLDER"], foto_nombre))

    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO usuarios
            (nie, nombre, password_hash, rol, cargo, seccion, bachillerato, edad, promedio, foto)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (nie, nombre, generate_password_hash(password), rol, cargo,
              seccion, bachillerato, edad, promedio, foto_nombre))
        conn.commit()
        flash("Cuenta creada exitosamente. Ya puedes iniciar sesión.", "success")
    except sqlite3.IntegrityError:
        flash("Ese NIE ya está registrado.", "error")
    finally:
        conn.close()
    return redirect(url_for("login"))

@app.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada correctamente.", "success")
    return redirect(url_for("login"))

# -------------------- Catálogo y Clubes --------------------
@app.route("/catalogo")
@login_required
def catalogo():
    conn = get_db()
    clubes = conn.execute("""
        SELECT c.*, u.nombre AS docente_nombre
        FROM clubes c
        LEFT JOIN usuarios u ON c.docente_id = u.id
        WHERE c.activo = 1
        ORDER BY c.categoria, c.nombre
    """).fetchall()
    categorias = [r["categoria"] for r in
                  conn.execute("SELECT DISTINCT categoria FROM clubes WHERE activo=1").fetchall()]
    conn.close()
    return render_template("catalogo.html", clubes=clubes, categorias=categorias)

@app.route("/club/<int:club_id>")
@login_required
def club_detalle(club_id):
    conn = get_db()
    club = conn.execute("""
        SELECT c.*, u.nombre AS docente_nombre
        FROM clubes c
        LEFT JOIN usuarios u ON c.docente_id = u.id
        WHERE c.id = ?
    """, (club_id,)).fetchone()

    if not club:
        flash("Club no encontrado.", "error")
        conn.close()
        return redirect(url_for("catalogo"))

    anuncios = conn.execute("""
        SELECT a.*, u.nombre AS autor
        FROM anuncios a
        LEFT JOIN usuarios u ON a.autor_id = u.id
        WHERE a.club_id = ?
        ORDER BY a.fecha DESC LIMIT 8
    """, (club_id,)).fetchall()

    inscrito = None
    if session["rol"] == "estudiante":
        inscrito = conn.execute("""
            SELECT * FROM inscripciones
            WHERE estudiante_id = ? AND club_id = ?
        """, (session["user_id"], club_id)).fetchone()

    conn.close()
    return render_template("club_detalle.html", club=club, anuncios=anuncios, inscrito=inscrito)

@app.route("/inscribir/<int:club_id>", methods=["POST"])
@login_required
def inscribir(club_id):
    if session["rol"] != "estudiante":
        flash("Solo los estudiantes pueden inscribirse.", "error")
        return redirect(url_for("club_detalle", club_id=club_id))

    conn = get_db()
    user = conn.execute("SELECT promedio FROM usuarios WHERE id = ?", (session["user_id"],)).fetchone()
    club = conn.execute("SELECT capacidad, inscritos, nombre FROM clubes WHERE id = ?", (club_id,)).fetchone()

    if not club:
        flash("Club no existe.", "error")
        conn.close()
        return redirect(url_for("catalogo"))

    if user["promedio"] < 7.0:
        flash("Necesitas un promedio mínimo de 7.0 para inscribirte en cualquier club.", "error")
        conn.close()
        return redirect(url_for("club_detalle", club_id=club_id))

    if club["inscritos"] >= club["capacidad"]:
        flash(f"El club «{club['nombre']}» ya no tiene cupos disponibles.", "error")
        conn.close()
        return redirect(url_for("club_detalle", club_id=club_id))

    try:
        conn.execute("""
            INSERT INTO inscripciones (estudiante_id, club_id, estado)
            VALUES (?, ?, 'aceptado')
        """, (session["user_id"], club_id))
        conn.execute("UPDATE clubes SET inscritos = inscritos + 1 WHERE id = ?", (club_id,))
        conn.commit()
        flash(f"¡Te has inscrito exitosamente en «{club['nombre']}»!", "success")
    except sqlite3.IntegrityError:
        flash("Ya estás inscrito en este club.", "error")
    finally:
        conn.close()
    return redirect(url_for("mi_club"))

# -------------------- Mi Perfil --------------------
@app.route("/mi-perfil")
@app.route("/mi-club")  # compatibilidad
@login_required
def mi_club():
    conn = get_db()
    usuario = conn.execute("SELECT * FROM usuarios WHERE id = ?", (session["user_id"],)).fetchone()

    if session.get("rol") == "docente":
        # Clubes que administra el docente
        mis_clubes = conn.execute("""
            SELECT * FROM clubes
            WHERE docente_id = ? AND activo = 1
            ORDER BY nombre
        """, (session["user_id"],)).fetchall()
        # También clubes sin docente asignado (para que pueda tomarlos)
        sin_asignar = conn.execute("""
            SELECT * FROM clubes WHERE docente_id IS NULL AND activo = 1 ORDER BY nombre
        """).fetchall()
        notifs = conn.execute("""
            SELECT * FROM notificaciones WHERE usuario_id = ?
            ORDER BY fecha DESC LIMIT 15
        """, (session["user_id"],)).fetchall()
        permisos_pub = conn.execute("""
            SELECT p.*, c.nombre AS club_nombre
            FROM permisos p
            LEFT JOIN clubes c ON p.club_id = c.id
            WHERE p.emitido_por = ? AND p.archivo_pdf IS NOT NULL
            ORDER BY p.fecha DESC LIMIT 20
        """, (session["user_id"],)).fetchall()
        conn.close()
        return render_template("mi_perfil_docente.html",
                               usuario=usuario,
                               mis_clubes=mis_clubes,
                               sin_asignar=sin_asignar,
                               notifs=notifs,
                               permisos_pub=permisos_pub)

    # Estudiante
    inscripciones = conn.execute("""
        SELECT c.*, i.estado, i.fecha AS fecha_inscripcion
        FROM inscripciones i
        JOIN clubes c ON i.club_id = c.id
        WHERE i.estudiante_id = ?
        ORDER BY i.fecha DESC
    """, (session["user_id"],)).fetchall()

    anuncios = []
    if inscripciones:
        ids = [str(i["id"]) for i in inscripciones]
        placeholders = ",".join(["?"] * len(ids))
        anuncios = conn.execute(f"""
            SELECT a.*, c.nombre AS club_nombre, u.nombre AS autor
            FROM anuncios a
            JOIN clubes c ON a.club_id = c.id
            LEFT JOIN usuarios u ON a.autor_id = u.id
            WHERE a.club_id IN ({placeholders})
            ORDER BY a.fecha DESC LIMIT 15
        """, ids).fetchall()

    notifs = conn.execute("""
        SELECT * FROM notificaciones
        WHERE usuario_id = ?
        ORDER BY fecha DESC LIMIT 20
    """, (session["user_id"],)).fetchall()

    # Permisos PDF disponibles para descargar (de sus clubes)
    permisos_pdf = []
    if inscripciones:
        ids = [i["id"] for i in inscripciones]
        ph = ",".join(["?"] * len(ids))
        permisos_pdf = conn.execute(f"""
            SELECT p.*, c.nombre AS club_nombre
            FROM permisos p
            LEFT JOIN clubes c ON p.club_id = c.id
            WHERE p.archivo_pdf IS NOT NULL
              AND (p.estudiante_id = ? OR p.club_id IN ({ph}))
            ORDER BY p.fecha DESC LIMIT 15
        """, [session["user_id"]] + ids).fetchall()

    conn.close()
    return render_template("mi_club.html",
                           inscripciones=inscripciones,
                           anuncios=anuncios,
                           notifs=notifs,
                           usuario=usuario,
                           permisos_pdf=permisos_pdf)


@app.route("/editar-perfil", methods=["POST"])
@login_required
def editar_perfil():
    edad = request.form.get("edad") or None
    promedio = request.form.get("promedio")
    seccion = request.form.get("seccion") or None
    bachillerato = request.form.get("bachillerato") or None

    conn = get_db()
    user = conn.execute("SELECT * FROM usuarios WHERE id = ?", (session["user_id"],)).fetchone()

    # Solo estudiantes pueden editar promedio/edad/sección desde aquí
    if user["rol"] == "estudiante":
        try:
            prom = float(promedio) if promedio not in (None, "") else user["promedio"]
        except ValueError:
            prom = user["promedio"]
        edad_val = int(edad) if edad else user["edad"]
        conn.execute("""
            UPDATE usuarios SET edad = ?, promedio = ?, seccion = ?, bachillerato = ?
            WHERE id = ?
        """, (edad_val, prom, seccion or user["seccion"], bachillerato or user["bachillerato"], session["user_id"]))
    else:
        # Docente: solo edad / cargo opcional
        edad_val = int(edad) if edad else user["edad"]
        conn.execute("UPDATE usuarios SET edad = ? WHERE id = ?", (edad_val, session["user_id"]))

    # Foto nueva
    if "foto" in request.files:
        f = request.files["foto"]
        if f and f.filename and allowed_file(f.filename, ALLOWED_IMG):
            ext = f.filename.rsplit(".", 1)[1].lower()
            foto_nombre = secure_filename(f"perfil_{session['nie']}_{datetime.now().strftime('%Y%m%d%H%M%S')}.{ext}")
            f.save(os.path.join(app.config["UPLOAD_FOLDER"], foto_nombre))
            conn.execute("UPDATE usuarios SET foto = ? WHERE id = ?", (foto_nombre, session["user_id"]))
            session["foto"] = foto_nombre

    # Boleta PDF (solo estudiante)
    if user["rol"] == "estudiante" and "boleta" in request.files:
        f = request.files["boleta"]
        if f and f.filename and allowed_file(f.filename, ALLOWED_PDF):
            pdf_nombre = secure_filename(f"boleta_{session['nie']}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf")
            f.save(os.path.join(app.config["UPLOAD_FOLDER"], pdf_nombre))
            conn.execute("UPDATE usuarios SET boleta_pdf = ? WHERE id = ?", (pdf_nombre, session["user_id"]))

    conn.commit()
    conn.close()
    flash("Perfil actualizado correctamente.", "success")
    return redirect(url_for("mi_club"))

# -------------------- Agenda --------------------
@app.route("/agenda")
@login_required
def agenda():
    conn = get_db()
    eventos = conn.execute("""
        SELECT e.*, c.nombre AS club_nombre, c.categoria
        FROM eventos_club e
        LEFT JOIN clubes c ON e.club_id = c.id
        ORDER BY e.fecha DESC, e.creado DESC
    """).fetchall()
    conn.close()
    return render_template("agenda.html", eventos=eventos)

# -------------------- Panel Docente --------------------
@app.route("/gestion")
@login_required
@docente_required
def gestion():
    conn = get_db()
    if es_admin_general():
        mis_clubes = conn.execute("SELECT * FROM clubes ORDER BY nombre").fetchall()
    else:
        # Solo su club + sin asignar (para tomar uno)
        mis_clubes = conn.execute("""
            SELECT * FROM clubes
            WHERE docente_id = ? OR docente_id IS NULL
            ORDER BY nombre
        """, (session["user_id"],)).fetchall()

    estudiantes = conn.execute("""
        SELECT u.id, u.nie, u.nombre, u.seccion, u.bachillerato, u.promedio, u.boleta_pdf,
               i.estado, c.nombre AS club_nombre, c.id AS club_id
        FROM usuarios u
        LEFT JOIN inscripciones i ON u.id = i.estudiante_id
        LEFT JOIN clubes c ON i.club_id = c.id
        WHERE u.rol = 'estudiante'
        ORDER BY u.nombre
    """).fetchall()

    permisos = conn.execute("""
        SELECT p.*, u.nombre AS estudiante_nombre, c.nombre AS club_nombre
        FROM permisos p
        JOIN usuarios u ON p.estudiante_id = u.id
        LEFT JOIN clubes c ON p.club_id = c.id
        ORDER BY p.fecha DESC LIMIT 30
    """).fetchall()

    anuncios = conn.execute("""
        SELECT a.*, c.nombre AS club_nombre
        FROM anuncios a
        LEFT JOIN clubes c ON a.club_id = c.id
        ORDER BY a.fecha DESC LIMIT 20
    """).fetchall()

    conn.close()
    return render_template("gestion.html",
                           mis_clubes=mis_clubes,
                           estudiantes=estudiantes,
                           permisos=permisos,
                           anuncios=anuncios)

@app.route("/crear-club", methods=["POST"])
@login_required
@docente_required
def crear_club():
    # Docente/coordinador: máximo 1 club a cargo
    if es_docente_limitado():
        conn = get_db()
        n = conn.execute("SELECT COUNT(*) AS c FROM clubes WHERE docente_id = ?", (session["user_id"],)).fetchone()["c"]
        conn.close()
        if n >= 1:
            flash("Como docente/coordinador solo puedes administrar un club. Contacta al director para más permisos.", "error")
            return redirect(url_for("gestion"))

    nombre = request.form.get("nombre", "").strip()
    categoria = request.form.get("categoria", "").strip()
    descripcion = request.form.get("descripcion", "")
    horario = request.form.get("horario", "")
    lugar = request.form.get("lugar", "")
    requisitos = request.form.get("requisitos", "")
    capacidad = int(request.form.get("capacidad") or 20)
    turno = request.form.get("turno", "Matutino")

    foto_nombre = None
    if "foto" in request.files:
        f = request.files["foto"]
        if f and f.filename and allowed_file(f.filename, ALLOWED_IMG):
            ext = f.filename.rsplit(".", 1)[1].lower()
            foto_nombre = secure_filename(f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{nombre[:20]}.{ext}")
            f.save(os.path.join(app.config["UPLOAD_FOLDER"], foto_nombre))

    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO clubes
            (nombre, categoria, descripcion, horario, lugar, requisitos, capacidad, docente_id, foto, turno)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (nombre, categoria, descripcion, horario, lugar, requisitos,
              capacidad, session["user_id"], foto_nombre, turno))
        conn.commit()
        flash(f"Club «{nombre}» creado correctamente.", "success")
    except sqlite3.IntegrityError:
        flash("Ya existe un club con ese nombre.", "error")
    finally:
        conn.close()
    return redirect(url_for("gestion"))

@app.route("/editar-horario/<int:club_id>", methods=["POST"])
@login_required
@docente_required
def editar_horario(club_id):
    nuevo_horario = request.form.get("horario", "").strip()
    nuevo_lugar = request.form.get("lugar", "").strip()
    conn = get_db()
    conn.execute("UPDATE clubes SET horario = ?, lugar = ? WHERE id = ?",
                 (nuevo_horario, nuevo_lugar, club_id))
    conn.commit()
    conn.close()
    flash("Horario actualizado.", "success")
    return redirect(url_for("gestion"))

@app.route("/publicar-anuncio", methods=["POST"])
@login_required
@docente_required
def publicar_anuncio():
    club_id = request.form.get("club_id")
    if club_id and not club_permitido(int(club_id)):
        flash("No tienes permiso sobre ese club.", "error")
        return redirect(url_for("gestion"))
    titulo = request.form.get("titulo", "").strip()
    contenido = request.form.get("contenido", "").strip()
    urgente = 1 if request.form.get("urgente") else 0

    if not titulo or not contenido:
        flash("Título y contenido son obligatorios.", "error")
        return redirect(url_for("gestion"))

    conn = get_db()
    conn.execute("""
        INSERT INTO anuncios (club_id, titulo, contenido, autor_id, urgente)
        VALUES (?, ?, ?, ?, ?)
    """, (club_id, titulo, contenido, session["user_id"], urgente))

    # Notificar a todos los inscritos del club
    inscritos = conn.execute("""
        SELECT estudiante_id FROM inscripciones
        WHERE club_id = ? AND estado = 'aceptado'
    """, (club_id,)).fetchall()

    for ins in inscritos:
        conn.execute("""
            INSERT INTO notificaciones (usuario_id, titulo, mensaje)
            VALUES (?, ?, ?)
        """, (ins["estudiante_id"], f"📢 {titulo}", contenido[:150]))

    conn.commit()
    conn.close()
    flash("Anuncio publicado y notificaciones enviadas a los estudiantes.", "success")
    return redirect(url_for("gestion"))

@app.route("/enviar-notificacion", methods=["POST"])
@login_required
@docente_required
def enviar_notificacion():
    titulo = request.form.get("titulo", "").strip()
    mensaje = request.form.get("mensaje", "").strip()
    club_id = request.form.get("club_id")

    conn = get_db()
    if club_id:
        destinatarios = conn.execute("""
            SELECT estudiante_id FROM inscripciones
            WHERE club_id = ? AND estado = 'aceptado'
        """, (club_id,)).fetchall()
    else:
        destinatarios = conn.execute("SELECT id AS estudiante_id FROM usuarios WHERE rol = 'estudiante'").fetchall()

    for d in destinatarios:
        conn.execute("""
            INSERT INTO notificaciones (usuario_id, titulo, mensaje)
            VALUES (?, ?, ?)
        """, (d["estudiante_id"], titulo, mensaje))

    conn.commit()
    conn.close()
    flash(f"Notificación enviada a {len(destinatarios)} estudiantes.", "success")
    return redirect(url_for("gestion"))

@app.route("/subir-pdf-permiso", methods=["POST"])
@login_required
@docente_required
def subir_pdf_permiso():
    club_id = request.form.get("club_id") or None
    if club_id and not club_permitido(int(club_id)):
        flash("No tienes permiso sobre ese club.", "error")
        return redirect(url_for("gestion"))
    motivo = request.form.get("motivo", "").strip()
    fecha_inicio = request.form.get("fecha_inicio", "")
    fecha_fin = request.form.get("fecha_fin", "")
    # Si no se elige estudiante, el PDF queda disponible para todo el club
    estudiante_id = request.form.get("estudiante_id") or None
    if estudiante_id == "":
        estudiante_id = None

    pdf_nombre = None
    if "pdf" in request.files:
        f = request.files["pdf"]
        if f and f.filename and allowed_file(f.filename, ALLOWED_PDF):
            pdf_nombre = secure_filename(f"permiso_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf")
            f.save(os.path.join(app.config["UPLOAD_FOLDER"], pdf_nombre))

    if not pdf_nombre:
        flash("Debes seleccionar un archivo PDF.", "error")
        return redirect(url_for("gestion"))

    conn = get_db()
    # Si no hay estudiante concreto, usamos el propio docente como placeholder en estudiante_id
    # y el club_id identifica a quiénes aplica
    est_id = estudiante_id if estudiante_id else session["user_id"]
    conn.execute("""
        INSERT INTO permisos
        (estudiante_id, club_id, motivo, fecha_inicio, fecha_fin, archivo_pdf, estado, emitido_por)
        VALUES (?, ?, ?, ?, ?, ?, 'aprobado', ?)
    """, (est_id, club_id, motivo or "Permiso oficial de club", fecha_inicio, fecha_fin, pdf_nombre, session["user_id"]))

    # Notificar a inscritos del club
    if club_id:
        inscritos = conn.execute("""
            SELECT estudiante_id FROM inscripciones WHERE club_id = ? AND estado = 'aceptado'
        """, (club_id,)).fetchall()
        for ins in inscritos:
            conn.execute("""
                INSERT INTO notificaciones (usuario_id, titulo, mensaje)
                VALUES (?, ?, ?)
            """, (ins["estudiante_id"], "📄 Nuevo permiso PDF disponible",
                  motivo or "Hay un permiso oficial listo para descargar e imprimir."))

    conn.commit()
    conn.close()
    flash("Permiso PDF subido. Los estudiantes del club pueden descargarlo.", "success")
    return redirect(url_for("gestion"))

@app.route("/solicitar-permiso", methods=["POST"])
@login_required
def solicitar_permiso():
    if session["rol"] != "estudiante":
        flash("Solo estudiantes pueden solicitar permisos.", "error")
        return redirect(url_for("mi_club"))

    club_id = request.form.get("club_id")
    motivo = request.form.get("motivo", "").strip()
    fecha_inicio = request.form.get("fecha_inicio", "")
    fecha_fin = request.form.get("fecha_fin", "")

    conn = get_db()
    conn.execute("""
        INSERT INTO permisos (estudiante_id, club_id, motivo, fecha_inicio, fecha_fin, estado)
        VALUES (?, ?, ?, ?, ?, 'pendiente')
    """, (session["user_id"], club_id, motivo, fecha_inicio, fecha_fin))
    conn.commit()
    conn.close()
    flash("Solicitud de permiso enviada al encargado del club.", "success")
    return redirect(url_for("mi_club"))

@app.route("/marcar-leida/<int:notif_id>", methods=["POST"])
@login_required
def marcar_leida(notif_id):
    conn = get_db()
    conn.execute("UPDATE notificaciones SET leida = 1 WHERE id = ? AND usuario_id = ?",
                 (notif_id, session["user_id"]))
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for("mi_club"))

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

# -------------------- Ejecutar --------------------
@app.route("/crear-evento", methods=["POST"])
@login_required
@docente_required
def crear_evento():
    club_id = request.form.get("club_id")
    if club_id and not club_permitido(int(club_id)):
        flash("No tienes permiso sobre ese club.", "error")
        return redirect(url_for("gestion"))
    titulo = request.form.get("titulo", "").strip()
    descripcion = request.form.get("descripcion", "").strip()
    fecha = request.form.get("fecha", "")
    hora = request.form.get("hora", "")
    lugar = request.form.get("lugar", "")

    if not club_id or not titulo:
        flash("Club y título son obligatorios.", "error")
        return redirect(url_for("gestion"))

    conn = get_db()
    conn.execute("""
        INSERT INTO eventos_club (club_id, titulo, descripcion, fecha, hora, lugar, creado_por)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (club_id, titulo, descripcion, fecha, hora, lugar, session["user_id"]))

    inscritos = conn.execute("""
        SELECT estudiante_id FROM inscripciones WHERE club_id = ? AND estado = 'aceptado'
    """, (club_id,)).fetchall()
    for ins in inscritos:
        conn.execute("""
            INSERT INTO notificaciones (usuario_id, titulo, mensaje)
            VALUES (?, ?, ?)
        """, (ins["estudiante_id"], f"📅 Nuevo evento: {titulo}",
              f"{fecha} {hora} · {lugar or ''} {descripcion[:80]}"))
    conn.commit()
    conn.close()
    flash("Evento creado y notificado a los estudiantes del club.", "success")
    return redirect(url_for("gestion"))


if __name__ == "__main__":
    init_db()
    print("\n" + "="*55)
    print("  PORTAL DE CLUBES INFRAMEN")
    print("  http://127.0.0.1:5000")
    print("  Admin: NIE ADMIN00001  |  Contraseña: admin123")
    print("="*55 + "\n")
    app.run(debug=True, host="0.0.0.0", port=5000)
