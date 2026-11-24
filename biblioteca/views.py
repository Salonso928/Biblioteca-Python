import base64
import io
import re
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from django.http import Http404, JsonResponse
from .models import Alumno, Categoria, Libro, Prestamo
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone

from .forms import AlumnoForm, LibroForm, PrestamoForm
from .models import Alumno, Libro, Prestamo


def listar_libros(request):
    consulta = request.GET.get("q", "").strip()
    libros = Libro.objects.select_related("categoria").all()

    if consulta:
        libros = libros.filter(
            Q(nombre__icontains=consulta)
            | Q(autor__icontains=consulta)
            | Q(codigo__icontains=consulta)
        )

    return render(request, "biblioteca/libros/lista.html", {
        "libros": libros,
        "consulta": consulta,
    })


def listar_alumnos(request):
    alumnos = Alumno.objects.all()
    return render(request, "biblioteca/alumnos/lista.html", {
        "alumnos": alumnos,
    })


def registrar_libro(request):
    if request.method == "POST":
        form = LibroForm(request.POST)

        if form.is_valid():
            libro = form.save(commit=False)
            libro.stock_disponible = libro.stock_total
            libro.save()
            messages.success(request, "El libro se registró correctamente.")
            return redirect("biblioteca:listar_libros")
    else:
        form = LibroForm()

    return render(request, "biblioteca/libros/formulario.html", {
        "form": form,
    })


def registrar_alumno(request):
    if request.method == "POST":
        form = AlumnoForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, "El alumno se registró correctamente.")
            return redirect("biblioteca:listar_alumnos")
    else:
        form = AlumnoForm()

    return render(request, "biblioteca/alumnos/formulario.html", {
        "form": form,
    })


def listar_prestamos(request):
    prestamos = Prestamo.objects.select_related("alumno", "libro").all()
    return render(request, "biblioteca/prestamos/lista.html", {
        "prestamos": prestamos,
    })


def registrar_prestamo(request):
    if request.method == "POST":
        form = PrestamoForm(request.POST)

        if "buscar" in request.POST:
            return render(request, "biblioteca/prestamos/formulario.html", {
                "form": form,
            })

        if form.is_valid():
            alumno = form.cleaned_data["alumno"]
            libro = form.cleaned_data["libro"]

            if alumno.estado == Alumno.Estado.SUSPENDIDO:
                messages.error(request, "El alumno está suspendido y no puede solicitar préstamos.")
            elif libro.stock_disponible <= 0:
                messages.error(request, "No hay ejemplares disponibles de este libro.")
            else:
                tiene_prestamo_atrasado = Prestamo.objects.filter(
                    alumno=alumno,
                    estado=Prestamo.Estado.ATRASADO,
                    fecha_devolucion_real__isnull=True,
                ).exists()

                if tiene_prestamo_atrasado:
                    messages.error(request, "El alumno tiene préstamos atrasados pendientes.")
                else:
                    with transaction.atomic():
                        libro = Libro.objects.select_for_update().get(pk=libro.pk)

                        if libro.stock_disponible <= 0:
                            messages.error(request, "No hay ejemplares disponibles de este libro.")
                        else:
                            prestamo = form.save(commit=False)
                            prestamo.estado = Prestamo.Estado.ACTIVO
                            prestamo.save()

                            libro.stock_disponible -= 1
                            libro.save(update_fields=("stock_disponible",))

                            messages.success(request, "Préstamo registrado correctamente.")
                            return redirect("biblioteca:listar_prestamos")
    else:
        form = PrestamoForm()

    return render(request, "biblioteca/prestamos/formulario.html", {
        "form": form,
    })


def registrar_devolucion(request, prestamo_id):
    try:
        prestamo = Prestamo.objects.select_related("libro").get(pk=prestamo_id)
    except Prestamo.DoesNotExist:
        raise Http404("Préstamo no encontrado")

    if request.method == "POST":
        if prestamo.estado == Prestamo.Estado.DEVUELTO:
            messages.warning(request, "Este préstamo ya fue devuelto.")
            return redirect("biblioteca:listar_prestamos")

        with transaction.atomic():
            prestamo = Prestamo.objects.select_for_update().get(pk=prestamo.pk)
            libro = Libro.objects.select_for_update().get(pk=prestamo.libro_id)

            prestamo.fecha_devolucion_real = timezone.now()
            prestamo.estado = Prestamo.Estado.DEVUELTO
            prestamo.save(update_fields=(
                "fecha_devolucion_real",
                "estado",
            ))

            libro.stock_disponible += 1

            if libro.stock_disponible > libro.stock_total:
                libro.stock_disponible = libro.stock_total

            libro.save(update_fields=("stock_disponible",))

        messages.success(request, "Devolución registrada correctamente.")
        return redirect("biblioteca:listar_prestamos")

    return render(request, "biblioteca/prestamos/devolucion.html", {
        "prestamo": prestamo,
    })

