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

def carga_masiva(request):
    resumen = None

    if request.method == "POST":
        tipo = request.POST.get("tipo")
        archivo = request.FILES.get("archivo")

        if not archivo:
            messages.error(request, "Debes seleccionar un archivo.")
            return redirect("biblioteca:carga_masiva")

        nombre_archivo = archivo.name.lower()

        try:
            if nombre_archivo.endswith((".xlsx", ".xls")):
                df = pd.read_excel(archivo)
            elif nombre_archivo.endswith((".csv", ".txt")):
                # Detecta automáticamente separadores (, ; o tabulación)
                df = pd.read_csv(archivo, sep=None, engine="python", encoding="utf-8-sig")
            else:
                messages.error(request, "Formato no soportado. Usa .xlsx, .xls, .csv o .txt.")
                return redirect("biblioteca:carga_masiva")
        except Exception as e:
            messages.error(request, f"Error al leer el archivo: {e}")
            return redirect("biblioteca:carga_masiva")

        # Normalizar nombres de columnas (minúsculas y sin espacios extra)
        df.columns = [str(col).strip().lower() for col in df.columns]

        creados, actualizados, omitidos = 0, 0, 0
        errores = []

        if tipo == "libros":
            anio_actual = timezone.now().year

            for idx, fila in df.iterrows():
                num_fila = idx + 2  # +2 considerando encabezado en fila 1
                isbn = str(fila.get("isbn", "")).strip() if pd.notna(fila.get("isbn")) else ""
                nombre = str(fila.get("nombre", "")).strip() if pd.notna(fila.get("nombre")) else ""

                if not isbn or not nombre:
                    omitidos += 1
                    errores.append(f"Fila {num_fila}: ISBN o Nombre vacío (omitida).")
                    continue

                autor = str(fila.get("autor", "")).strip() if pd.notna(fila.get("autor")) and str(fila.get("autor")).strip() else "Autor Desconocido"
                editorial = str(fila.get("editorial", "")).strip() if pd.notna(fila.get("editorial")) and str(fila.get("editorial")).strip() else "Sin Editorial"
                cat_nombre = str(fila.get("categoria", "")).strip() if pd.notna(fila.get("categoria")) and str(fila.get("categoria")).strip() else "General"

                anio_val = pd.to_numeric(fila.get("anio_publicacion"), errors="coerce")
                anio = int(anio_val) if pd.notna(anio_val) and anio_val > 0 else anio_actual

                stock_tot_val = pd.to_numeric(fila.get("stock_total"), errors="coerce")
                stock_total = int(stock_tot_val) if pd.notna(stock_tot_val) and stock_tot_val >= 0 else 1

                stock_disp_val = pd.to_numeric(fila.get("stock_disponible"), errors="coerce")
                stock_disponible = int(stock_disp_val) if pd.notna(stock_disp_val) and stock_disp_val >= 0 else stock_total

                # Respetar CheckConstraint: stock_disponible <= stock_total
                if stock_disponible > stock_total:
                    stock_disponible = stock_total

                categoria, _ = Categoria.objects.get_or_create(nombre=cat_nombre)

                try:
                    _, creado = Libro.objects.update_or_create(
                        isbn=isbn,
                        defaults={
                            "nombre": nombre,
                            "autor": autor,
                            "editorial": editorial,
                            "anio_publicacion": anio,
                            "categoria": categoria,
                            "stock_total": stock_total,
                            "stock_disponible": stock_disponible,
                        },
                    )
                    if creado:
                        creados += 1
                    else:
                        actualizados += 1
                except Exception as e:
                    omitidos += 1
                    errores.append(f"Fila {num_fila} ({nombre}): {e}")

        elif tipo == "alumnos":
            patron_codigo = re.compile(r"^u[0-9]{8}$")

            for idx, fila in df.iterrows():
                num_fila = idx + 2
                codigo = str(fila.get("codigo_alumno", "")).strip().lower() if pd.notna(fila.get("codigo_alumno")) else ""
                nombre = str(fila.get("nombre", "")).strip() if pd.notna(fila.get("nombre")) else ""

                if not codigo or not nombre or not patron_codigo.match(codigo):
                    omitidos += 1
                    errores.append(f"Fila {num_fila}: Código inválido (debe ser u + 8 dígitos) o Nombre vacío.")
                    continue

                carrera = str(fila.get("carrera", "")).strip() if pd.notna(fila.get("carrera")) and str(fila.get("carrera")).strip() else "Sin Especificar"
                correo = str(fila.get("correo", "")).strip() if pd.notna(fila.get("correo")) and str(fila.get("correo")).strip() else f"{codigo}@utp.edu.pe"
                estado_raw = str(fila.get("estado", "")).strip().capitalize() if pd.notna(fila.get("estado")) else "Activo"
                estado = estado_raw if estado_raw in (Alumno.Estado.ACTIVO, Alumno.Estado.SUSPENDIDO) else Alumno.Estado.ACTIVO

                try:
                    _, creado = Alumno.objects.update_or_create(
                        codigo_alumno=codigo,
                        defaults={
                            "nombre": nombre,
                            "carrera": carrera,
                            "correo": correo,
                            "estado": estado,
                        },
                    )
                    if creado:
                        creados += 1
                    else:
                        actualizados += 1
                except Exception as e:
                    omitidos += 1
                    errores.append(f"Fila {num_fila} ({codigo}): {e}")

        resumen = {
            "creados": creados,
            "actualizados": actualizados,
            "omitidos": omitidos,
            "errores": errores[:15],  # Mostrar los primeros 15 avisos
        }
        messages.success(request, f"Proceso finalizado: {creados} creados, {actualizados} actualizados, {omitidos} omitidos.")

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

    # --- 1. Métricas generales con NumPy ---
    stocks_totales = np.array([l.stock_total for l in libros], dtype=int)
    stocks_disp = np.array([l.stock_disponible for l in libros], dtype=int)

    total_ejemplares = int(np.sum(stocks_totales)) if stocks_totales.size else 0
    total_disponibles = int(np.sum(stocks_disp)) if stocks_disp.size else 0
    promedio_stock = round(float(np.mean(stocks_totales)), 2) if stocks_totales.size else 0
    tasa_disponibilidad = round((total_disponibles / total_ejemplares) * 100, 1) if total_ejemplares > 0 else 0

    # --- 2. Gráfico 1: Stock Total vs Disponible por Categoría ---
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

    # --- 3. Gráfico 2: Distribución de Préstamos por Estado ---
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