def buscar_libros_api(request):
    consulta = request.GET.get("q", "").strip()
    filtro = request.GET.get("filtro", "todos")

    if not consulta:
        return JsonResponse({"resultados": []})

    libros = Libro.objects.select_related("categoria").all()

    if filtro == "codigo":
        libros = libros.filter(Q(codigo__icontains=consulta) | Q(isbn__icontains=consulta))
    elif filtro == "nombre":
        libros = libros.filter(nombre__icontains=consulta)
    elif filtro == "autor":
        libros = libros.filter(autor__icontains=consulta)
    else:
        libros = libros.filter(
            Q(nombre__icontains=consulta)
            | Q(autor__icontains=consulta)
            | Q(codigo__icontains=consulta)
            | Q(isbn__icontains=consulta)
        )

    resultados = [
        {
            "codigo": libro.codigo,
            "isbn": libro.isbn,
            "nombre": libro.nombre,
            "autor": libro.autor,
            "categoria": libro.categoria.nombre,
            "stock_disponible": libro.stock_disponible,
            "stock_total": libro.stock_total,
        }
        for libro in libros[:8]
    ]
    return JsonResponse({"resultados": resultados})

def _texto(fila, columna, por_defecto=""):
    """Obtiene un valor de texto limpio o un valor por defecto si está vacío/NaN."""
    valor = fila.get(columna)
    if pd.isna(valor):
        return por_defecto
    texto = str(valor).strip()
    return texto if texto else por_defecto


def _entero(fila, columna, por_defecto, minimo=None):
    """Convierte a entero de forma segura; si falla o es menor al mínimo, usa por_defecto."""
    numero = pd.to_numeric(fila.get(columna), errors="coerce")
    if pd.isna(numero):
        return por_defecto
    entero = int(numero)
    if minimo is not None and entero < minimo:
        return por_defecto
    return entero


def _leer_dataframe(archivo):
    nombre = archivo.name.lower()
    if nombre.endswith((".xlsx", ".xls")):
        df = pd.read_excel(archivo)
    elif nombre.endswith((".csv", ".txt")):
        df = pd.read_csv(archivo, sep=None, engine="python", encoding="utf-8-sig")
    else:
        raise ValueError("Formato no soportado. Usa .xlsx, .xls, .csv o .txt.")

    df.columns = [str(col).strip().lower() for col in df.columns]
    return df


def _importar_libros(df):
    stats = {"creados": 0, "actualizados": 0, "omitidos": 0, "errores": []}
    anio_actual = timezone.now().year

    for idx, fila in df.iterrows():
        num_fila = idx + 2
        isbn = _texto(fila, "isbn")
        nombre = _texto(fila, "nombre")

        if not isbn or not nombre:
            stats["omitidos"] += 1
            stats["errores"].append(f"Fila {num_fila}: ISBN o Nombre vacío.")
            continue

        stock_total = _entero(fila, "stock_total", por_defecto=1, minimo=0)
        stock_disponible = _entero(fila, "stock_disponible", por_defecto=stock_total, minimo=0)
        stock_disponible = min(stock_disponible, stock_total)

        categoria, _ = Categoria.objects.get_or_create(
            nombre=_texto(fila, "categoria", por_defecto="General")
        )

        try:
            _, creado = Libro.objects.update_or_create(
                isbn=isbn,
                defaults={
                    "nombre": nombre,
                    "autor": _texto(fila, "autor", por_defecto="Autor Desconocido"),
                    "editorial": _texto(fila, "editorial", por_defecto="Sin Editorial"),
                    "anio_publicacion": _entero(fila, "anio_publicacion", por_defecto=anio_actual, minimo=1),
                    "categoria": categoria,
                    "stock_total": stock_total,
                    "stock_disponible": stock_disponible,
                },
            )
            stats["creados" if creado else "actualizados"] += 1
        except Exception as e:
            stats["omitidos"] += 1
            stats["errores"].append(f"Fila {num_fila} ({nombre}): {e}")

    return stats


def _importar_alumnos(df):
    stats = {"creados": 0, "actualizados": 0, "omitidos": 0, "errores": []}
    patron_codigo = re.compile(r"^u[0-9]{8}$")
    estados_validos = {Alumno.Estado.ACTIVO, Alumno.Estado.SUSPENDIDO}

    for idx, fila in df.iterrows():
        num_fila = idx + 2
        codigo = _texto(fila, "codigo_alumno").lower()
        nombre = _texto(fila, "nombre")

        if not codigo or not nombre or not patron_codigo.match(codigo):
            stats["omitidos"] += 1
            stats["errores"].append(f"Fila {num_fila}: Código inválido o Nombre vacío.")
            continue

        estado_sin_formato = _texto(fila, "estado", por_defecto=Alumno.Estado.ACTIVO).upper()
        estado = estado_sin_formato if estado_sin_formato in estados_validos else Alumno.Estado.ACTIVO

        try:
            _, creado = Alumno.objects.update_or_create(
                codigo_alumno=codigo,
                defaults={
                    "nombre": nombre,
                    "carrera": _texto(fila, "carrera", por_defecto="Sin Especificar"),
                    "correo": _texto(fila, "correo", por_defecto=f"{codigo}@utp.edu.pe"),
                    "estado": estado,
                },
            )
            stats["creados" if creado else "actualizados"] += 1
        except Exception as e:
            stats["omitidos"] += 1
            stats["errores"].append(f"Fila {num_fila} ({codigo}): {e}")

    return stats


def carga_masiva(request):
    resumen = None

    if request.method == "POST":
        tipo = request.POST.get("tipo")
        archivo = request.FILES.get("archivo")

        if not archivo:
            messages.error(request, "Debes seleccionar un archivo.")
            return redirect("biblioteca:carga_masiva")

        try:
            df = _leer_dataframe(archivo)
        except Exception as e:
            messages.error(request, f"Error al leer el archivo: {e}")
            return redirect("biblioteca:carga_masiva")

        if tipo == "libros":
            stats = _importar_libros(df)
        elif tipo == "alumnos":
            stats = _importar_alumnos(df)
        else:
            messages.error(request, "Tipo de importación no válido.")
            return redirect("biblioteca:carga_masiva")

        resumen = {**stats, "errores": stats["errores"][:15]}
        messages.success(
            request,
            f"Proceso finalizado: {stats['creados']} creados, "
            f"{stats['actualizados']} actualizados, {stats['omitidos']} omitidos.",
        )

    return render(request, "biblioteca/carga_masiva.html", {"resumen": resumen})

def _fig_a_base64(fig):
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", bbox_inches="tight", dpi=110)
    buffer.seek(0)
    imagen_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    plt.close(fig)
    return imagen_base64


def estadisticas(request):
    libros = Libro.objects.select_related("categoria").all()
    prestamos = Prestamo.objects.all()

    # aqui sacamos los datos usando numpy
    stocks_totales = np.array([l.stock_total for l in libros], dtype=int)
    stocks_disp = np.array([l.stock_disponible for l in libros], dtype=int)

    total_ejemplares = int(np.sum(stocks_totales)) if stocks_totales.size else 0
    total_disponibles = int(np.sum(stocks_disp)) if stocks_disp.size else 0
    promedio_stock = round(float(np.mean(stocks_totales)), 2) if stocks_totales.size else 0
    tasa_disponibilidad = round((total_disponibles / total_ejemplares) * 100, 1) if total_ejemplares > 0 else 0

    # Grafico 1 es de  Stock Total vs Disponible por Categoría ---
    grafico_categorias = None
    categorias = list(Categoria.objects.all())
    if categorias:
        nombres_cat = [c.nombre for c in categorias]
        totales_cat = np.array([sum(l.stock_total for l in libros if l.categoria_id == c.id) for c in categorias])
        disp_cat = np.array([sum(l.stock_disponible for l in libros if l.categoria_id == c.id) for c in categorias])

        x = np.arange(len(nombres_cat))
        ancho = 0.35

        fig, ax = plt.subplots(figsize=(7, 4))
        ax.bar(x - ancho / 2, totales_cat, ancho, label="Stock Total", color="#0d6efd")
        ax.bar(x + ancho / 2, disp_cat, ancho, label="Disponible", color="#198754")
        ax.set_title("Stock Total vs. Disponible por Categoría")
        ax.set_xticks(x)
        ax.set_xticklabels(nombres_cat, rotation=25, ha="right")
        ax.set_ylabel("Ejemplares")
        ax.legend()
        ax.grid(axis="y", linestyle="--", alpha=0.5)
        grafico_categorias = _fig_a_base64(fig)

    # grafico 2 de Distribución de Préstamos por Estado ---
    grafico_prestamos = None
    if prestamos.exists():
        estados = [Prestamo.Estado.ACTIVO, Prestamo.Estado.DEVUELTO, Prestamo.Estado.ATRASADO]
        conteos = np.array([prestamos.filter(estado=e).count() for e in estados])
        if np.sum(conteos) > 0:
            colores = ["#0d6efd", "#198754", "#dc3545"]
            fig, ax = plt.subplots(figsize=(5.5, 4))
            ax.pie(conteos, labels=estados, autopct="%1.1f%%", startangle=140, colors=colores)
            ax.set_title("Estado de Préstamos")
            grafico_prestamos = _fig_a_base64(fig)

    return render(request, "biblioteca/estadisticas.html", {
        "total_ejemplares": total_ejemplares,
        "total_disponibles": total_disponibles,
        "promedio_stock": promedio_stock,
        "tasa_disponibilidad": tasa_disponibilidad,
        "grafico_categorias": grafico_categorias,
        "grafico_prestamos": grafico_prestamos,
    })